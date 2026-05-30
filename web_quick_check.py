import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# ================= 網頁介面基本設定 =================
st.set_page_config(page_title="個股即時情報站", page_icon="🕵️‍♂️", layout="centered")

# ================= 核心爬蟲函數 =================
def get_stock_news(code):
    """抓取 Yahoo 股市個股最新 5 條新聞"""
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
                if href.startswith('/'):
                    href = "https://tw.stock.yahoo.com" + href
                
                if not any(n['title'] == title for n in news_list):
                    news_list.append({"title": title, "link": href})
                    
                if len(news_list) >= 5: 
                    break
                    
        return news_list
    except Exception:
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
                    
        if records:
            return pd.DataFrame(records[:10])
        return None
    except Exception:
        return None

def clean_number(val):
    """安全地將字串轉為純數字計算"""
    try:
        return int(str(val).replace(',', '').replace('+', '').replace(' ', ''))
    except:
        return 0

# ================= 網頁排版與互動設計 =================
st.title("🕵️‍♂️ 個股即時情報站")
st.markdown("輸入股票代號，一秒查詢 **最新新聞** 與 **三大法人籌碼動態**！")

col1, col2 = st.columns([3, 1])
with col1:
    code_input = st.text_input("👉 請輸入股票代號 (例如: 2330)", max_chars=6)
with col2:
    st.markdown("<br>", unsafe_allow_html=True) 
    search_btn = st.button("🚀 立即查詢", use_container_width=True)

if search_btn:
    code = code_input.strip()
    
    if not code.isdigit() or len(code) < 4:
        st.warning("⚠️ 請輸入正確的 4 碼 (或以上) 數字股票代號！")
    else:
        with st.spinner(f"正在為您搜集 {code} 的最新情報..."):
            
            # --- 區塊 1：新聞 ---
            st.subheader("📰 最新重點新聞")
            news = get_stock_news(code)
            if news:
                for n in news:
                    st.markdown(f"- **[{n['title']}]({n['link']})**")
            else:
                st.info("⚠️ 找不到近期相關新聞。")
                
            st.divider() 
            time.sleep(0.5)

            # --- 區塊 2：籌碼表格 ---
            st.subheader("🏦 近 10 日三大法人買賣超")
            chips_df = get_institutional_data(code)
            
            if chips_df is not None and not chips_df.empty:
                # 顯示原始網頁表格
                st.dataframe(chips_df, use_container_width=True)
                
                # 計算三大法人 10 日總計
                foreign_sum = chips_df['外資(張)'].apply(clean_number).sum()
                trust_sum = chips_df['投信(張)'].apply(clean_number).sum()
                dealer_sum = chips_df['自營商(張)'].apply(clean_number).sum()
                
                st.markdown("### 📊 近 10 日買賣超總計")
                
                # 使用 st.columns 和 st.metric 做出漂亮的數據儀表板
                m1, m2, m3 = st.columns(3)
                m1.metric(label="外資總計", value=f"{foreign_sum:,} 張")
                m2.metric(label="投信總計", value=f"{trust_sum:,} 張")
                m3.metric(label="自營商總計", value=f"{dealer_sum:,} 張")
                
                # --- 區塊 3：AI 智能籌碼短評 ---
                # 將三大法人的總和放入字典，並尋找「絕對值最大」的那一個法人
                investors = {
                    "外資": foreign_sum,
                    "投信": trust_sum,
                    "自營商": dealer_sum
                }
                
                # 找出動作最大(絕對值最高)的主力
                dominant_player = max(investors, key=lambda k: abs(investors[k]))
                dominant_volume = investors[dominant_player]
                
                st.markdown("<br>", unsafe_allow_html=True) # 稍微空一行
                
                if dominant_volume > 0:
                    st.success(f"🔥 **【AI 籌碼短評】近 10 日主要控盤者為【{dominant_player}】，累計大買 {dominant_volume:,} 張，主力積極偏多操作！**")
                elif dominant_volume < 0:
                    st.error(f"⚠️ **【AI 籌碼短評】警戒：近 10 日主要殺盤者為【{dominant_player}】，累計大賣 {abs(dominant_volume):,} 張，請留意上方倒貨壓力！**")
                else:
                    st.info("💡 **【AI 籌碼短評】平穩：近 10 日三大法人無明顯大動作。**")
                    
            else:
                st.warning("⚠️ 找不到法人買賣超資料 (可能為上櫃股票或尚無交易紀錄)。")