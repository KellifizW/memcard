import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import json
from datetime import datetime
from bs4 import BeautifulSoup  # 新增：抓內文

st.set_page_config(page_title="亞太新聞抓取器", layout="wide")
st.title("🌏 亞太供應鏈新聞監控器（含內文抓取）")

# Sidebar
with st.sidebar:
    st.header("API Keys")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    max_results = st.slider("抓取數量", 5, 30, 15)

KEYWORDS = ["TSMC", "台積電", "三星", "Samsung", "半導體", "HBM", "CoWoS"]

def get_full_content(url):
    """嘗試抓取完整內文"""
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, 'html.parser')
        paragraphs = soup.find_all('p')
        content = " ".join([p.text.strip() for p in paragraphs[:10] if len(p.text) > 20])
        return content[:2000] if content else "無法抓取內文"
    except:
        return "抓取內文失敗（可能需付費或反爬）"

if st.button("🚀 抓取新聞並分析", type="primary"):
    with st.spinner("抓取中..."):
        # Google News
        articles = []
        for q, hl in [("半導體 OR 台積電", "zh-TW_TW"), ("半導体 OR 東京エレクトロン", "ja_JP"), ("반도체 OR 삼성", "ko_KR")]:
            arts = []  # 你的 fetch_google_news 函數
            # ... (保留你之前的 fetch 邏輯)
            articles.extend(arts)

        # NewsData.io
        try:
            url = f"https://newsdata.io/api/1/latest?apikey={newsdata_key}&country=tw&q=台積電 OR 半導體"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            for item in data.get("results", [])[:max_results]:
                item["source"] = "NewsData.io"
                item["full_content"] = get_full_content(item.get("link", ""))
                articles.append(item)
        except:
            pass

        # 過濾與顯示
        df = pd.DataFrame(articles)
        if not df.empty:
            st.dataframe(df[["source", "title", "published", "link"]], use_container_width=True)
            
            # 下載修正編碼
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 下載 CSV（含中文）", csv, "asia_news.csv", "text/csv")
            
            st.success("✅ 已嘗試抓取內文！點擊連結可手動查看完整報導")

st.info("內文抓取為實驗功能，部分網站會失敗（反爬蟲）。建議搭配你的 AI 模型直接讀取 link 內容。")
