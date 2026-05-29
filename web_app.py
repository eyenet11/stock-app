import streamlit as st
import yfinance as yf
import pandas as pd
import time

# ================= 網頁介面設定 =================
st.set_page_config(page_title="巴菲特選股神器", page_icon="📈", layout="centered")

st.title("📈 雙重濾網：高 ROE & ROA 選股神器")
st.markdown("上傳你的股票名單，系統將自動連線 Yahoo 財經，幫你抓出基本面最強的績優股！")

# 建立側邊欄：讓使用者自己調參數
st.sidebar.header("⚙️ 篩選條件設定")
min_roe = st.sidebar.number_input("最低 ROE 要求 (%)", min_value=0, max_value=100, value=15)
min_roa = st.sidebar.number_input("最低 ROA 要求 (%)", min_value=0, max_value=100, value=5)

# ================= 網頁主區塊 =================
# 1. 檔案上傳按鈕
uploaded_file = st.file_uploader("📂 請上傳你的股票名單 (例如 Daily_Stock_List.txt)", type=["txt", "csv"])

if uploaded_file is not None:
    # 讀取上傳的檔案
    content = uploaded_file.read().decode("utf-8").splitlines()
    stock_list = [line.strip() for line in content if line.strip().startswith("TW")]
    
    st.success(f"✅ 成功讀取 {len(stock_list)} 檔股票！")

    # 2. 執行按鈕
    if st.button("🚀 開始進行基本面健檢"):
        
        # 準備一個進度條跟顯示文字的地方
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 準備表格來存放結果
        results = []
        passed_codes = []

        for i, tw_code in enumerate(stock_list):
            yf_code = tw_code.replace("TW", "") + ".TW"
            status_text.text(f"🔍 正在分析 ({i+1}/{len(stock_list)}): {tw_code} ...")
            
            try:
                info = yf.Ticker(yf_code).info
                roe = info.get('returnOnEquity', 0)
                roa = info.get('returnOnAssets', 0)
                
                roe_pct = (0 if roe is None else roe) * 100
                roa_pct = (0 if roa is None else roa) * 100
                
                # 判斷是否及格
                is_pass = "✅ 及格" if (roe_pct >= min_roe and roa_pct >= min_roa) else "❌ 淘汰"
                
                if roe_pct >= min_roe and roa_pct >= min_roa:
                    passed_codes.append(tw_code)

                # 把資料存進結果清單
                results.append({
                    "股票代號": tw_code,
                    "ROE (%)": round(roe_pct, 2),
                    "ROA (%)": round(roa_pct, 2),
                    "狀態": is_pass
                })
                
                time.sleep(0.1) # 防止被擋
            except Exception:
                pass
            
            # 更新進度條
            progress_bar.progress((i + 1) / len(stock_list))

        status_text.success("🎉 分析完成！")
        
        # 3. 把結果畫成漂亮的網頁表格
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)

        # 4. 提供下載按鈕 (只下載及格的)
        if passed_codes:
            st.subheader(f"🔥 恭喜！共有 {len(passed_codes)} 檔股票通過考驗！")
            
            # 把及格名單轉成文字檔格式
            download_text = "\n".join(passed_codes)
            
            st.download_button(
                label="📥 下載及格名單 (可匯入飛狐)",
                data=download_text,
                file_name="ROAE_Pass.txt",
                mime="text/plain"
            )
        else:
            st.warning("沒有任何股票通過這次的嚴格篩選。")