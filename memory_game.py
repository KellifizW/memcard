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

st.set_page_config(page_title="亞太股市大盤監控器 v7.0", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v7.0 - 極限除錯強固版)")
st.markdown("已升級：黑盒子級別極限除錯日誌、多語系台日韓大盤動態對齊、網絡重定向全狀態鏈追蹤。")

# 初始化 Session State，防止下載 CSV 後頁面重置
if "all_articles" not in st.session_state:
    st.session_state.all_articles = None
if "api_statuses" not in st.session_state:
    st.session_state.api_statuses = None

# Sidebar
with st.sidebar:
    st.header("🔑 API Keys")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents API", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    
    st.header("⚙️ 抓取配置")
    max_results = st.slider("每來源最多抓取", 5, 25, 15)
    scrape_body = st.checkbox("深度分析（追蹤真實網址並爬取內文）", value=True)

def deep_debug_google_url(google_url):
    """【極限除錯級別】解密 Google News 網址，並記錄每一步的底層網路與演算法狀態"""
    log_chain = []
    log_chain.append(f"[INIT] 開始處理 Google 原始網址: {google_url[:60]}...")
    
    if "news.google.com" not in google_url:
        return google_url, "[SKIP] 網址本身已是非 Google 原始媒體網址"
    
    # 軌道 1：本地 Base64 逆向演算法拆解
    try:
        match = re.search(r"articles/([a-zA-Z0-9_=-]+)", google_url)
        if match:
            b64_str = match.group(1).replace('-', '+').replace('_', '/')
            b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
            decoded_bytes = base64.b64decode(b64_str)
            decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
            log_chain.append(f"[B64] 成功解碼 Base64 區塊, 長度: {len(decoded_text)} 字元")
            
            urls = re.findall(r'https?://[^\s"\u0000-\u001f]+', decoded_text)
            if urls:
                clean_url = urls[0].split('')[0].split('\x01')[0].split('\x02')[0]
                if "news.google.com" not in clean_url and len(clean_url) > 12:
                    log_chain.append(f"[SUCCESS] 演算法還原成功 -> {clean_url[:50]}")
                    return clean_url, " | ".join(log_chain)
            log_chain.append("[B64_WARN] 未能在解密文本中找到合法的第三方 HTTP 網址")
        else:
            log_chain.append("[B64_FAIL] 網址中未匹配到 articles/ 加密區塊")
    except Exception as e:
        log_chain.append(f"[B64_ERR] 演算法崩潰: {str(e)}")

    # 軌道 2：高仿真 Session 網絡流跳轉追蹤
    try:
        session = requests.Session()
        # 使用極其逼真的桌面端 Chrome 標頭，防止被 TLS 拒絕
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache"
        }
        log_chain.append("[HTTP_REQ] 發送 Session GET 請求以追蹤重定向...")
        res = session.get(google_url, headers=headers, timeout=5, allow_redirects=True)
        
        # 記錄重定向歷史鏈
        if res.history:
            history_chain = " -> ".join([f"[{r.status_code}] {r.url[:40]}" for r in res.history])
            log_chain.append(f"[REDIRECT_CHAIN] {history_chain} -> 最終: [{res.status_code}]")
        else:
            log_chain.append(f"[HTTP_RESP] 無跳轉歷史. 狀態碼: {res.status_code}")

        if res.url and "news.google.com" not in res.url:
            log_chain.append(f"[SUCCESS] 網路流擊穿成功 -> {res.url[:50]}")
            return res.url, " | ".join(log_chain)
            
        # 軌道 3：檢查源碼中是否有新版前端 Meta Refresh 或是 JS 混淆跳轉
        log_chain.append("[DOM_PARSE] 仍留在 Google 網域，啟動網頁源碼深度解析...")
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 檢查 Meta Refresh
        meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
        if meta_refresh:
            refresh_url = re.search(r"url=(http.*)", meta_refresh['content'], re.IGNORECASE)
            if refresh_url:
                target_url = refresh_url.group(1).strip('"').strip("'")
                log_chain.append(f"[SUCCESS] 提取到 Meta Refresh 標籤網址 -> {target_url[:50]}")
                return target_url, " | ".join(log_chain)
        
        # 檢查常見的 A 標籤備用跳轉
        noscript_a = soup.find('noscript')
        if noscript_a and noscript_a.find('a'):
            target_url = noscript_a.find('a')['href']
            log_chain.append(f"[SUCCESS] 提取到 Noscript 備用 A 標籤 -> {target_url[:50]}")
            return target_url, " | ".join(log_chain)

        log_chain.append(f"[FAILURE] 所有軌道均未解開。網頁源碼長度: {len(res.text)} 字元")
    except Exception as e:
        # 捕獲詳細的堆疊簡化訊息
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        log_chain.append(f"[HTTP_ERR] 網路請求流崩潰: {error_msg}")
        
    return google_url, " | ".join(log_chain)

def get_full_content_verbose(url):
    """【內文爬蟲】抓取目標網頁段落，並記錄極限除錯狀態"""
    log_chain = []
    if not url or url.startswith("javascript") or "news.google.com" in url: 
        return "無內文", "[SPIDER_SKIP] 由於前置網址未能成功解密，放棄爬取"
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9"
        }
        log_chain.append(f"[SPIDER_REQ] 嘗試訪問目標網站: {url[:40]}...")
        r = requests.get(url, timeout=5, headers=headers)
        r.encoding = r.apparent_encoding
        log_chain.append(f"[SPIDER_RESP] 狀態碼: {r.status_code}, 編認語系: {r.encoding}")
        
        if r.status_code != 200:
            return "無內文", f" | ".join(log_chain) + f" | [SPIDER_FAIL] 伺服器拒絕訪問"
            
        soup = BeautifulSoup(r.text, 'html.parser')
        # 剔除干擾節點
        for s in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'noscript', 'aside', 'form']): s.decompose()
        
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 25]
        log_chain.append(f"[DOM_PARSE] 尋找到符合長度的 <p> 標籤數量: {len(paragraphs)}")
        
        text = " ".join(paragraphs)
        if not text:
            return "無內文", " | ".join(log_chain) + " | [SPIDER_FAIL] 網頁結構無有效段落文本"
            
        # 垃圾清洗檢查
        block_keywords = ["cookie", "privacy policy", "subscribe", "yahoo finance is not", "閱讀全文"]
        if any(kw in text.lower() for kw in block_keywords) and len(text) < 350:
            return "內容已屏蔽", " | ".join(log_chain) + " | [SPIDER_WARN] 觸發垃圾文本/反爬蟲隱私條款清洗機制"
            
        return text[:1500], " | ".join(log_chain) + f" | [SPIDER_SUCCESS] 成功提取字數: {len(text)}"
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        return "無內文", " | ".join(log_chain) + f" | [SPIDER_CRASH] 異常中斷: {error_msg}"

def fetch_google_news(query, hl_cc, max_r, category_label="未分類"):
    try:
        q = urllib.parse.quote(query)
        parts = hl_cc.split('_')
        hl, gl = parts[0], parts[1]
        url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}"
        feed = feedparser.parse(url)
        arts = []
        for entry in feed.entries[:max_r]:
            raw_link = entry.link
            
            # 獲取深度解密與日誌
            real_link, url_debug_log = deep_debug_google_url(raw_link) if scrape_body else (raw_link, "未啟用解密")
            content_summary, spider_debug_log = get_full_content_verbose(real_link) if scrape_body else ("未啟用內文抓取", "未啟用爬蟲")
            
            arts.append({
                "📊 維度": category_label,
                "來源": "Google News",
                "標題": entry.title,
                "發布時間": entry.get("published", "N/A"),
                "連結": real_link,
                "摘要": entry.get("summary", ""),
                "內文摘要": content_summary,
                "🛠️ 核心解密日誌": url_debug_log,         # ✅ 全Verbose級別日誌
                "🕷️ 爬蟲深度日誌": spider_debug_log         # ✅ 全Verbose級別日誌
            })
        return arts
    except Exception as e:
        st.error(f"Google News 模組執行異常: {str(e)}")
        return []

# --- 主觸發按鈕 ---
if st.button("🚀 啟動全網大盤數據監控", type="primary"):
    with st.spinner("正在掃描台日韓股市大盤數據..."):
        all_articles = []
        api_statuses = {}
        
        # --- 1. Google News 抓取 (精準定位台日韓股市大盤與加權指數動態) ---
        macro_tw = "(台股大盤 OR 加權指數 OR 盤中速報 OR 台股買賣超 OR 三大法人)"
        macro_jp = "(日經指數 OR 日經225 OR Nikkei 225 OR 日股大盤 OR 東京股市)"  
        macro_kr = "(韓國綜合指數 OR KOSPI OR 韓股大盤 OR 首爾股市)"

        g_arts = []
        g_arts.extend(fetch_google_news(macro_tw, "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news(macro_jp, "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news(macro_kr, "ko_KR", max_results, "韓股大盤動態"))
        
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取失敗"

        # --- 2. NewsData.io 抓取 (鎖定台日韓大盤指數關鍵字) ---
        if newsdata_key:
            try:
                url = f"https://newsdata.io/api/1/latest?apikey={newsdata_key}&country=tw,jp,kr&q=stocks%20OR%20index%20OR%20market"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    nd_arts = resp.json().get("results", [])[:max_results]
                    for a in nd_arts:
                        content_summary, spider_log = get_full_content_verbose(a.get("link")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太股市行情", "來源": "NewsData.io", "標題": a.get("title"),
                            "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 核心解密日誌": "[API直接提供原始網址]", "🕷️ 爬蟲深度日誌": spider_log
                        })
                    api_statuses["NewsData.io API"] = f"🟢 OK ({len(nd_arts)} 則)"
                else:
                    api_statuses["NewsData.io API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["NewsData.io API"] = f"🔴 異常: {str(e)}"

        # --- 3. Currents API 抓取 (✅ 終極大盤對齊：支持多語系與混合大盤關鍵字) ---
        if currents_key:
            try:
                url = "https://api.currentsapi.services/v1/search"
                # 使用英文大盤專用詞，不加多餘限定，確保多國大盤新聞精準命中
                params = {
                    "apiKey": currents_key, 
                    "keywords": "TAIEX NIKKEI KOSPI stock market index",  
                    "limit": max_results
                }
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    cur_arts = resp.json().get("news", [])[:max_results]
                    for a in cur_arts:
                        content_summary, spider_log = get_full_content_verbose(a.get("url")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太股市行情", "來源": "Currents", "標題": a.get("title"),
                            "發布時間": a.get("published"), "連結": a.get("url"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 核心解密日誌": "[API直接提供原始網址]", "🕷️ 爬蟲深度日誌": spider_log
                        })
                    api_statuses["Currents API"] = f"🟢 OK ({len(cur_arts)} 則)"
                else:
                    api_statuses["Currents API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 異常: {str(e)}"

        # --- 4. Marketaux API 抓取 (大盤核心指數錨點) ---
        if marketaux_key:
            try:
                # 鎖定台股大盤指數(^TWII)、日經大盤指數(^N225)
                url = f"https://api.marketaux.com/v1/news/all?symbols=^TWII,^N225&limit={max_results}&api_token={marketaux_key}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    ma_arts = resp.json().get("data", [])
                    for a in ma_arts:
                        all_articles.append({
                            "📊 維度": "指數關鍵大盤", "來源": "Marketaux", "標題": a.get("title"),
                            "發布時間": a.get("published_at"), "連結": a.get("url"), "摘要": a.get("description"),
                            "內文摘要": a.get("snippet", ""), "🛠️ 核心解密日誌": "[API原生提供片段數據]", "🕷️ 爬蟲深度日誌": "[無需二次爬取]"
                        })
                    api_statuses["Marketaux API"] = f"🟢 OK ({len(ma_arts)} 則)"
                else:
                    api_statuses["Marketaux API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Marketaux API"] = f"🔴 異常: {str(e)}"

        # 儲存至 Session State
        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# --- 介面渲染面板 ---
if st.session_state.api_statuses:
    st.subheader("🔌 API 連線狀態檢查")
    cols = st.columns(4)
    for i, (api_name, status_text) in enumerate(st.session_state.api_statuses.items()):
        cols[i].metric(label=api_name, value=status_text)
    st.markdown("---")

if st.session_state.all_articles:
    df = pd.DataFrame(st.session_state.all_articles)
    st.success(f"✅ 當前成功展示 {len(df)} 則亞太台日韓大盤行情數據！")
    
    st.subheader("📋 亞太前瞻數據監控表（含極限偵錯日誌）")
    st.dataframe(df, width='stretch')

    # 下載按鈕（完美防頁面刷洗重置）
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.download_button("📥 下載全新偵錯全維度數據 (CSV)", csv_buffer.getvalue(), f"asia_stock_macro_verbose_v7_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
