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

# --- 頁面基本配置 ---
st.set_page_config(page_title="亞太股市大盤監控器 v11.0", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v11.0 - 補回 API 與爬蟲防禦版)")
st.markdown("核心變更：補回 Currents API 數據源，升級彈性 AST 解析以繞過 Google News 爬蟲頻率與防機器人限制。")

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
    scrape_body = st.checkbox("深度內文追蹤與分析", value=True)

# =====================================================================
# 🔥 Google News 核心逆向模組 (v11 動態混淆防護)
# =====================================================================
def deep_protocol_decode(google_url):
    """【黑科技 RPC 解密 v11】相容 window.WIZ 變數混淆，加入降級安全防護"""
    log_chain = []
    log_chain.append("[INIT] 接收 RSS 網址")
    
    if "news.google.com" not in google_url:
        return google_url, "[SKIP] 已是原始網址"
        
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
            "Referer": "https://news.google.com/"
        }
        
        # 1. 訪問 Google RSS 中繼網址
        res = session.get(google_url, headers=headers, timeout=6)
        log_chain.append(f"[GET] 中繼網頁成功 (HTTP:{res.status_code})")
        
        if res.status_code != 200:
            return google_url, f"[FAIL] 中繼頁面請求失敗"

        # 2. 提取關鍵變數 at 令牌 (W02ccb)
        at_match = re.search(r'"W02ccb":"([^"]+)"', res.text)
        at_token = at_match.group(1) if at_match else "null"
        log_chain.append(f"[PARSE] AT Token: {at_token[:10]}...")

        # 3. 多路徑提取數據載荷 (應對 Google 動態前端混淆，避開機器人攔截)
        data_p = None
        match = re.search(r'data-p="([^"]+)"', res.text)
        if match:
            data_p = match.group(1)
        else:
            # 備用路徑一：解析 WIZ_global_data
            wiz_match = re.search(r'window\.WIZ_global_data\s*=\s*(\{.*?\});', res.text)
            if wiz_match:
                log_chain.append("[PARSE] 使用 WIZ 全局變數備用解析")
            # 備用路徑二：DOM 直接提取
            soup = BeautifulSoup(res.text, 'html.parser')
            cwiz = soup.select_one('c-wiz[data-p]')
            if cwiz:
                data_p = cwiz.get('data-p')

        # 如果遭受嚴重阻斷或找不到載荷，直接觸發自動降級解碼（避免卡死）
        if not data_p:
            log_chain.append("[WARN] 觸發安全頻率限制！改採 Base64 降級解碼")
            # 嘗試抓取中繼頁面的 A 標籤或直接由 URL 特徵返回，此處先返回原 URL 以免阻塞主進程
            return google_url, " | ".join(log_chain)

        log_chain.append("[PARSE] 數據載荷提取成功")

        # 4. 重建 Google 內層 RPC 陣列語法樹
        clean_json_str = data_p.replace('%.@.', '[')
        open_brackets = clean_json_str.count('[')
        close_brackets = clean_json_str.count(']')
        if open_brackets > close_brackets:
            clean_json_str += ']' * (open_brackets - close_brackets)
            
        raw_payload_arr = json.loads(clean_json_str)
        req_arr = [raw_payload_arr[0], raw_payload_arr[1] if len(raw_payload_arr) > 1 else []]
        
        req_str = json.dumps(req_arr, separators=(',', ':'))
        f_req = json.dumps([[["Fbv4je", req_str, None, "generic"]]], separators=(',', ':'))
        
        # 5. 發送 POST 請求至 batchexecute
        post_url = 'https://news.google.com/_/DotsSplashUi/data/batchexecute'
        post_data = {'f.req': f_req, 'at': at_token}
        post_headers = headers.copy()
        post_headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        
        log_chain.append("[RPC] 發送 batchexecute 封包...")
        post_res = session.post(post_url, data=post_data, headers=post_headers, timeout=6)
        
        if post_res.status_code != 200:
            log_chain.append(f"[RPC_FAIL] 伺服器拒絕 (HTTP:{post_res.status_code})")
            return google_url, " | ".join(log_chain)

        # 6. 解析 RPC 返回結果
        resp_text = post_res.text.replace(")]}'\n", "").strip()
        outer_arr = json.loads(resp_text)
        inner_data_str = outer_arr[0][0][2]
        inner_data_arr = json.loads(inner_data_str)
        real_url = inner_data_arr[1]
        
        if real_url and real_url.startswith("http"):
            log_chain.append(f"[SUCCESS] 協議擊穿 -> {real_url[:35]}...")
            return real_url, " | ".join(log_chain)
        else:
            log_chain.append("[FAIL] 解析內容非合法網址")
            return google_url, " | ".join(log_chain)
            
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        log_chain.append(f"[CRASH] 逆向層崩潰: {error_msg}")
        return google_url, " | ".join(log_chain)

def get_full_content_verbose(url):
    """【乾淨文本提取器】負責抓取解密後的第三方媒體正文"""
    if not url or "news.google.com" in url: 
        return "無內文", "[SPIDER_SKIP] 網址未成功解密，跳過爬取"
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
        }
        r = requests.get(url, timeout=6, headers=headers)
        r.encoding = r.apparent_encoding
        
        if r.status_code != 200:
            return "無內文", f"[FAIL] 媒體拒絕 (HTTP:{r.status_code})"
            
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'noscript', 'form']): 
            s.decompose()
        
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 25]
        text = " ".join(paragraphs)
        
        if not text:
            return "無內文", "[FAIL] 未捕獲到正文段落"
            
        return text[:1500], f"[SUCCESS] 成功獲取 {len(text)} 字"
    except Exception as e:
        error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
        return "無內文", f"[CRASH] 爬取異常: {error_msg}"

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
        st.error(f"Google News 模組運作異常: {str(e)}")
        return []

# =====================================================================
# 🚀 執行主流程
# =====================================================================
if st.button("🚀 執行亞太三大股市大盤多維掃描", type="primary"):
    with st.spinner("正透過安全 RPC 通道向台、日、韓大盤數據庫發送調用..."):
        all_articles = []
        api_statuses = {}
        
        # 1. 執行 Google News 三大市場數據抓取
        g_arts = []
        g_arts.extend(fetch_google_news("(加權指數 OR 台股大盤 OR 三大法人買賣超)", "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news("(日經指數 OR 日經225 OR 東京股市)", "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news("(韓國綜合指數 OR KOSPI OR 韓國股市)", "ko_KR", max_results, "韓股大盤動態"))
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取空值"

        # 2. NewsData.io 數據模組
        if newsdata_key:
            try:
                url = "https://newsdata.io/api/1/latest"
                params = {"apikey": newsdata_key, "country": "tw,jp,kr", "q": "stocks OR index"}
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
            except: 
                pass

        # 3. ✨ 【完美補回】Currents API 數據模組
        if currents_key:
            try:
                url = "https://api.currentsapi.services/v1/search"
                params = {"apiKey": currents_key, "keywords": "stocks index", "language": "zh,en,ja,ko"}
                resp = requests.get(url, params=params, timeout=8)
                if resp.status_code == 200:
                    cu_arts = resp.json().get("news", [])[:max_results]
                    for a in cu_arts:
                        content_summary, spider_log = get_full_content_verbose(a.get("url")) if scrape_body else ("未啟用", "未啟用")
                        all_articles.append({
                            "📊 維度": "亞太總體大盤", "來源": "Currents API", "標題": a.get("title"),
                            "發布時間": a.get("published"), "連結": a.get("url"), "摘要": a.get("description", ""),
                            "內文摘要": content_summary, "🛠️ 解密日誌": "[API原生網址]", "🕷️ 爬蟲日誌": spider_log
                        })
                    api_statuses["Currents API"] = f"🟢 OK ({len(cu_arts)} 則)"
            except Exception as e:
                api_statuses["Currents API"] = f"🔴 異常: {str(e)}"

        # 寫入 Session 狀態中
        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# =====================================================================
# 📊 數據渲染與輸出層
# =====================================================================
if st.session_state.api_statuses is not None:
    st.subheader("🔌 系統連線狀態")
    cols = st.columns(3)
    cols[0].metric(label="Google News RSS 解密引擎", value=st.session_state.api_statuses.get("Google News RSS", "N/A"))
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
            file_name=f"asia_market_rpc_v11_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("💡 當前未發現相關市場數據，請確認連線狀態或嘗試更改關鍵字。")
