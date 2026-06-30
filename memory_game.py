import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime  # ✅ 修正：補上缺失的 datetime 引用

st.set_page_config(page_title="亞太宏觀與供應鏈監控器", layout="wide", page_icon="🌏")
st.title("🌏 亞太科技大盤與供應鏈新聞前瞻系統")
st.markdown("整合全球宏觀動向、亞太三大指數與半導體核心供應鏈，為美股預測提供先行指標。")

# Sidebar
with st.sidebar:
    st.header("🔑 API Keys")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents API", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    
    st.header("⚙️ 抓取配置")
    max_results = st.slider("每來源最多抓取", 5, 25, 12)
    fetch_mode = st.radio("監控維度", ["全方位（宏觀大盤 + 核心供應鏈）", "僅限宏觀大盤", "僅限個股供應鏈"])
    scrape_body = st.checkbox("深度分析（抓取新聞內文）", value=False, help="開啟後會減慢速度，但能提供完整內文供 AI 分析")

def get_full_content(url):
    """具備安全機制的內文抓取器"""
    if not url or url.startswith("javascript"): return "無效網址"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, timeout=5, headers=headers)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, 'html.parser')
        text = " ".join([p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 25])
        return text[:1500] if text else "未能提取到段落文本"
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
            link = entry.link
            arts.append({
                "📊 維度": category_label,
                "來源": "Google News",
                "標題": entry.title,
                "發布時間": entry.get("published", "N/A"),
                "連結": link,
                "摘要": entry.get("summary", ""),
                "內文摘要": get_full_content(link) if scrape_body else "未啟用深度抓取"
            })
        return arts
    except Exception as e:
        return []

# 主按鈕
if st.button("🚀 啟動全網前瞻數據監控", type="primary"):
    with st.spinner("正在掃描亞太宏觀大盤與供應鏈數據..."):
        all_articles = []
        
        # --- 定義多維度監控關鍵字 ---
        macro_tw = "外資 OR 加權指數 OR 央行 OR 新台幣"
        macro_jp = "日經225 OR 日元 OR 日銀 OR 利差交易"  
        macro_kr = "韓國綜合指數 OR 央行 OR 韓元"
        
        industry_tw = "半導體 OR 先進封裝 OR 矽晶圓 OR 電子代工"
        industry_jp = "半導體材料 OR 東京威力科創 OR 光阻劑"
        industry_kr = "記憶體現貨價 OR HBM OR 晶圓代工"

        # --- 依據模式執行抓取 ---
        if "宏觀大盤" in fetch_mode or "全方位" in fetch_mode:
            all_articles.extend(fetch_google_news(macro_tw, "zh-TW_TW", max_results, "亞太宏觀市場"))
            all_articles.extend(fetch_google_news(macro_jp, "ja_JP", max_results, "亞太宏觀市場"))
            all_articles.extend(fetch_google_news(macro_kr, "ko_KR", max_results, "亞太宏觀市場"))
            
        if "供應鏈" in fetch_mode or "全方位" in fetch_mode:
            all_articles.extend(fetch_google_news(industry_tw, "zh-TW_TW", max_results, "產業核心供應鏈"))
            all_articles.extend(fetch_google_news(industry_jp, "ja_JP", max_results, "產業核心供應鏈"))
            all_articles.extend(fetch_google_news(industry_kr, "ko_KR", max_results, "產業核心供應鏈"))

        # --- 整合其餘專業 API ---
        if newsdata_key and ("供應鏈" in fetch_mode or "全方位" in fetch_mode):
            try:
                url = f"https://newsdata.io/api/1/latest?apikey={newsdata_key}&country=tw&category=technology,business"
                resp = requests.get(url, timeout=8).json()
                for a in resp.get("results", [])[:max_results]:
                    all_articles.append({
                        "📊 維度": "產業核心供應鏈", "來源": "NewsData.io", "標題": a.get("title"),
                        "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                        "內文摘要": get_full_content(a.get("link")) if scrape_body else "未啟用深度抓取"
                    })
            except: pass

        if marketaux_key and ("供應鏈" in fetch_mode or "全方位" in fetch_mode):
            try:
                url = f"https://api.marketaux.com/v1/news/all?symbols=2330.TW,005930.KS&limit={max_results}&api_token={marketaux_key}"
                resp = requests.get(url, timeout=8).json()
                for a in resp.get("data", []):
                    all_articles.append({
                        "📊 維度": "個股關鍵錨點", "來源": "Marketaux", "標題": a.get("title"),
                        "發布時間": a.get("published_at"), "連結": a.get("url"), "摘要": a.get("description"),
                        "內文摘要": get_full_content(a.get("url")) if scrape_body else "未啟用深度抓取"
                    })
            except: pass

        # --- 數據渲染 ---
        if all_articles:
            df = pd.DataFrame(all_articles)
            
            st.success(f"✅ 成功整合 {len(all_articles)} 則亞太前瞻多維度新聞！")
            
            # 分流顯示
            tab1, tab2 = st.tabs(["📋 所有監控數據數據表", "🔍 分類多維度檢視"])
            with tab1:
                # ✅ 修正：將已廢棄的 use_container_width=True 替換為新版語法 width='stretch'
                st.dataframe(df, width='stretch')
            with tab2:
                categories = df["📊 維度"].unique()
                for cat in categories:
                    with st.expander(f"📌 {cat} ({len(df[df['📊 維度']==cat])} 則)"):
                        st.table(df[df["📊 維度"] == cat][["來源", "標題", "發布時間"]].head(10))

            # 下載模組
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            st.download_button("📥 下載全維度前瞻數據 (CSV)", csv_buffer.getvalue(), f"asia_macro_tech_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        else:
            st.error("未能獲取數據，請確認網絡或 API Key 有效性。")
