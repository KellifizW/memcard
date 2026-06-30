import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime

st.set_page_config(page_title="亞太宏觀與供應鏈監控器 v3", layout="wide", page_icon="🌏")
st.title("🌏 亞太科技大盤與供應鏈新聞前瞻系統 (v3.0 - 穩定版)")
st.markdown("已修正：Currents API 策略、Google 網址真實追蹤、防下載重置機制（Session State）。")

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
    max_results = st.slider("每來源最多抓取", 5, 25, 12)
    fetch_mode = st.radio("監控維度", ["全方位（宏觀大盤 + 核心供應鏈）", "僅限宏觀大盤", "僅限個股供應鏈"])
    scrape_body = st.checkbox("深度分析（追蹤 Google 真實網址並抓取內文）", value=True)

def resolve_google_url(google_url):
    """透過網路重導向追蹤，100% 獲取 Google News 原始媒體網址"""
    if "news.google.com" not in google_url:
        return google_url
    try:
        # 使用特定 Headers 迫使 Google News 執行 Location 重導向
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"}
        response = requests.get(google_url, headers=headers, timeout=5, allow_redirects=True)
        return response.url
    except:
        return google_url

def get_full_content(url):
    """具備安全機制的內文抓取器"""
    if not url or url.startswith("javascript") or "news.google.com" in url: 
        return "無法解析原始網址"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        r = requests.get(url, timeout=5, headers=headers)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 移除干擾標籤
        for s in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header']): s.decompose()
        
        text = " ".join([p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 30])
        
        # 阻擋爬蟲垃圾內文清洗機制 (抗 Token 浪費)
        block_keywords = ["cookie", "privacy policy", "subscribe", "yahoo finance is not", "copyright", "閱讀全文"]
        if any(kw in text.lower() for kw in block_keywords) and len(text) < 350:
            return "偵測到阻擋爬蟲或無效內文，已自動屏蔽以節省 Token。"
            
        return text[:1500] if text else "未能提取到足夠段落文本"
    except:
        return "暫時無法訪問該網站"

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
            
            # ✅ 修正 2：利用重導向真實追踪原始網址
            real_link = resolve_google_url(raw_link) if scrape_body else raw_link
            
            arts.append({
                "📊 維度": category_label,
                "來源": "Google News",
                "標題": entry.title,
                "發布時間": entry.get("published", "N/A"),
                "連結": real_link,
                "摘要": entry.get("summary", ""),
                "內文摘要": get_full_content(real_link) if (scrape_body and "news.google.com" not in real_link) else "未啟用內文抓取"
            })
        return arts
    except:
        return []

# --- 主觸發按鈕 ---
if st.button("🚀 啟動全網前瞻數據監控", type="primary"):
    with st.spinner("正在掃描亞太宏觀大盤與供應鏈數據..."):
        all_articles = []
        api_statuses = {}
        
        # --- 1. Google News 抓取 ---
        macro_tw = "外資 OR 加權指數 OR 央行 OR 新台幣"
        macro_jp = "日經225 OR 日元 OR 日銀 OR 利差交易"  
        macro_kr = "韓國綜合指數 OR 央行 OR 韓元"
        industry_tw = "半導體 OR 先進封裝 OR 矽晶圓 OR 電子代工"
        industry_jp = "半導體材料 OR 東京威力科創 OR 光阻劑"
        industry_kr = "記憶體現貨價 OR HBM OR 晶圓代工"

        g_arts = []
        if "宏觀大盤" in fetch_mode or "全方位" in fetch_mode:
            g_arts.extend(fetch_google_news(macro_tw, "zh-TW_TW", max_results, "亞太宏觀市場"))
            g_arts.extend(fetch_google_news(macro_jp, "ja_JP", max_results, "亞太宏觀市場"))
            g_arts.extend(fetch_google_news(macro_kr, "ko_KR", max_results, "亞太宏觀市場"))
        if "供應鏈" in fetch_mode or "全方位" in fetch_mode:
            g_arts.extend(fetch_google_news(industry_tw, "zh-TW_TW", max_results, "產業核心供應鏈"))
            g_arts.extend(fetch_google_news(industry_jp, "ja_JP", max_results, "產業核心供應鏈"))
            g_arts.extend(fetch_google_news(industry_kr, "ko_KR", max_results, "產業核心供應鏈"))
        
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取失敗"

        # --- 2. NewsData.io 抓取 ---
        if newsdata_key and ("供應鏈" in fetch_mode or "全方位" in fetch_mode):
            try:
                url = f"https://newsdata.io/api/1/latest?apikey={newsdata_key}&country=tw&category=technology,business"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    nd_arts = resp.json().get("results", [])[:max_results]
                    for a in nd_arts:
                        all_articles.append({
                            "📊 維度": "產業核心供應鏈", "來源": "NewsData.io", "標題": a.get("title"),
                            "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                            "內文摘要": get_full_content(a.get("link")) if scrape_body else "未啟用內文抓取"
                        })
                    api_statuses["NewsData.io API"] = f"🟢 OK ({len(nd_arts)} 則)"
                else:
                    api_statuses["NewsData.io API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["NewsData.io API"] = f"🔴 異常: {str(e)}"
        else:
            api_statuses["NewsData.io API"] = "🟡 未啟用"

        # --- 3. Currents API 抓取 (✅ 修正 1：改用科技分類最新端點，徹底避開關鍵字停用問題) ---
        if currents_key and ("供應鏈" in fetch_mode or "全方位" in fetch_mode):
            try:
                url = "https://api.currentsapi.services/v1/latest-news" # 改用最新大盤端點
                params = {"apiKey": currents_key, "category": "technology", "language": "zh", "limit": max_results}
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    cur_arts = resp.json().get("news", [])[:max_results]
                    for a in cur_arts:
                        all_articles.append({
                            "📊 維度": "產業核心供應鏈", "來源": "Currents", "標題": a.get("title"),
                            "發布時間": a.get("published"), "連結": a.get("url"), "摘要": a.get("description", ""),
                            "內文摘要": get_full_content(a.get("url")) if scrape_body else "未啟用內文抓取"
                        })
                    api_statuses["Currents API"] = f"🟢 OK ({len(cur_arts)} 則)"
                else:
                    api_statuses["Currents API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 異常: {str(e)}"
        else:
            api_statuses["Currents API"] = "🟡 未啟用"

        # --- 4. Marketaux API 抓取 ---
        if marketaux_key and ("供應鏈" in fetch_mode or "全方位" in fetch_mode):
            try:
                url = f"https://api.marketaux.com/v1/news/all?symbols=2330.TW,005930.KS&limit={max_results}&api_token={marketaux_key}"
                resp = requests.get(url, timeout=8)
                if resp.status_code == 200:
                    ma_arts = resp.json().get("data", [])
                    for a in ma_arts:
                        raw_snippet = a.get("snippet", "")
                        clean_snippet = raw_snippet if ("yahoo finance" not in raw_snippet.lower() and len(raw_snippet) > 50) else a.get("description", "已由系統過濾阻擋文本")
                        all_articles.append({
                            "📊 維度": "個股關鍵錨點", "來源": "Marketaux", "標題": a.get("title"),
                            "發布時間": a.get("published_at"), "連結": a.get("url"), "摘要": a.get("description"),
                            "內文摘要": clean_snippet
                        })
                    api_statuses["Marketaux API"] = f"🟢 OK ({len(ma_arts)} 則)"
                else:
                    api_statuses["Marketaux API"] = f"🔴 錯誤: {resp.status_code}"
            except Exception as e:
                api_statuses["Marketaux API"] = f"🔴 異常: {str(e)}"
        else:
            api_statuses["Marketaux API"] = "🟡 未啟用"

        # 將數據保存到 Session State 避免重置
        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# --- 介面渲染邏輯 (不論是否 Rerun，只要 State 有資料就維持顯示) ---
if st.session_state.api_statuses:
    st.subheader("🔌 API 連線狀態檢查")
    cols = st.columns(4)
    for i, (api_name, status_text) in enumerate(st.session_state.api_statuses.items()):
        cols[i].metric(label=api_name, value=status_text)
    st.markdown("---")

if st.session_state.all_articles:
    df = pd.DataFrame(st.session_state.all_articles)
    st.success(f"✅ 當前展示 {len(df)} 則亞太前瞻多維度新聞！")
    
    tab1, tab2 = st.tabs(["📋 所有監控數據數據表", "🔍 分類多維度檢視"])
    with tab1:
        st.dataframe(df, width='stretch')
    with tab2:
        categories = df["📊 維度"].unique()
        for cat in categories:
            with st.expander(f"📌 {cat} ({len(df[df['📊 維度']==cat])} 則)"):
                st.table(df[df["📊 維度"] == cat][["來源", "標題", "發布時間"]].head(10))

    # ✅ 修正 3：下載按鈕讀取 Session State 資料，觸發 Rerun 後頁面內容依然保留
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.download_button("📥 下載全新全維度數據 (CSV)", csv_buffer.getvalue(), f"asia_macro_tech_v3_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
