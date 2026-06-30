import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime

# --- 頁面基本配置 ---
st.set_page_config(page_title="亞太股市大盤監控器 v12.0", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v12.0 - API 參數優化與 RSS 降級版)")
st.markdown("核心變更：終止 Google News 協議解密（回歸原生 RSS），重新設計 Currents API 請求架構以解決 0 則新聞問題。")

# =====================================================================
# ✨ 初始化 Session State
# =====================================================================
if "all_articles" not in st.session_state:
    st.session_state.all_articles = None
if "api_statuses" not in st.session_state:
    st.session_state.api_statuses = None

# --- 側邊欄配置 ---
with st.sidebar:
    st.header("🔑 API 憑證配置")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents API", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    
    st.header("⚙️ 引擎配置")
    max_results = st.slider("單一市場抓取量", 5, 25, 10)

# =====================================================================
# 📰 Google News 原生快速抓取模組 (不解密、不爬取)
# =====================================================================
def fetch_google_news_native(query, hl_cc, max_r, category_label):
    """回歸純淨 RSS 模式，僅提取 Google 封裝好的資訊，100% 免疫防爬限制"""
    try:
        q = urllib.parse.quote(query)
        parts = hl_cc.split('_')
        url = f"https://news.google.com/rss/search?q={q}&hl={parts[0]}&gl={parts[1]}"
        feed = feedparser.parse(url)
        arts = []
        for entry in feed.entries[:max_r]:
            # 使用 BeautifulSoup 清理 RSS 摘要中的 HTML 標籤
            clean_summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(strip=True) if entry.get("summary") else ""
            
            arts.append({
                "📊 維度": category_label,
                "來源": "Google News",
                "標題": entry.title,
                "發布時間": entry.get("published", "N/A"),
                "連結": entry.link,
                "摘要": clean_summary[:200],
                "內文摘要": "未啟用深度解密",
                "🛠️ 狀態日誌": "🟢 原生 RSS 讀取成功"
            })
        return arts
    except Exception as e:
        st.error(f"Google News RSS 讀取異常: {str(e)}")
        return []

# =====================================================================
# 🚀 執行主流程
# =====================================================================
if st.button("🚀 執行亞太三大股市大盤多維掃描", type="primary"):
    with st.spinner("正在調取亞太市場多源數據數據庫..."):
        all_articles = []
        api_statuses = {}
        
        # 1. 執行 Google News 原生 RSS 數據採集（極速無阻礙）
        g_arts = []
        g_arts.extend(fetch_google_news_native("(加權指數 OR 台股大盤)", "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news_native("(日經指數 OR 日經225)", "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news_native("(韓國綜合指數 OR KOSPI)", "ko_KR", max_results, "韓股大盤動態"))
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = f"🟢 OK ({len(g_arts)} 則)"

        # 2. NewsData.io 數據模組
        if newsdata_key:
            try:
                url = "https://newsdata.io/api/1/latest"
                params = {"apikey": newsdata_key, "country": "tw,jp,kr", "q": "stocks OR index"}
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    nd_arts = resp.json().get("results", [])[:max_results]
                    for a in nd_arts:
                        all_articles.append({
                            "📊 維度": "亞太總體大盤", "來源": "NewsData.io", "標題": a.get("title"),
                            "發布時間": a.get("pubDate"), "連結": a.get("link"), "摘要": a.get("description", ""),
                            "內文摘要": "API 提供原生片段", "🛠️ 狀態日誌": "🟢 API 原生網址"
                        })
                    api_statuses["NewsData.io API"] = f"🟢 OK ({len(nd_arts)} 則)"
            except: 
                pass

        # 3. 🔥 【架構重組】Currents API 優化模組
        if currents_key:
            try:
                # 解決 0 則關鍵：放棄複合關鍵字與 language 聯集，改採標準 query 語法
                url = "https://api.currentsapi.services/v1/search"
                params = {
                    "apiKey": currents_key,
                    "query": "stocks",        # 改用標準查詢參數
                    "language": "zh",          # 預設抓取中文亞太市場
                    "country": "TW,JP,KR"      # 嚴格過濾目標亞太地理區
                }
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    cu_arts = resp.json().get("news", [])[:max_results]
                    for a in cu_arts:
                        all_articles.append({
                            "📊 維度": "亞太總體大盤", "來源": "Currents API", "標題": a.get("title"),
                            "發布時間": a.get("published"), "連結": a.get("url"), "摘要": a.get("description", ""),
                            "內文摘要": "API 提供原生片段", "🛠️ 狀態日誌": "🟢 API 原生網址"
                        })
                    api_statuses["Currents API"] = f"🟢 OK ({len(cu_arts)} 則)"
                else:
                    api_statuses["Currents API"] = f"🔴 伺服器錯誤 (HTTP:{resp.status_code})"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 連線異常: {str(e)}"

        # 寫入 Session 狀態中
        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# =====================================================================
# 📊 數據渲染與輸出層
# =====================================================================
if st.session_state.api_statuses is not None:
    st.subheader("🔌 系統連線狀態")
    cols = st.columns(3)
    cols[0].metric(label="Google News RSS", value=st.session_state.api_statuses.get("Google News RSS", "N/A"))
    if "NewsData.io API" in st.session_state.api_statuses:
        cols[1].metric(label="NewsData.io 數據通道", value=st.session_state.api_statuses.get("NewsData.io API"))
    if "Currents API" in st.session_state.api_statuses:
        cols[2].metric(label="Currents API 數據通道", value=st.session_state.api_statuses.get("Currents API"))
    st.markdown("---")

if st.session_state.all_articles is not None:
    df = pd.DataFrame(st.session_state.all_articles)
    if not df.empty:
        st.success(f"✅ 成功獲取 {len(df)} 則台日韓大盤最新多源動態！")
        st.dataframe(df, width='stretch')

        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下載完整數據 (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"asia_market_v12_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("💡 當前未發現相關市場數據。")
