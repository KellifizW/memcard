import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import base64
import re
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime

st.set_page_config(page_title="亞太股市大盤監控器 v6.0", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v6.0 - 偵錯強固版)")
st.markdown("已修正：Currents 國際指數大盤配置、所有渠道鎖定台日韓大盤、CSV 內建「爬蟲偵測日誌」欄位。")

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

def force_decode_google_url(google_url):
    """【解密追蹤】嘗試解析 Google 加密網址，並返回 (解析後網址, 階段Log)"""
    logs = []
    if "news.google.com" not in google_url:
        return google_url, "[URL] 已經是原始媒體網址"
    
    # 階段 1：嘗試本地 Base64 演算法
    try:
        match = re.search(r"articles/([a-zA-Z0-9_=-]+)", google_url)
        if match:
            b64_str = match.group(1).replace('-', '+').replace('_', '/')
            b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
            decoded_text = base64.b64decode(b64_str).decode('utf-8', errors='ignore')
            urls = re.findall(r'https?://[^\s"\u0000-\u001f]+', decoded_text)
            if urls:
                clean_url = urls[0].split('')[0].split('\x01')[0].split('\x02')[0]
                if "news.google.com" not in clean_url and len(clean_url) > 12:
                    return clean_url, "[解密成功] 經由本地演算法還原網址"
    except Exception as e:
        logs.append(f"Base64異常: {str(e)}")

    # 階段 2：發送 Session 網路請求追蹤 Rerun 重定向
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9"
        }
        res = session.get(google_url, headers=headers, timeout=4, allow_redirects=True)
        if res.url and "news.google.com" not in res.url:
            return res.url, f"[解密成功] 經由網路流追蹤到最終跳轉網址. 狀態碼: {res.status_code}"
        
        # 階段 3：檢查源碼中是否有 Meta Refresh
        soup = BeautifulSoup(res.text, 'html.parser')
        meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
        if meta_refresh:
            refresh_url = re.search(r"url=(http.*)", meta_refresh['content'], re.IGNORECASE)
            if refresh_url:
                return refresh_url.group(1), "[解密成功] 提取到 Meta Refresh 跳轉鏈接"
        
        return google_url, f"[解密失敗] 網路流未能擊穿 Google 加密層. 最終留在: {res.url}"
    except Exception as e:
        logs.append(f"網路流異常: {str(e)}")
        
    return google_url, f"[解密失敗] 錯誤日誌: {'; '.join(logs)}"

def get_full_content(url):
    """【內文爬蟲】抓取目標網頁段落，並返回 (內文, 爬蟲狀態Log)"""
    if not url or url.startswith("javascript") or "news.google.com" in url: 
        return "無內文", "[爬蟲跳過] 因網址未成功還原，放棄訪問目標網站"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9"
        }
        r = requests.get(url, timeout=5, headers=headers)
        r.encoding = r.apparent_encoding
        
        if r.status_code != 200:
            return "無內文", f"[爬蟲攔截] 目標網站返回非200狀態碼: {r.status_code}"
            
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'noscript', 'aside']): s.decompose()
        
        text = " ".join([p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 25])
        
        if not text:
            return "無內文", "[爬蟲失敗] 成功載入網頁，但未匹配到任何有效的 <p> 標籤段落內容"
            
        # 阻擋爬蟲洗網頁檢查
        block_keywords = ["cookie", "privacy policy", "subscribe", "yahoo finance is not", "閱讀全文"]
        if any(kw in text.lower() for kw in block_keywords) and len(text) < 350:
            return "內容已屏蔽", "[爬蟲警告] 成功抓取，但內容多為隱私政策或阻擋爬蟲提示"
            
        return text[:1500], f"[爬蟲成功] 成功提取文本，長度 {len(text)} 字"
    except Exception as e:
        return "無內文", f"[爬蟲崩潰] 無法訪問網站，錯誤原因: {str(e)}"

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
            
            # 獲取還原結果與日誌
            real_link, url_log = force_decode_google_url(raw_link) if scrape_body else (raw_link, "未啟用解密")
            content_summary, spider_log = get_full_content(real_link) if scrape_body else ("未啟用內文抓取", "未啟用爬蟲")
            
            arts.append({
                "📊 維度": category_label,
                "來源": "Google News",
                "標題": entry.title,
                "發布時間": entry.get("published", "N/A"),
                "連結": real_link,
                "摘要": entry.get("summary", ""),
                "內文摘要": content_summary,
                "🛠️ 爬蟲偵測日誌": f"{url_log} -> {spider_log}"  # ✅ 新增 Log 欄位
            })
        return arts
    except Exception as e:
        st.error(f"Google News 模組錯誤: {str(e)}")
        return []

# --- 主觸發按鈕 ---
if st.button("🚀 啟動全網大盤數據監控", type="primary"):
    with st.spinner("正在掃描台日韓股市大盤數據..."):
        all_articles = []
        api_statuses = {}
        
        # --- 1. Google News 抓取 (全面鎖定台日韓股市大盤與指數動態) ---
        macro_tw = "(台股大盤 OR 加權指數 OR 盤中速報 OR 台股買賣超)"
        macro_jp = "(日經指數 OR 日經225 OR Nikkei 225 OR 日股大盤)"  
        macro_kr = "(韓國綜合指數 OR KOSPI OR 韓股大盤)"

        g_arts = []
        g_arts.extend(fetch_google_news(macro_tw, "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news(macro_jp, "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news(macro_kr, "ko_KR", max_results, "韓股大盤動態"))
        
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取失敗"

        # --- 2. NewsData.io 抓取 (鎖定台日韓區域，大盤關鍵字) ---
        if newsdata_key:
            try:
                # 聚焦大盤指數與股市行情
                url = f"https://newsdata.io/api/1/latest?apikey={newsdata_key}&country=tw,jp,kr&q=stocks%20OR%20index%20OR%20market"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    nd_arts = resp.json().get("results", [])[:max_results]
                    for a in nd_arts:
                        content_summary, spider_log = get_full_content(a.get("link")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太股市行情", "來源": "NewsData.io", "標題": a.get("title"),
                            "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 爬蟲偵測日誌": f"[API直接網址] -> {spider_log}"
                        })
                    api_statuses["NewsData.io API"] = f"🟢 OK ({len(nd_arts)} 則)"
                else:
                    api_statuses["NewsData.io API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["NewsData.io API"] = f"🔴 異常: {str(e)}"

        # --- 3. Currents API 抓取 (✅ 完美修復：改用大盤指數專業詞彙，避開 AND 交集歸零) ---
        if currents_key:
            try:
                url = "https://api.currentsapi.services/v1/search"
                # 改用 TAIEX(台股), NIKKEI(日股), KOSPI(韓股)，這是國際大盤數據庫最穩定的調用詞
                params = {
                    "apiKey": currents_key, 
                    "keywords": "TAIEX NIKKEI KOSPI",  
                    "language": "en", # 國際財經多以英文收錄此類大盤
                    "limit": max_results
                }
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    cur_arts = resp.json().get("news", [])[:max_results]
                    for a in cur_arts:
                        content_summary, spider_log = get_full_content(a.get("url")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太股市行情", "來源": "Currents", "標題": a.get("title"),
                            "發布時間": a.get("published"), "連結": a.get("url"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 爬蟲偵測日誌": f"[API直接網址] -> {spider_log}"
                        })
                    api_statuses["Currents API"] = f"🟢 OK ({len(cur_arts)} 則)"
                else:
                    api_statuses["Currents API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 異常: {str(e)}"

        # --- 4. Marketaux API 抓取 (鎖定大盤指數代碼) ---
        if marketaux_key:
            try:
                # 改抓台股加權指數(^TWII)、日經指數(^N225)大盤錨點
                url = f"https://api.marketaux.com/v1/news/all?symbols=^TWII,^N225&limit={max_results}&api_token={marketaux_key}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    ma_arts = resp.json().get("data", [])
                    for a in ma_arts:
                        all_articles.append({
                            "📊 維度": "指數關鍵大盤", "來源": "Marketaux", "標題": a.get("title"),
                            "發布時間": a.get("published_at"), "連結": a.get("url"), "摘要": a.get("description"),
                            "內文摘要": a.get("snippet", ""), "🛠️ 爬蟲偵測日誌": "[API直接內文片段]"
                        })
                    api_statuses["Marketaux API"] = f"🟢 OK ({len(ma_arts)} 則)"
                else:
                    api_statuses["Marketaux API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Marketaux API"] = f"🔴 異常: {str(e)}"

        # 寫入狀態
        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# --- 介面渲染邏輯 (不論是否重置都保持原樣) ---
if st.session_state.api_statuses:
    st.subheader("🔌 API 連線狀態檢查")
    cols = st.columns(4)
    for i, (api_name, status_text) in enumerate(st.session_state.api_statuses.items()):
        cols[i].metric(label=api_name, value=status_text)
    st.markdown("---")

if st.session_state.all_articles:
    df = pd.DataFrame(st.session_state.all_articles)
    st.success(f"✅ 當前展示 {len(df)} 則亞太台日韓大盤動態新聞！")
    
    st.subheader("📋 所有監控數據（含爬蟲偵錯日誌）")
    st.dataframe(df, width='stretch')

    # 下載按鈕（完美防重置）
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.download_button("📥 下載全新全維度數據 (CSV)", csv_buffer.getvalue(), f"asia_stock_macro_v6_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
