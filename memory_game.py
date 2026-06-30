import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import base64
import re
import traceback
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime

st.set_page_config(page_title="亞太股市大盤監控器 v8.0", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v8.0 - 協議級除錯版)")
st.markdown("已修正：Currents 多軌大盤查詢池、鎖定台日韓三大指數、CSV 內置協議級網路與 DOM 狀態日誌。")

# 初始化 Session State
if "all_articles" not in st.session_state:
    st.session_state.all_articles = None
if "api_statuses" not in st.session_state:
    st.session_state.api_statuses = None

# Sidebar
with st.sidebar:
    st.header("🔑 API 憑證配置")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents API", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    
    st.header("⚙️ 引擎配置")
    max_results = st.slider("單一市場抓取量", 5, 25, 15)
    scrape_body = st.checkbox("深度內文追蹤與分析", value=True)

def deep_protocol_decode(google_url):
    """【協議級黑盒子】深度追蹤 Google 網址跳轉狀態，抓出阻斷反爬蟲的元凶"""
    log_chain = []
    log_chain.append(f"[INIT] 原始 URL 長度: {len(google_url)}")
    
    if "news.google.com" not in google_url:
        return google_url, "[SKIP] 已是原始媒體連結"
    
    # 軌道 1：優化版本地 Base64 二進位掃描
    try:
        match = re.search(r"articles/([a-zA-Z0-9_=-]+)", google_url)
        if match:
            b64_str = match.group(1).replace('-', '+').replace('_', '/')
            b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
            decoded_bytes = base64.b64decode(b64_str)
            # 使用更寬鬆的掃描機制，直接提取符合 URL 特徵的 ASCII 區塊
            urls = re.findall(r'https?://[a-zA-Z0-9_\-./?=&%#+]+', decoded_bytes.decode('utf-8', errors='ignore'))
            if urls:
                clean_url = urls[0].split('\x00')[0].split('\x01')[0]
                if "news.google.com" not in clean_url and len(clean_url) > 12:
                    log_chain.append(f"[SUCCESS_B64] 演算法成功解析: {clean_url[:40]}...")
                    return clean_url, " | ".join(log_chain)
            log_chain.append("[B64_WARN] 未能從二進位流中分離出合法第三方 URL")
        else:
            log_chain.append("[B64_FAIL] 網址未匹配到 articles/ 標籤")
    except Exception as e:
        log_chain.append(f"[B64_ERR] 演算法異常: {str(e)}")

    # 軌道 2：協議級 Session 網路流追蹤
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
            "Connection": "keep-alive"
        }
        log_chain.append("[NET_REQ] 發送高仿真協議請求...")
        res = session.get(google_url, headers=headers, timeout=6, allow_redirects=True)
        
        # 記錄詳細的跳轉路徑狀態碼
        if res.history:
            chain = " -> ".join([f"[{r.status_code}]" for r in res.history])
            log_chain.append(f"[NET_REDIRECTS] 經歷跳轉鏈: {chain} -> 最終碼: [{res.status_code}]")
        else:
            log_chain.append(f"[NET_RESP] 無跳轉. 狀態碼: {res.status_code}")
            
        log_chain.append(f"[NET_FINAL_URL] 最終停留在: {res.url[:50]}")

        if "news.google.com" not in res.url:
            log_chain.append("[SUCCESS_NET] 網路流成功擊穿跳轉")
            return res.url, " | ".join(log_chain)
            
        # 軌道 3：深入剖析留在 Google 網域時的 DOM 結構
        soup = BeautifulSoup(res.text, 'html.parser')
        page_title = soup.title.string.strip() if soup.title else "無標題"
        log_chain.append(f"[DOM_DEBUG] Google 頁面標題: '{page_title}' | 源碼長度: {len(res.text)}")
        
        # 記錄關鍵的回應標頭片段，判斷是否遭遇安全阻斷
        server_hd = res.headers.get('Server', 'Unknown')
        log_chain.append(f"[SERVER_HEADER] 伺服器類型: {server_hd}")

        # 嘗試從前端混淆中強制提取
        meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
        if meta_refresh:
            refresh_url = re.search(r"url=(http.*)", meta_refresh['content'], re.IGNORECASE)
            if refresh_url:
                target = refresh_url.group(1).strip('"').strip("'")
                log_chain.append(f"[SUCCESS_META] 捕獲前端跳轉標籤: {target[:30]}")
                return target, " | ".join(log_chain)
                
        noscript_a = soup.find('noscript')
        if noscript_a and noscript_a.find('a'):
            target = noscript_a.find('a')['href']
            log_chain.append(f"[SUCCESS_NOSCRIPT] 提取到備用載具連結: {target[:30]}")
            return target, " | ".join(log_chain)

        log_chain.append(f"[RAW_HTML_SNIPPET] 頁面特徵: {res.text[:180].replace(',', ' ')}")
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        log_chain.append(f"[NET_CRASH] 網路協議層崩潰: {error_msg}")
        
    return google_url, " | ".join(log_chain)

def get_full_content_verbose(url):
    """【目標媒體爬蟲】訪問最終新聞網站，記錄詳細的 DOM 提取日誌"""
    log_chain = []
    if not url or "news.google.com" in url: 
        return "無內文", "[SPIDER_SKIP] 由於解密未完成，放棄爬取目標網站"
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        r = requests.get(url, timeout=5, headers=headers)
        r.encoding = r.apparent_encoding
        log_chain.append(f"[REQ] 狀態: {r.status_code} | 編碼: {r.encoding} | 長度: {len(r.text)}")
        
        if r.status_code != 200:
            return "無內文", " | ".join(log_chain) + " | [FAIL] 網站拒絕請求"
            
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'noscript', 'form']): s.decompose()
        
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 25]
        log_chain.append(f"[DOM] 尋獲有效段落數: {len(paragraphs)}")
        
        text = " ".join(paragraphs)
        if not text:
            return "無內文", " | ".join(log_chain) + " | [FAIL] 未能匹配到標準段落格式"
            
        block_keywords = ["cookie", "privacy policy", "subscribe", "閱讀全文", "版權所有"]
        if any(kw in text.lower() for kw in block_keywords) and len(text) < 350:
            return "內容已屏蔽", " | ".join(log_chain) + " | [WARN] 網頁被反爬蟲條款或登入牆攔截"
            
        return text[:1500], " | ".join(log_chain) + f" | [SUCCESS] 成功導出 {len(text)} 字"
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        return "無內文", " | ".join(log_chain) + f" | [CRASH] 錯誤: {error_msg}"

def fetch_google_news(query, hl_cc, max_r, category_label):
    try:
        q = urllib.parse.quote(query)
        parts = hl_cc.split('_')
        url = f"https://news.google.com/rss/search?q={q}&hl={parts[0]}&gl={parts[1]}"
        feed = feedparser.parse(url)
        arts = []
        for entry in feed.entries[:max_r]:
            raw_link = entry.link
            real_link, url_log = deep_protocol_decode(raw_link) if scrape_body else (raw_link, "未開啟解密")
            content_summary, spider_log = get_full_content_verbose(real_link) if scrape_body else ("未啟用", "未啟用")
            
            arts.append({
                "📊 維度": category_label,
                "來源": "Google News",
                "標題": entry.title,
                "發布時間": entry.get("published", "N/A"),
                "連結": real_link,
                "摘要": entry.get("summary", ""),
                "內文摘要": content_summary,
                "🛠️ 協議級解密日誌": url_log,
                "🕷️ 媒體爬蟲日誌": spider_log
            })
        return arts
    except Exception as e:
        st.error(f"Google News 模組異常: {str(e)}")
        return []

# --- 主執行流程 ---
if st.button("🚀 執行亞太三大股市大盤多維掃描", type="primary"):
    with st.spinner("正透過協議級通道向台、日、韓大盤數據庫發送調用..."):
        all_articles = []
        api_statuses = {}
        
        # 1. Google News 核心大盤詞彙配置
        g_arts = []
        g_arts.extend(fetch_google_news("(加權指數 OR 台股大盤 OR 三大法人買賣超 OR 盤勢分析)", "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news("(日經225 OR 日經指數 OR Nikkei 225 OR 東京股市大盤)", "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news("(韓國綜合指數 OR KOSPI OR 首爾股市大盤 OR 韓股動態)", "ko_KR", max_results, "韓股大盤動態"))
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取空值"

        # 2. NewsData.io 大盤配置
        if newsdata_key:
            try:
                url = f"https://newsdata.io/api/1/latest?apikey={newsdata_key}&country=tw,jp,kr&q=(index OR market OR stocks OR \"加權指數\" OR \"日經\")"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    nd_arts = resp.json().get("results", [])[:max_results]
                    for a in nd_arts:
                        content_summary, spider_log = get_full_content_verbose(a.get("link")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太總體大盤", "來源": "NewsData.io", "標題": a.get("title"),
                            "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 協議級解密日誌": "[API原生網址]", "🕷️ 媒體爬蟲日誌": spider_log
                        })
                    api_statuses["NewsData.io API"] = f"🟢 OK ({len(nd_arts)} 則)"
                else:
                    api_statuses["NewsData.io API"] = f"🔴 錯誤狀態碼: {resp.status_code}"
            except Exception as e:
                api_statuses["NewsData.io API"] = f"🔴 異常: {str(e)}"

        # 3. Currents API 核心修復（動態多線程調用池，解決 AND 歸零問題）
        if currents_key:
            try:
                # 將多關鍵字拆開為獨立的大盤探索請求，確保台日韓均有產出
                target_queries = ["TAIEX market", "Nikkei index", "KOSPI stock"]
                currents_pool = []
                
                for q_term in target_queries:
                    url = "https://api.currentsapi.services/v1/search"
                    params = {"apiKey": currents_key, "keywords": q_term, "limit": 8}
                    resp = requests.get(url, params=params, timeout=6)
                    if resp.status_code == 200:
                        currents_pool.extend(resp.json().get("news", []))
                
                # 去重合併
                seen_urls = set()
                final_currents = []
                for n in currents_pool:
                    if n.get("url") not in seen_urls:
                        seen_urls.add(n.get("url"))
                        final_currents.append(n)
                
                for a in final_currents[:max_results]:
                    content_summary, spider_log = get_full_content_verbose(a.get("url")) if scrape_body else ("未啟用", "未啟用")
                    all_articles.append({
                        "📊 維度": "亞太總體大盤", "來源": "Currents", "標題": a.get("title"),
                        "發布時間": a.get("published"), "連結": a.get("url"), "摘要": a.get("description", ""),
                        "內文摘要": content_summary, "🛠️ 協議級解密日誌": "[API多軌查詢池]", "🕷️ 媒體爬蟲日誌": spider_log
                    })
                api_statuses["Currents API"] = f"🟢 OK ({len(final_currents)} 則)"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 查詢池異常: {str(e)}"

        # 4. Marketaux API 大盤精準錨點
        if marketaux_key:
            try:
                # ^TWII (台灣加權), ^N225 (日經225), ^KS11 (韓國綜合指數)
                url = f"https://api.marketaux.com/v1/news/all?symbols=^TWII,^N225,^KS11&limit={max_results}&api_token={marketaux_key}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    ma_arts = resp.json().get("data", [])
                    for a in ma_arts:
                        all_articles.append({
                            "📊 維度": "指數宏觀行情", "來源": "Marketaux", "標題": a.get("title"),
                            "發布時間": a.get("published_at"), "連結": a.get("url"), "摘要": a.get("description"),
                            "內文摘要": a.get("snippet", ""), "🛠️ 協議級解密日誌": "[API大盤指數連動]", "🕷️ 媒體爬蟲日誌": "[無需二次爬取]"
                        })
                    api_statuses["Marketaux API"] = f"🟢 OK ({len(ma_arts)} 則)"
                else:
                    api_statuses["Marketaux API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Marketaux API"] = f"🔴 異常: {str(e)}"

        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# --- 介面渲染面板 ---
if st.session_state.api_statuses:
    st.subheader("🔌 全渠道大盤引擎連線狀態")
    cols = st.columns(4)
    for i, (api_name, status_text) in enumerate(st.session_state.api_statuses.items()):
        cols[i].metric(label=api_name, value=status_text)
    st.markdown("---")

if st.session_state.all_articles:
    df = pd.DataFrame(st.session_state.all_articles)
    st.success(f"✅ 當前成功導出 {len(df)} 則台日韓股市大盤動態數據！")
    
    st.subheader("📋 亞太前瞻大盤監控面板（含協議級除錯日誌）")
    st.dataframe(df, width='stretch')

    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.download_button("📥 下載全新協議偵錯全維度大盤數據 (CSV)", csv_buffer.getvalue(), f"asia_stock_macro_verbose_v8_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
