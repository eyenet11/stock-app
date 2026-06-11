def extract_codes_from_image(img):
    """【第一階段】讓 Gemini 視覺大腦判讀圖片，加入 503 自動重試機制"""
    if GEMINI_API_KEY == "請填入你的_API_KEY":
        return [], "⚠️ 請先設定 GEMINI_API_KEY 才能呼叫 AI。"
        
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
            
            # 使用正規表達式進行清洗
            ai_text = response.text.upper()
            raw_codes = re.findall(r'\b[0-9A-Z]{4,6}\b', ai_text)
            
            # 去除重複並保持原有順序
            unique_codes = []
            for code in raw_codes:
                if code not in unique_codes:
                    unique_codes.append(code)
                    
            return unique_codes, None  # 成功就直接回傳，結束函數

        except Exception as e:
            error_msg = str(e)
            # 如果是 503 伺服器忙碌錯誤，且還沒達到最大重試次數
            if "503" in error_msg and attempt < max_retries - 1:
                time.sleep(3)  # 讓程式冷靜等 3 秒鐘，再進入下一次迴圈重試
                continue       # 繼續下一次嘗試
            else:
                # 如果不是 503 錯誤，或者是已經試了 3 次還是失敗，才真的報錯
                return [], f"AI 視覺辨識發生錯誤 (已嘗試{attempt+1}次): {error_msg}"