import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import re
import json
import traceback
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime

st.set_page_config(page_title="亞太股市大盤監控器 v9.0", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v9.0 - RPC 逆向解密版)")
st.markdown("已實裝：Google News `batchexecute` RPC 物理擊穿、Currents 獨立查詢池、確保輸出乾淨文本。")

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
    max_results = st.slider("單一市場抓取量", 5, 25, 10)
    scrape_body = st.checkbox("深度內文追蹤與分析", value=True)

def deep_protocol_decode(google_url):
    """【黑科技 RPC 解密】逆向 Google News 前端 API 獲取真實網址"""
    log_chain = []
    log_chain.append("[INIT] 接收 RSS 網址")
    
    if "news.google.com" not in google_url:
        return google_url, "[SKIP] 已是原始網址"
        
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
        }
        # 1. 獲取中繼跳轉頁
        res = session.get(google_url, headers=headers, timeout=6)
        log_chain.append(f"[GET] 中繼頁面 (碼:{res.status_code})")
        
        # 2. 擷取 data-p 參數
        match = re.search(r'data-p="(%.@.[^"]+)"', res.text)
        if not match:
            soup = BeautifulSoup(res.text, 'html.parser')
            cwiz = soup.select_one('c-wiz[data-p]')
            if cwiz:
                data_p = cwiz.get('data-p')
            else:
                log_chain.append("[FAIL] 無法提取 data-p (可能為 CAPTCHA 阻擋)")
                return google_url, " | ".join(log_chain)
        else:
            data_p = match.group(1)
            
        log_chain.append("[PARSE] 提取 data-p 成功")
            
        # 3. 封裝 batchexecute RPC Payload
        json_str = data_p.replace('%.@.', '["garturlreq",')
        obj = json.loads(json_str)
        req_arr = obj[:-6] + obj[-2:]
        req_str = json.dumps(req_arr, separators=(',', ':'))
        f_req = json.dumps([[["Fbv4je", req_str, "null", "generic"]]], separators=(',', ':'))
        
        post_url = 'https://news.google.com/_/DotsSplashUi/data/batchexecute'
        post_headers = headers.copy()
        post_headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        
        log_chain.append("[RPC] 發送 Fbv4je 請求...")
        post_res = session.post(post_url, data={'f.req': f_req}, headers=post_headers, timeout=6)
        
        # 4. 解析 RPC 響應
        resp_text = post_res.text.replace(")]}'\n", "").strip()
        resp_arr = json.loads(resp_text)
        real_url = json.loads(resp_arr[0][2])[1]
        
        log_chain.append(f"[SUCCESS] RPC 擊穿 -> {real_url[:35]}...")
        return real_url, " | ".join(log_chain)
        
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        log_chain.append(f"[CRASH] RPC 解密崩潰: {error_msg}")
        return google_url, " | ".join(log_chain)

def get_full_content_verbose(url):
    """【目標媒體爬蟲】訪問最終新聞網站，提取乾淨文本"""
    log_chain = []
    if not url or "news.google.com" in url: 
        return "無內文", "[SPIDER_SKIP] 網址解密失敗，放棄爬取"
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        }
        r = requests.get(url, timeout=6, headers=headers)
        r.encoding = r.apparent_encoding
        
        if r.status_code != 200:
            return "無內文", f"[FAIL] 網站拒絕請求 ({r.status_code})"
            
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'noscript', 'form']): s.decompose()
        
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 25]
        text = " ".join(paragraphs)
        
        if not text:
            return "無內文", "[FAIL] 未匹配到標準段落"
            
        block_keywords = ["cookie", "privacy policy", "subscribe", "閱讀全文", "版權所有"]
        if any(kw in text.lower() for kw in block_keywords) and len(text) < 350:
            return "內容已屏蔽", "[WARN] 觸發反爬蟲或訂閱牆"
            
        return text[:1500], f"[SUCCESS] 成功導出 {len(text)} 字"
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        return "無內文", f"[CRASH] 錯誤: {error_msg}"

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
                "🛠️ 解密日誌": url_log,
                "🕷️ 爬蟲日誌": spider_log
            })
        return arts
    except Exception as e:
        st.error(f"Google News 模組異常: {str(e)}")
        return []

# --- 主執行流程 ---
if st.button("🚀 執行亞太三大股市大盤多維掃描", type="primary"):
    with st.spinner("正透過 RPC 通道向台、日、韓大盤數據庫發送調用..."):
        all_articles = []
        api_statuses = {}
        
        # 1. Google News (鎖定中日韓大盤動態)
        g_arts = []
        g_arts.extend(fetch_google_news("(加權指數 OR 台股大盤 OR 台股買賣超)", "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news("(日經指數 OR 日經225 OR 東京股市)", "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news("(韓國綜合指數 OR KOSPI OR 韓國股市)", "ko_KR", max_results, "韓股大盤動態"))
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取空值"

        # 2. NewsData.io (安全 params 傳遞)
        if newsdata_key:
            try:
                url = "https://newsdata.io/api/1/latest"
                params = {
                    "apikey": newsdata_key,
                    "country": "tw,jp,kr",
                    "q": "stocks OR index OR market OR 加權指數 OR 日經"
                }
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    nd_arts = resp.json().get("results", [])[:max_results]
                    for a in nd_arts:
                        content_summary, spider_log = get_full_content_verbose(a.get("link")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太總體大盤", "來源": "NewsData.io", "標題": a.get("title"),
                            "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 解密日誌": "[API原生網址]", "🕷️ 爬蟲日誌": spider_log
                        })
                    api_statuses["NewsData.io API"] = f"🟢 OK ({len(nd_arts)} 則)"
                else:
                    api_statuses["NewsData.io API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["NewsData.io API"] = f"🔴 異常: {str(e)}"

        # 3. Currents API (獨立查詢池 + 語系對齊)
        if currents_key:
            try:
                # 拆分為獨立關鍵字，避免 AND 交集，並確保台日韓均有產出
                target_queries = ["台股", "日經", "KOSPI"]
                currents_pool = []
                url = "https://api.currentsapi.services/v1/search"
                
                for q_term in target_queries:
                    params = {
                        "apiKey": currents_key, 
                        "keywords": q_term, 
                        "language": "zh", # 確保抓取中文報導的亞洲股市
                        "limit": 5
                    }
                    resp = requests.get(url, params=params, timeout=6)
                    if resp.status_code == 200:
                        currents_pool.extend(resp.json().get("news", []))
                
                # 去重
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
                        "內文摘要": content_summary, "🛠️ 解密日誌": "[API多軌查詢池]", "🕷️ 爬蟲日誌": spider_log
                    })
                api_statuses["Currents API"] = f"🟢 OK ({len(final_currents)} 則)"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 查詢池異常: {str(e)}"

        # 4. Marketaux API (大盤精準錨點)
        if marketaux_key:
            try:
                url = f"https://api.marketaux.com/v1/news/all?symbols=^TWII,^N225,^KS11&limit={max_results}&api_token={marketaux_key}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    ma_arts = resp.json().get("data", [])
                    for a in ma_arts:
                        all_articles.append({
                            "📊 維度": "指數宏觀行情", "來源": "Marketaux", "標題": a.get("title"),
                            "發布時間": a.get("published_at"), "連結": a.get("url"), "摘要": a.get("description"),
                            "內文摘要": a.get("snippet", ""), "🛠️ 解密日誌": "[API原生數據]", "🕷️ 爬蟲日誌": "[無需爬取]"
                        })
                    api_statuses["Marketaux API"] = f"🟢 OK ({len(ma_arts)} 則)"
                else:
                    api_statuses["Marketaux API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Marketaux API"] = f"🔴 異常: {str(e)}"

        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# --- 介面渲染 ---
if st.session_state.api_statuses:
    st.subheader("🔌 系統連線狀態")
    cols = st.columns(4)
    for i, (api_name, status_text) in enumerate(st.session_state.api_statuses.items()):
        cols[i].metric(label=api_name, value=status_text)
    st.markdown("---")

if st.session_state.all_articles:
    df = pd.DataFrame(st.session_state.all_articles)
    st.success(f"✅ 成功獲取 {len(df)} 則台日韓大盤動態！")
    
    st.subheader("📋 大盤前瞻監控數據 (含解密日誌)")
    st.dataframe(df, width='stretch')

    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.download_button("📥 下載完整數據 (CSV)", csv_buffer.getvalue(), f"asia_market_rpc_v9_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
