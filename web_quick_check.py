import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from google import genai

# ================= 參數與金鑰設定區 =================
# 嘗試從 Streamlit 雲端的安全金庫中讀取 API Key
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    # 這是為了讓程式不要當機的假密碼。
    # ⚠️ 絕對不要把真正的 API Key 寫死在這裡上傳到 GitHub！
    GEMINI_API_KEY = "LOCAL_TEST_KEY_NO_REAL_API_KEY"
# ============================================

st.set_page_config(page_title="AI 個股情報站", page_icon="🤖", layout="wide")

# ================= 核心爬蟲函數 =================
def get_stock_news(code):
    """抓取 Yahoo 股市最新 5 條新聞"""
    url = f"https://tw.stock.yahoo.com/quote/{code}/news"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        news_list = []
        links = soup.find_all('a', href=True)
        for a in links:
            href = a['href']
            title = a.text.strip()
            if len(title) > 10 and ('/news/' in href or '/article/' in href):
                if href.startswith('/'): href = "https://tw.stock.yahoo.com" + href
                if not any(n['title'] == title for n in news_list):
                    news_list.append({"title": title, "link": href})
                if len(news_list) >= 5: break
        return news_list
    except:
        return []

def get_institutional_data(code):
    """使用文字特徵辨識法，抓取 Yahoo 法人籌碼"""
    url = f"https://tw.stock.yahoo.com/quote/{code}/institutional-trading"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        records = []
        for li in soup.find_all('li'):
            texts = list(li.stripped_strings)
            if len(texts) >= 5:
                date_str = texts[0]
                if '/' in date_str and date_str.replace('/', '').isdigit():
                    records.append({
                        '日期': texts[0],
                        '外資(張)': texts[1],
                        '投信(張)': texts[2],
                        '自營商(張)': texts[3]
                    })
        if records: return pd.DataFrame(records[:10])
        return None
    except:
        return None

def clean_number(val):
    """安全地將字串(例如 +1,234 或 -500)轉為純數字計算"""
    try: return int(str(val).replace(',', '').replace('+', '').replace(' ', ''))
    except: return 0

# ================= 呼叫 Gemini AI 的函數 =================
def ask_gemini_analysis(stock_code, news_list, chips_df):
    """將新聞與籌碼數據交給 Gemini 進行專業分析"""
    
    # 檢查是否有拿到真實的 API Key
    if GEMINI_API_KEY == "LOCAL_TEST_KEY_NO_REAL_API_KEY":
        return "⚠️ 請先至 Streamlit 後台 (Settings -> Secrets) 設定您的 GEMINI_API_KEY。"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # 整理新聞文字
        news_text = "\n".join([f"- {n['title']}" for n in news_list]) if news_list else "無近期新聞"
        
        # 整理籌碼數字
        if chips_df is not None:
            f_sum = chips_df['外資(張)'].apply(clean_number).sum()
            t_sum = chips_df['投信(張)'].apply(clean_number).sum()
            d_sum = chips_df['自營商(張)'].apply(clean_number).sum()
            chips_text = f"近10日籌碼：外資總計 {f_sum}張，投信總計 {t_sum}張，自營商總計 {d_sum}張。"
        else:
            chips_text = "無法人籌碼資料。"

        prompt = f"""
        你是一位專業的台股分析師。請根據以下關於股票 {stock_code} 的最新資訊，提供一段約 150 字的專業短評。
        
        【最新新聞標題】
        {news_text}
        
        【籌碼狀態】
        {chips_text}
        
        請依照以下格式回答：
        **📰 新聞情緒**：(綜合新聞標題，判斷目前市場偏多、偏空或中立，並簡述原因)
        **🏦 籌碼解讀**：(根據法人買賣超，判斷目前主力動向)
        **💡 總結建議**：(給投資人的簡短操作提醒)
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"⚠️ AI 分析發生錯誤 (可能為 API Key 錯誤或連線逾時)。錯誤代碼：{e}"

# ================= 網頁排版設計 =================
st.title("🤖 AI 個股情報與籌碼分析站")
st.markdown("輸入股票代號，讓 **Google Gemini AI** 為您瞬間解讀新聞與主力動向！")

col1, col2 = st.columns([3, 1])
with col1:
    code_input = st.text_input("👉 請輸入股票代號 (例如: 2330)", max_chars=6)
with col2:
    st.markdown("<br>", unsafe_allow_html=True) 
    search_btn = st.button("🚀 啟動 AI 智能分析", use_container_width=True)

if search_btn:
    code = code_input.strip()
    
    if not code.isdigit() or len(code) < 4:
        st.warning("⚠️ 請輸入正確的 4 碼數字股票代號！")
    else:
        with st.spinner(f"正在為您搜集資料並喚醒 Gemini AI..."):
            
            news = get_stock_news(code)
            chips_df = get_institutional_data(code)
            
            # 左右排版
            left_col, right_col = st.columns([1.2, 1])
            
            with left_col:
                st.subheader("✨ Gemini AI 智能診斷")
                ai_report = ask_gemini_analysis(code, news, chips_df)
                st.info(ai_report)
                
                st.subheader("📰 最新重點新聞")
                if news:
                    for n in news:
                        st.markdown(f"- [{n['title']}]({n['link']})")
                else:
                    st.write("找不到近期新聞。")

            with right_col:
                st.subheader("🏦 近 10 日三大法人買賣超")
                if chips_df is not None and not chips_df.empty:
                    st.dataframe(chips_df, use_container_width=True, hide_index=True)
                    
                    foreign_sum = chips_df['外資(張)'].apply(clean_number).sum()
                    trust_sum = chips_df['投信(張)'].apply(clean_number).sum()
                    dealer_sum = chips_df['自營商(張)'].apply(clean_number).sum()
                    
                    st.markdown("### 📊 近 10 日買賣超總計")
                    m1, m2, m3 = st.columns(3)
                    m1.metric(label="外資總計", value=f"{foreign_sum:,} 張")
                    m2.metric(label="投信總計", value=f"{trust_sum:,} 張")
                    m3.metric(label="自營商總計", value=f"{dealer_sum:,} 張")
                    
                    # --- AI 短評 ---
                    investors = {
                        "外資": foreign_sum,
                        "投信": trust_sum,
                        "自營商": dealer_sum
                    }
                    dominant_player = max(investors, key=lambda k: abs(investors[k]))
                    dominant_volume = investors[dominant_player]
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if dominant_volume > 0:
                        st.success(f"🔥 **【主力追蹤】近 10 日主要控盤者為【{dominant_player}】，累計大買 {dominant_volume:,} 張，主力積極偏多操作！**")
                    elif dominant_volume < 0:
                        st.error(f"⚠️ **【主力追蹤】警戒：近 10 日主要殺盤者為【{dominant_player}】，累計大賣 {abs(dominant_volume):,} 張，請留意上方倒貨壓力！**")
                    else:
                        st.info("💡 **【主力追蹤】平穩：近 10 日三大法人無明顯大動作。**")
                else:
                    st.warning("⚠️ 找不到法人籌碼資料。")