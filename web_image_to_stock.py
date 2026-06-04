import streamlit as st
import re
from datetime import datetime
from PIL import Image
from google import genai

st.set_page_config(page_title="AI 視覺選股轉換器", page_icon="👁️", layout="centered")

# ================= 參數與金鑰設定區 (安全版) =================
try:
    # 當程式在雲端執行時，它會去向 Streamlit 拿你鎖在 Secrets 裡的真實密碼
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    # ⚠️ 這是一個防呆的假密碼。請不要把真實密碼寫在這裡上傳到 GitHub！
    GEMINI_API_KEY = "NO_REAL_KEY_HERE"
# =========================================================

def extract_codes_from_image(img):
    """讓 Gemini AI 判讀圖片，抓出所有的 4 碼股票代號"""
    
    # 檢查是否只拿到假密碼
    if GEMINI_API_KEY == "NO_REAL_KEY_HERE":
        return None, "⚠️ 請至 Streamlit 後台 (Settings -> Secrets) 設定您的 GEMINI_API_KEY。"
        
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = """
        請分析這張圖片，找出裡面「所有的 4 碼數字股票代號」。
        請直接列出數字即可，不需要其他多餘的文字解釋。
        """

        # 呼叫 Gemini 視覺模型 (傳入圖片與提示詞)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, prompt]
        )
        
        # 使用正規表達式 (Regex) 進行二次清洗，確保只抓到 4 碼純數字
        ai_text = response.text
        raw_codes = re.findall(r'\b\d{4}\b', ai_text)
        
        # 去除重複並排序
        unique_codes = sorted(list(set(raw_codes)))
        return unique_codes, None

    except Exception as e:
        return None, f"AI 辨識發生錯誤: {e}"

# ================= 網頁主程式 =================
st.title("👁️ AI 視覺選股轉換器")
st.markdown("看到不錯的概念股圖片？直接上傳！AI 會瞬間幫您抓出所有股號，並轉成飛狐可用的 TXT 檔。")

# 1. 檔案上傳區塊
uploaded_file = st.file_uploader("🖼️ 請上傳含有股票代號的圖片 (支援 jpg, png, jpeg)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 顯示使用者上傳的圖片預覽
    img = Image.open(uploaded_file)
    st.image(img, caption="您上傳的圖片預覽")
    
    st.markdown("---")
    
    # 2. 啟動辨識按鈕
    if st.button("🚀 開始 AI 視覺海關", use_container_width=True):
        with st.spinner("🤖 Gemini AI 正在睜大眼睛幫您掃描圖片中的數字..."):
            
            # 執行 AI 辨識
            stock_codes, error_msg = extract_codes_from_image(img)
            
            if error_msg:
                st.error(error_msg)
            elif not stock_codes:
                st.warning("⚠️ AI 看完了圖片，但找不到任何像是 4 碼股票代號的數字。")
            else:
                st.success(f"🎯 辨識成功！共抓出 **{len(stock_codes)}** 檔股票代號。")
                
                # 將代號加上 TW，並準備成可下載的文字內容
                formatted_codes = [f"TW{code}" for code in stock_codes]
                download_text = "\n".join(formatted_codes)
                
                # 顯示抓到的代號給使用者看
                st.write("🔍 **抓取結果預覽：**")
                st.code(download_text, language="text")
                
                # 3. 產生下載按鈕，檔名為 stackYYYYMMDD.txt
                today_str = datetime.now().strftime('%Y%m%d')
                output_filename = f"stack{today_str}.txt"
                
                st.download_button(
                    label="📥 下載股票名單 (TXT)",
                    data=download_text,
                    file_name=output_filename,
                    mime="text/plain",
                    type="primary",
                    use_container_width=True
                )