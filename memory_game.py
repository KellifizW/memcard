import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import json
from datetime import datetime
from bs4 import BeautifulSoup
from io import BytesIO

st.set_page_config(page_title="亞太新聞抓取器", layout="wide", page_icon="🌏")
st.title("🌏 亞太供應鏈新聞監控器（全 API 版）")
st.markdown("Google News + NewsData.io + Currents + Marketaux | 已修正按鈕 + 中文")

# Sidebar
with st.sidebar:
    st.header("🔑 API Keys")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents API", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    max_results = st.slider("每來源最多抓取", 5, 25, 10)

KEYWORDS = ["TSMC", "台積電", "三星", "Samsung", "半導體", "HBM", "CoWoS"]

def get_full_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        text = " ".join([p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 30])
        return text[:1800] if text else "抓取失敗"
    except:
        return "無法抓取內文"

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
    except Exception as e:
        st.error(f"Google RSS 錯誤: {e}")
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
        return [{"source": "Marketaux", "title": "API 錯誤"}]

# 主按鈕
if st.button("🚀 抓取所有來源新聞", type="primary"):
    with st.spinner("正在抓取中，請稍候..."):
        all_articles = []
        
        # Google News
        all_articles.extend(fetch_google_news("半導體 OR 台積電", "zh-TW_TW", max_results))
        all_articles.extend(fetch_google_news("半導体 OR 東京エレクトロン", "ja_JP", max_results))
        all_articles.extend(fetch_google_news("반도체 OR 삼성", "ko_KR", max_results))
        
        # 其他 API
        all_articles.extend(fetch_newsdata(newsdata_key, "台積電 OR 半導體", "tw", max_results))
        all_articles.extend(fetch_currents(currents_key, "台積電 OR 半導體", "zh", max_results))
        all_articles.extend(fetch_marketaux(marketaux_key, "2330.TW", max_results))

        if all_articles:
            df = pd.DataFrame(all_articles)
            display_cols = [c for c in ["source", "title", "published", "link", "summary"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)

            # 下載修正中文
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_buffer.seek(0)
            
            st.download_button("📥 下載 CSV（繁體中文正常）", csv_buffer.getvalue(), "asia_news_full.csv", "text/csv")
            
            st.success(f"✅ 總抓取 {len(all_articles)} 則新聞")
        else:
            st.error("未抓到任何資料，請檢查網路或 API Key")

st.caption("無限制模式 | 免費版有內容限制是正常現象")
