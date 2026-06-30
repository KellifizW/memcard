import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import json
from datetime import datetime
from bs4 import BeautifulSoup

st.set_page_config(page_title="亞太新聞抓取器", layout="wide", page_icon="🌏")
st.title("🌏 亞太供應鏈新聞監控器（全 API 版）")
st.markdown("**Google News + NewsData.io + Currents + Marketaux** | 支援內文抓取")

# Sidebar
with st.sidebar:
    st.header("🔑 API Keys")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents API", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    
    st.header("⚙️ 設定")
    max_results = st.slider("每來源最大數量", 5, 20, 10)
    kw_input = st.text_input("過濾關鍵字（逗號分隔）", "TSMC,台積電,半導體,三星,Samsung,HBM,CoWoS")
    KEYWORDS = [k.strip() for k in kw_input.split(",") if k.strip()]

def get_full_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 30]
        return " ".join(paragraphs[:12])[:2000]
    except:
        return "無法抓取完整內文（網站限制或付費牆）"

def fetch_google_news(query, hl_cc, max_r):
    try:
        q = urllib.parse.quote(query)
        parts = hl_cc.split('_')
        hl = parts[0]
        gl = parts[1] if len(parts) > 1 else hl.split('-')[0].upper()
        url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}"
        feed = feedparser.parse(url)
        arts = []
        for entry in feed.entries[:max_r]:
            arts.append({
                "source": "Google News",
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", "N/A"),
                "summary": entry.get("summary", ""),
                "full_content": get_full_content(entry.link)
            })
        return arts
    except:
        return []

def fetch_newsdata(key, q, country="tw", max_r=10):
    if not key: return []
    try:
        url = f"https://newsdata.io/api/1/latest?apikey={key}&country={country}&q={urllib.parse.quote(q)}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        arts = data.get("results", [])[:max_r]
        for a in arts:
            a["source"] = "NewsData.io"
            a["full_content"] = get_full_content(a.get("link", ""))
        return arts
    except:
        return [{"source": "NewsData.io", "title": "API 錯誤或額度已滿"}]

def fetch_currents(key, keywords, language="zh", max_r=10):
    if not key: return []
    try:
        url = "https://api.currentsapi.services/v1/search"
        params = {"apiKey": key, "keywords": keywords, "language": language, "limit": max_r}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        arts = data.get("news", [])[:max_r]
        for a in arts:
            a["source"] = "Currents"
            a["full_content"] = get_full_content(a.get("url", a.get("link", "")))
        return arts
    except:
        return [{"source": "Currents", "title": "API 錯誤"}]

def fetch_marketaux(key, ticker="2330.TW", max_r=10):
    if not key: return []
    try:
        url = f"https://api.marketaux.com/v1/news/all?symbols={ticker}&limit={max_r}&api_token={key}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        arts = data.get("data", [])[:max_r]
        for a in arts:
            a["source"] = "Marketaux"
            a["full_content"] = get_full_content(a.get("url", ""))
        return arts
    except:
        return [{"source": "Marketaux", "title": "API 錯誤或額度已滿"}]

# 主邏輯
if st.button("🚀 抓取所有來源新聞", type="primary"):
    with st.spinner("抓取 Google + NewsData + Currents + Marketaux 中..."):
        all_articles = []

        # Google
        all_articles.extend(fetch_google_news("半導體 OR 台積電", "zh-TW_TW", max_results))
        all_articles.extend(fetch_google_news("半導体 OR 東京エレクトロン", "ja_JP", max_results))
        all_articles.extend(fetch_google_news("반도체 OR 삼성", "ko_KR", max_results))

        # 其他 API
        all_articles.extend(fetch_newsdata(newsdata_key, "台積電 OR 半導體", "tw", max_results))
        all_articles.extend(fetch_currents(currents_key, "台積電 OR 半導體", "zh", max_results))
        all_articles.extend(fetch_marketaux(marketaux_key, "2330.TW", max_results))

        # 過濾
        filtered = [a for a in all_articles if any(k.lower() in str(a).lower() for k in KEYWORDS)]

        df = pd.DataFrame(all_articles)
        if not df.empty:
            display_cols = [c for c in ["source", "title", "published", "link", "summary"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)

            # 下載
            csv_data = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 下載完整 CSV", csv_data, "asia_news_full.csv", "text/csv")
            
            st.success(f"總抓取 **{len(all_articles)}** 則 | 關鍵字命中 **{len(filtered)}** 則")
        else:
            st.error("未抓到任何新聞，請檢查 API Keys 或網路")

st.caption("無限制模式打造 | 內文抓取為實驗功能")
