import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
from google import genai
from PIL import Image
import re

st.set_page_config(page_title="AI 視覺首席選股經理人", page_icon="👨‍💼", layout="wide")

# ================= 金鑰設定區 =================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    # ⚠️ 若在本地端測試，請換成真實 API Key
    GEMINI_API_KEY = "請填入你的_API_KEY"
# ============================================

def extract_codes_from_image(img):
    """【第一階段】讓 Gemini 視覺大腦判讀圖片，加入 503 自動重試機制"""
    if GEMINI_API_KEY == "請填入你的_API_KEY":
        return [], "⚠️ 請先至 Streamlit 後台 (Secrets) 設定您的 GEMINI_API_KEY。"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = """
        請分析這張圖片，找出裡面「所有的股票代號」。
        台灣股票或ETF代號通常為 4 到 6 碼的數字或英文字母組合（例如 2330, 0050, 00878, 00929）。
        請直接列出所有找到的代號，以半形逗號分隔，不要加上其他的文字解釋，也不要包含圖片最左邊的序號(1, 2, 3...)。
        """

        max_retries = 3  # 最多嘗試 3 次
        
        for attempt in range(max_retries):
            try:
                # 呼叫 Gemini 視覺模型
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[img, prompt]
                )
                
                ai_text = response.text.upper()
                raw_codes = re.findall(r'\b[0-9A-Z]{4,6}\b', ai_text)
                
                unique_codes = []
                for code in raw_codes:
                    if code not in unique_codes:
                        unique_codes.append(code)
                        
                return unique_codes, None  # 成功就直接回傳

            except Exception as e:
                error_msg = str(e)
                # 如果是 503 伺服器忙碌錯誤，且還沒達到最大重試次數
                if "503" in error_msg and attempt < max_retries - 1:
                    time.sleep(3)  # 讓程式冷靜等 3 秒鐘再試
                    continue       
                else:
                    return [], f"AI 視覺辨識發生錯誤 (已嘗試{attempt+1}次): {error_msg}"
                    
    except Exception as e:
        return [], f"AI 初始化失敗: {e}"

def get_stock_data(code):
    """【第二階段】抓取現股 20MA、籌碼總結與最新新聞"""
    data = {"代號": code, "現價": "無", "20MA": "無", "籌碼短評": "無", "最新新聞": "無"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"}
    
    try:
        hist = yf.Ticker(code + ".TW").history(period="3mo")
        if hist.empty: hist = yf.Ticker(code + ".TWO").history(period="3mo")
        if not hist.empty:
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            data["現價"] = round(hist['Close'].iloc[-1], 2)
            data["20MA"] = round(hist['MA20'].iloc[-1], 2)
    except: pass

    try:
        url_chips = f"https://tw.stock.yahoo.com/quote/{code}/institutional-trading"
        res_chips = requests.get(url_chips, headers=headers, timeout=5)
        soup_chips = BeautifulSoup(res_chips.text, 'html.parser')
        
        f_sum, t_sum = 0, 0
        count = 0
        for li in soup_chips.find_all('li'):
            texts = list(li.stripped_strings)
            if len(texts) >= 5 and '/' in texts[0] and texts[0].replace('/', '').isdigit():
                try:
                    f_sum += int(texts[1].replace(',', '').replace('+', ''))
                    t_sum += int(texts[2].replace(',', '').replace('+', ''))
                    count += 1
                    if count >= 5: break 
                except: pass
        if count > 0:
            data["籌碼短評"] = f"近5日外資 {f_sum}張，投信 {t_sum}張"
    except: pass

    try:
        url_news = f"https://tw.stock.yahoo.com/quote/{code}/news"
        res_news = requests.get(url_news, headers=headers, timeout=5)
        soup_news = BeautifulSoup(res_news.text, 'html.parser')
        
        news_titles = []
        for a in soup_news.find_all('a', href=True):
            title = a.text.strip()
            href = a['href']
            if len(title) > 10 and ('/news/' in href or '/article/' in href):
                if title not in news_titles:
                    news_titles.append(title)
                if len(news_titles) >= 3: 
                    break
        if news_titles:
            data["最新新聞"] = "、".join(news_titles)
    except: pass

    return data

def ask_ai_fund_manager(stock_data_list):
    """【第三階段】將綜合數據交給 Gemini 進行決選"""
    if GEMINI_API_KEY == "請填入你的_API_KEY":
        return "⚠️ 請先設定 GEMINI_API_KEY。"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        report_str = ""
        for s in stock_data_list:
            report_str += f"【{s['代號']}】現價:{s['現價']}, 20MA:{s['20MA']}\n"
            report_str += f"   籌碼: {s['籌碼短評']}\n"
            report_str += f"   新聞: {s['最新新聞']}\n\n"

        prompt = f"""
        你是一位極度嚴格的華爾街量化基金經理人。以下是今日系統初選出的「潛力股候選名單」。
        
        【今日名單與數據】
        {report_str}
        
        請根據上述提供的「法人籌碼(外資與投信動向)」以及「新聞題材(是否具備市場熱度或利多)」，從中挑選出 **【最強的 3 檔股票/ETF】** 作為明日買進建議。
        
        請使用以下格式輸出：
        ### 🏆 首席經理人 Top 3 買進推薦
        
        **🥇 第一名：[股票代號]**
        * **入選理由**：(精準點評其籌碼優勢與題材)
        * **防守策略**：(例如跌破20MA停損)
        
        **🥈 第二名：[股票代號]**
        * **入選理由**：...
        
        **🥉 第三名：[股票代號]**
        * **入選理由**：...
        
        ---
        💡 **經理人總結點評**：(一句話總結這份名單的整體資金動向或產業趨勢)
        """

        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI 錯誤：{e}"

# ================= 網頁主程式 =================
st.title("👨‍💼 AI 視覺首席選股經理人")
st.markdown("上傳您的名單或**截圖**，AI 會瞬間查閱**三大法人籌碼**與**全網新聞題材**，為您精選明日必買 Top 3！")

tab1, tab2 = st.tabs(["📄 方式一：上傳飛狐名單 (.txt)", "🖼️ 方式二：上傳截圖看圖選股"])
final_codes = []

with tab1:
    st.info("💡 支援飛狐交易師匯出的 txt 檔 (格式如 TW2330 或 2330)")
    txt_file = st.file_uploader("📂 請上傳 .txt 股票名單", type=["txt"])
    
    if st.button("🚀 從 TXT 啟動 AI 診斷", use_container_width=True, key="btn_txt"):
        if txt_file is None:
            st.warning("⚠️ 請先上傳 .txt 檔案！")
        else:
            content = txt_file.read().decode("utf-8").splitlines()
            for line in content:
                clean_line = line.strip().upper().replace('TW', '').replace('=', '').replace('"', '')
                match = re.search(r'\b\d{4}\b', clean_line)
                if match and match.group() not in final_codes:
                    final_codes.append(match.group())

with tab2:
    st.info("💡 看到網路上的看好名單？直接截圖上傳，讓 AI 幫你把代號抓出來！")
    img_file = st.file_uploader("🖼️ 請上傳含有股票代號的圖片", type=["jpg", "jpeg", "png"])
    
    if img_file is not None:
        img = Image.open(img_file)
        st.image(img, caption="您上傳的待審查圖片", use_container_width=True)
        
    if st.button("🚀 從圖片啟動 AI 診斷", use_container_width=True, key="btn_img"):
        if img_file is None:
            st.warning("⚠️ 請先上傳圖片！")
        else:
            with st.spinner("👁️ AI 視覺正在辨識圖片中的代號 (遇到塞車會自動重試)..."):
                final_codes, error_msg = extract_codes_from_image(img)
                if error_msg: st.error(error_msg)

# ================= 共同執行邏輯 =================
if final_codes:
    if len(final_codes) > 30:
        st.warning(f"⚠️ 名單高達 {len(final_codes)} 檔，系統隨機抽取前 30 檔以維持分析品質。")
        final_codes = final_codes[:30]
        
    st.success(f"✅ 成功鎖定 {len(final_codes)} 檔候選股票：{', '.join(final_codes)}")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    stock_data_list = []
    
    for i, code in enumerate(final_codes):
        status_text.text(f"🔍 正在搜集 ({i+1}/{len(final_codes)})：{code} 的籌碼與題材...")
        data = get_stock_data(code)
        stock_data_list.append(data)
        progress_bar.progress((i + 1) / len(final_codes))
        time.sleep(0.1)
        
    status_text.success("✅ 數據搜集完畢！正在交給 AI 總經理決選...")
    
    with st.spinner("🧠 AI 基金經理人正在激戰挑選 Top 3..."):
        ai_report = ask_ai_fund_manager(stock_data_list)
        
    st.markdown("---")
    st.subheader("📝 最終決策報告出爐")
    st.info(ai_report)
    
    with st.expander("🔍 點我看 AI 參考的底層大數據"):
        st.dataframe(pd.DataFrame(stock_data_list), use_container_width=True)