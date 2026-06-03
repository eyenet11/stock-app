import streamlit as st
import yfinance as yf
import pandas as pd
import re
from datetime import datetime
import time
from google import genai

st.set_page_config(page_title="AI 權證全自動篩選器", page_icon="🎯", layout="wide")

# ================= 參數與金鑰設定區 =================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    GEMINI_API_KEY = "請填入你的_API_KEY"
# ============================================

# ================= 初始化記憶體 (Session State) =================
if 'warrant_search_done' not in st.session_state:
    st.session_state.warrant_search_done = False
if 'passed_warrants' not in st.session_state:
    st.session_state.passed_warrants = []
# ============================================================

def get_stock_and_ma20(code):
    """抓取現股 20MA (包含三重備援)"""
    try:
        hist = yf.Ticker(code + ".TW").history(period="3mo")
        if hist.empty: hist = yf.Ticker(code + ".TWO").history(period="3mo")
        if not hist.empty:
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            return round(hist['Close'].iloc[-1], 2), round(hist['MA20'].iloc[-1], 2)
    except:
        pass
    return None, None

def calculate_days_left(date_str):
    try:
        date_str = str(date_str).strip()
        match = re.search(r'(\d+)年(\d+)月(\d+)', date_str)
        if match:
            year = int(match.group(1)) + 1911 
            month = int(match.group(2))
            day = int(match.group(3))
            end_date = datetime(year, month, day)
            return (end_date - datetime.now()).days
        return 0
    except:
        return 0

def ask_ai_top_3(warrants_list, stock_price, target_type):
    if GEMINI_API_KEY == "請填入你的_API_KEY":
        return "⚠️ 請先在 Streamlit 後台 (Secrets) 設定您的 GEMINI_API_KEY。"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        warrant_data_str = ""
        for w in warrants_list:
            warrant_data_str += f"代號:{w['權證代碼']} | 名稱:{w['權證名稱']} | 價內外:{w['價內外(%)']} | 天數:{w['剩餘天數']} | 行使比例:{w['行使比例']}\n"

        prompt = f"""
        你是一位專業的權證操盤手。
        目前現股價格為 {stock_price} 元，我們目前的策略是操作【{target_type}】權證。
        以下是從市場上初步篩選出來的候選名單（已符合天期>60天且價外15%~價內5%）：
        
        {warrant_data_str}
        
        請根據以下三個條件，從上面的名單中精選出【前 3 名】最推薦的權證：
        1. 價內外程度：以稍微價外 (-10% ~ 0%) 為最佳甜密區，槓桿與勝率最平衡。
        2. 行使比例：越高越好（與現股連動性最佳，跳動比較有感）。
        3. 剩餘天期：90天 ~ 180天最剛好（太短時間價值耗損快，太長沒槓桿）。
        
        請依照下列格式給出你的報告：
        ### 👑 AI 精選 Top 3 權證
        **🥇 第一名：[權證代碼] [權證名稱]**
        - 推薦理由：(分析其價內外、天期與行使比例的優勢)
        **🥈 第二名：[權證代碼] [權證名稱]**
        - 推薦理由：...
        **🥉 第三名：[權證代碼] [權證名稱]**
        - 推薦理由：...
        
        ### ⚠️ 實戰最後叮嚀
        (提醒使用者：帶著這三檔代號去券商APP，務必檢查「買賣價差是否過大」與「是否有掛出穩定的造市單」)
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"⚠️ AI 分析發生錯誤：{e}"

# ================= 網頁主程式 =================
st.title("🎯 頂級造市商【權證全自動篩選器】雲端版")
st.markdown("嚴格遵守 4 大鐵則：**趨勢判定、價內外15%~5%、天期>60天、優質造市商**。")

# 1. 檔案上傳區塊
uploaded_file = st.file_uploader("📂 請上傳證交所的每日權證大表 (warrantStock.csv 或 xls)", type=["csv", "xls", "xlsx"])

# 2. 搜尋條件區塊
col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.5, 1.5])
with col1:
    target_code = st.text_input("👉 現股代號 (如 2330)", max_chars=6)
with col2:
    target_issuer = st.selectbox("🏦 發行券商", ["全部", "群益", "凱基", "元大", "富邦", "統一"])
with col3:
    # ✨ 全新加入：多空強制切換器
    target_strategy = st.selectbox("🧭 策略方向", ["🤖 AI 自動判定 (依20MA)", "📈 強制找【認購】", "📉 強制找【認售】"])
with col4:
    st.markdown("<br>", unsafe_allow_html=True) 
    search_btn = st.button("🚀 篩選黃金權證", use_container_width=True)

# ----------------- 階段 1：處理搜尋 -----------------
if search_btn:
    code = target_code.strip()
    
    if uploaded_file is None:
        st.warning("⚠️ 請先上傳權證大表檔案！")
    elif len(code) < 4:
        st.warning("⚠️ 請輸入正確的股票代號！")
    else:
        with st.spinner("正在讀取檔案與計算均線..."):
            try:
                if uploaded_file.name.endswith('.csv'):
                    try:
                        warrants_df = pd.read_csv(uploaded_file, encoding='cp950', skiprows=2, dtype=str)
                    except:
                        uploaded_file.seek(0)
                        warrants_df = pd.read_csv(uploaded_file, encoding='utf-8', skiprows=2, dtype=str)
                else:
                    warrants_df = pd.read_excel(uploaded_file, skiprows=2, dtype=str)
                warrants_df.columns = [str(c).strip() for c in warrants_df.columns]
            except Exception as e:
                st.error(f"檔案讀取失敗: {e}")
                warrants_df = None

            if warrants_df is not None and not warrants_df.empty:
                stock_price, ma20 = get_stock_and_ma20(code)
                
                if stock_price is None:
                    st.error("❌ 找不到現貨報價。")
                    st.session_state.warrant_search_done = False
                else:
                    # ✨ 核心邏輯：判斷真實均線趨勢
                    is_bull_ma20 = stock_price > ma20
                    
                    # 根據使用者的「策略方向」來決定程式要做多還是做空
                    if target_strategy == "🤖 AI 自動判定 (依20MA)":
                        is_bull_trade = is_bull_ma20
                        target_type = "認購" if is_bull_trade else "認售"
                    elif target_strategy == "📈 強制找【認購】":
                        is_bull_trade = True
                        target_type = "認購"
                    elif target_strategy == "📉 強制找【認售】":
                        is_bull_trade = False
                        target_type = "認售"
                    
                    passed_warrants = []
                    for index, row in warrants_df.iterrows():
                        underlying = str(row.get('標的代號', '')).strip()
                        if underlying != code: continue
                            
                        w_code = str(row.get('權證代號', '')).strip().replace('="', '').replace('"', '')
                        w_name = str(row.get('權證簡稱', '')).strip()
                        w_type = str(row.get('權證類型', '')).strip()
                        
                        if target_issuer != "全部" and target_issuer not in w_name: continue
                        
                        # 依照決定的策略 (is_bull_trade) 來篩選認購或認售
                        if is_bull_trade and '購' not in w_type: continue
                        if not is_bull_trade and '售' not in w_type: continue
                            
                        end_date = str(row.get('最後交易日', '')).strip()
                        days_left = calculate_days_left(end_date)
                        if days_left < 60: continue
                            
                        strike_str = str(row.get('履約價格(元)/點數', '0')).replace(',', '').strip()
                        try:
                            strike_price = float(strike_str)
                            if strike_price <= 0: continue 
                        except: continue 
                            
                        # 認購與認售的價內外計算公式不同
                        if is_bull_trade: # 認購：(現價-履約價)/履約價
                            moneyness = (stock_price - strike_price) / strike_price * 100
                        else:             # 認售：(履約價-現價)/履約價
                            moneyness = (strike_price - stock_price) / strike_price * 100
                            
                        if -15 <= moneyness <= 5:
                            ratio = str(row.get('行使比例', 'N/A')).strip()
                            passed_warrants.append({
                                "權證代碼": w_code,
                                "權證名稱": w_name,
                                "履約價": strike_price,
                                "價內外(%)": f"{round(moneyness, 1)}%",
                                "剩餘天數": days_left,
                                "行使比例": ratio
                            })

                    # 將結果存入記憶體
                    st.session_state.warrant_search_done = True
                    st.session_state.passed_warrants = passed_warrants
                    st.session_state.stock_price = stock_price
                    st.session_state.ma20 = ma20
                    st.session_state.is_bull_ma20 = is_bull_ma20
                    st.session_state.target_type = target_type
                    st.session_state.target_issuer = target_issuer
                    st.session_state.target_strategy = target_strategy

# ----------------- 階段 2：顯示結果與 AI 按鈕 -----------------
if st.session_state.warrant_search_done:
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前現股價", f"{st.session_state.stock_price} 元")
    m2.metric("20MA (月線)", f"{st.session_state.ma20} 元")
    
    # 動態顯示趨勢與策略
    trend_text = "多頭 (站上月線)" if st.session_state.is_bull_ma20 else "空頭 (跌破月線)"
    if st.session_state.target_strategy != "🤖 AI 自動判定 (依20MA)":
        trend_text += " (手動強制改變方向)"
        
    m3.metric("趨勢判定", trend_text, delta=f"尋找【{st.session_state.target_type}】" if st.session_state.target_type == "認購" else f"-尋找【{st.session_state.target_type}】")
    m4.metric("目標發行商", st.session_state.target_issuer)
    st.markdown("---")

    if st.session_state.passed_warrants:
        df_result = pd.DataFrame(st.session_state.passed_warrants)
        df_result = df_result.sort_values(by="剩餘天數", ascending=False)
        df_result["剩餘天數"] = df_result["剩餘天數"].astype(str) + " 天"
        
        st.success(f"為您篩選出 **{len(st.session_state.passed_warrants)} 檔** 候選標的。")
        st.dataframe(df_result, use_container_width=True, hide_index=True)
        
        # ===== 啟動 AI 決選機制 =====
        st.markdown("### 🤖 標的太多不知怎麼挑？交給 AI 幫您精選！")
        if st.button("✨ 讓 Gemini AI 幫我選出 Top 3", use_container_width=True):
            with st.spinner("AI 正在深度分析每一檔權證的槓桿與時間價值..."):
                ai_report = ask_ai_top_3(st.session_state.passed_warrants, st.session_state.stock_price, st.session_state.target_type)
                st.info(ai_report)
    else:
        st.warning(f"您上傳的檔案中，沒有符合【{st.session_state.target_type}】條件的標的。")