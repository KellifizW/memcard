import streamlit as st
import feedparser
import urllib.parse
import requests
import json
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="亞太科技新聞抓取器", layout="wide")
st.title("🌏 亞太供應鏈新聞監控工具（美股前瞻）")
st.markdown("支援台、日、韓半導體新聞，適合 OpenClaw 等 AI 情緒分析系統")

# Sidebar 配置
with st.sidebar:
    st.header("API Keys")
    newsdata_key = st.text_input("NewsData.io Key", value="pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents Key", value="zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux Key", value="otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    
    st.header("抓取設定")
    max_results = st.slider("每來源最大抓取數", 5, 20, 10)
    keywords_input = st.text_input("過濾關鍵字（逗號分隔）", "TSMC,台積電,三星,Samsung,半導體,HBM")
    KEYWORDS = [k.strip() for k in keywords_input.split(",")]

# ====================== 函數（與之前優化版相同） ======================
def fetch_google_news(region_keyword, hl_cc="zh-TW_TW", max_r=10):
    try:
        query = urllib.parse.quote(region_keyword)
        parts = hl_cc.split('_')
        hl = parts[0]
        gl = parts[1] if len(parts) > 1 else hl.split('-')[0].upper()
        url = f"https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={hl}:{gl}"
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_r]:
            articles.append({
                "source": "Google News",
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", "N/A"),
                "summary": entry.get("summary", "")
            })
        return articles
    except:
        return []

def fetch_newsdata(key, country="tw", q="台積電", max_r=10):
    if not key: return []
    try:
        url = f"https://newsdata.io/api/1/latest?apikey={key}&country={country}&q={urllib.parse.quote(q)}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        results = data.get("results", [])[:max_r]
        for r in results: r["source"] = "NewsData.io"
        return results
    except:
        return []

# ... (Currents & Marketaux 函數類似，可自行補齊或我再提供)

def keyword_filter(articles, kws):
    filtered = []
    for art in articles:
        text = " ".join(str(v) for v in art.values() if isinstance(v, str))
        if any(kw.lower() in text.lower() for kw in kws):
            filtered.append(art)
    return filtered

# 主介面
col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 開始抓取新聞", type="primary"):
        with st.spinner("正在抓取台日韓科技新聞..."):
            # Google
            g1 = fetch_google_news("半導體 OR 台積電", "zh-TW_TW", max_results)
            g2 = fetch_google_news("半導体 OR 東京エレクトロン", "ja_JP", max_results)
            g3 = fetch_google_news("반도체 OR 삼성", "ko_KR", max_results)
            
            # 其他 API (填 Key 後啟用)
            nd = fetch_newsdata(newsdata_key, "tw", "台積電 OR 半導體", max_results)
            # cur = fetch_currents...
            # ma = fetch_marketaux...
            
            all_articles = g1 + g2 + g3 + nd  # + cur + ma
            filtered = keyword_filter(all_articles, KEYWORDS)
            
            st.success(f"總抓取 {len(all_articles)} 則 | 命中 {len(filtered)} 則")
            
            # 顯示表格
            if filtered:
                df = pd.DataFrame(filtered)
                st.dataframe(df[["source", "title", "published", "link"]], use_container_width=True)
                
                # 下載
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 下載 CSV", csv, "asia_news.csv", "text/csv")
                
                json_str = json.dumps(filtered, ensure_ascii=False, indent=2)
                st.download_button("📥 下載 JSON", json_str, "asia_news.json", "application/json")
            else:
                st.warning("本次無強烈命中關鍵字新聞")

st.caption("由 Grok 無限制模式打造 | 適合串接 AI 情緒分析")
