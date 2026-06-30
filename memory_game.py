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
st.set_page_config(page_title="亞太股市大盤監控器 v10.1", layout="wide", page_icon="🌏")
st.title("🌏 亞太股市大盤前瞻系統 (v10.1 - 完整穩定版)")
st.markdown("當前核心功能：補齊頂層生命週期狀態，擊穿 Google News `batchexecute` 協議層。")

# =====================================================================
# ✨ 核心修復：初始化 Session State，徹底防止首次載入時的 KeyError 崩潰
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
# 🔥 Google News 核心逆向模組 (v10+ 雙重序列化防線)
# =====================================================================
def deep_protocol_decode(google_url):
    """【黑科技 RPC 解密】精準擊穿 Google News 混淆層，還原媒體原始網址"""
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
        
        # 1. 訪問 Google RSS 中繼網址，獲取 c-wiz 渲染上下文
        res = session.get(google_url, headers=headers, timeout=6)
        log_chain.append(f"[GET] 中繼網頁成功 (HTTP:{res.status_code})")
        
        if res.status_code != 200:
            return google_url, f"[FAIL] 中繼頁面請求失敗"

        # 2. 提取關鍵變數 at 令牌 (W02ccb)
        at_match = re.search(r'"W02ccb":"([^"]+)"', res.text)
        at_token = at_match.group(1) if at_match else "null"
        log_chain.append(f"[PARSE] AT Token: {at_token[:10]}...")

        # 3. 提取 data-p 屬性並將混淆字串安全還原
        match = re.search(r'data-p="([^"]+)"', res.text)
        if not match:
            soup = BeautifulSoup(res.text, 'html.parser')
            cwiz = soup.select_one('c-wiz[data-p]')
            if cwiz:
                data_p = cwiz.get('data-p')
            else:
                log_chain.append("[FAIL] 無法提取數據載荷 (可能觸發驗證碼限制)")
                return google_url, " | ".join(log_chain)
        else:
            data_p = match.group(1)

        log_chain.append("[PARSE] 數據載荷提取成功")

        # 4. 完美重建 Google 內層 RPC 陣列語法樹，避免字串替換出錯
        clean_json_str = data_p.replace('%.@.', '[')
        open_brackets = clean_json_str.count('[')
        close_brackets = clean_json_str.count(']')
        if open_brackets > close_brackets:
            clean_json_str += ']' * (open_brackets - close_brackets)
            
        raw_payload_arr = json.loads(clean_json_str)
        req_arr = [raw_payload_arr[0], raw_payload_arr[1] if len(raw_payload_arr) > 1 else []]
        
        # 進行第一層序列化
        req_str = json.dumps(req_arr, separators=(',', ':'))
        # 進行第二層封裝 (外層 Envelope 陣列，指定呼叫 Fbv4je 函數)
        f_req = json.dumps([[["Fbv4je", req_str, None, "generic"]]], separators=(',', ':'))
        
        # 5. 發送 POST 請求至 batchexecute 端點
        post_url = 'https://news.google.com/_/DotsSplashUi/data/batchexecute'
        post_data = {
            'f.req': f_req,
            'at': at_token
        }
        post_headers = headers.copy()
        post_headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        
        log_chain.append("[RPC] 發送 batchexecute 協議包...")
        post_res = session.post(post_url, data=post_data, headers=post_headers, timeout=6)
        
        if post_res.status_code != 200:
            log_chain.append(f"[RPC_FAIL] 伺服器拒絕 (HTTP:{post_res.status_code})")
            return google_url, " | ".join(log_chain)

        # 6. 解析 RPC 返回結果 (移除防注入安全前綴 )]}' )
        resp_text = post_res.text.replace(")]}'\n", "").strip()
        outer_arr = json.loads(resp_text)
        
        # 解析內部嵌套的 JSON 字串
        inner_data_str = outer_arr[0][0][2]
        inner_data_arr = json.loads(inner_data_str)
        
        # 最終提取出解密後的真實新聞網站 URL
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
    """Google News RSS 下載與工作流分流控制器"""
    try:
        q = urllib.parse.quote(query)
        parts = hl_cc.split('_')
        url = f"https://news.google.com/rss/search?q={q}&hl={parts[0]}&gl={parts[1]}"
        feed = feedparser.parse(url)
        arts = []
        for entry in feed.entries[:max_r]:
            raw_link = entry.link
            
            # 呼叫大改版的解密與爬取引擎
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
        
        # 執行 Google News 三大市場數據抓取
        g_arts = []
        g_arts.extend(fetch_google_news("(加權指數 OR 台股大盤 OR 三大法人買賣超)", "zh-TW_TW", max_results, "台股大盤動態"))
        g_arts.extend(fetch_google_news("(日經指數 OR 日經225 OR 東京股市)", "ja_JP", max_results, "日股大盤動態"))
        g_arts.extend(fetch_google_news("(韓國綜合指數 OR KOSPI OR 韓國股市)", "ko_KR", max_results, "韓股大盤動態"))
        all_articles.extend(g_arts)
        api_statuses["Google News RSS"] = "🟢 OK" if g_arts else "🔴 抓取空值"

        # NewsData.io (兼容快照模組)
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

        # 將結果寫入 Session 狀態中
        st.session_state.all_articles = all_articles
        st.session_state.api_statuses = api_statuses

# =====================================================================
# 📊 數據渲染與輸出層
# =====================================================================
# 安全檢查：僅在 api_statuses 存在（即使用者已經點擊並執行過按鈕）時才渲染狀態面板
if st.session_state.api_statuses is not None:
    st.subheader("🔌 系統連線狀態")
    cols = st.columns(2)
    cols[0].metric(label="Google News RSS 解密引擎", value=st.session_state.api_statuses.get("Google News RSS", "N/A"))
    if "NewsData.io API" in st.session_state.api_statuses:
        cols[1].metric(label="NewsData.io 數據通道", value=st.session_state.api_statuses.get("NewsData.io API"))
    st.markdown("---")

if st.session_state.all_articles is not None:
    df = pd.DataFrame(st.session_state.all_articles)
    if not df.empty:
        st.success(f"✅ 成功獲取 {len(df)} 則台日韓大盤最新動態！")
        st.dataframe(df, width='stretch')

        # 下載緩衝區
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下載完整數據 (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"asia_market_rpc_v10_1_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("💡 當前未發現相關市場數據，請確認連線狀態或嘗試更改關鍵字。")
