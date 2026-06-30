import streamlit as st
import feedparser
import urllib.parse
import requests
import pandas as pd
import json
from datetime import datetime
from bs4 import BeautifulSoup
from io import BytesIO

st.set_page_config(page_title="亞太新聞抓取器", layout="wide")
st.title("🌏 亞太供應鏈新聞監控器（全 API + 內文）")
st.markdown("**Google + NewsData + Currents + Marketaux** | 已修正中文亂碼")

# Sidebar (同上)
with st.sidebar:
    st.header("🔑 API Keys")
    newsdata_key = st.text_input("NewsData.io", "pub_eead009008954d30b8242dc77816bf17", type="password")
    currents_key = st.text_input("Currents", "zGbxOF-BIvNfS-jeV9WYrLDuRpcgUOBgZzRtqCBlHS8ncGtw", type="password")
    marketaux_key = st.text_input("Marketaux", "otCWokqLfT83SZYS42NoIujEc6b0cqOJdUosEZEp", type="password")
    max_results = st.slider("每來源數量", 5, 20, 10)

KEYWORDS = ["TSMC", "台積電", "三星", "Samsung", "半導體", "HBM", "CoWoS"]

def get_full_content(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, 'html.parser')
        text = " ".join([p.get_text() for p in soup.find_all('p') if len(p.get_text().strip()) > 30])
        return text[:1800] if text else "抓取失敗"
    except:
        return "無法抓取內文"

# fetch_xxx 函數（與上一版相同，省略以節省篇幅，你直接複製上一版完整函數貼上即可）

if st.button("🚀 抓取全部來源", type="primary"):
    with st.spinner("執行中..."):
        all_articles = []
        # ... (呼叫四個 fetch 函數，與上一版完全相同)

        df = pd.DataFrame(all_articles)
        if not df.empty:
            display_cols = [c for c in ["source", "title", "published", "link", "summary"] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)

            # === 修正中文亂碼的下載方式 ===
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_buffer.seek(0)
            
            st.download_button(
                label="📥 下載 CSV（繁體中文正常）",
                data=csv_buffer,
                file_name="asia_news_full.csv",
                mime="text/csv"
            )
            
            st.success(f"總抓取 {len(all_articles)} 則 | 命中關鍵字 {len([a for a in all_articles if any(k.lower() in str(a).lower() for k in KEYWORDS)])} 則")

st.info("免費版限制：大多只能拿到標題+摘要。想穩定讀全文建議考慮付費 API 或合法爬蟲。")
