import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import datetime

# --- 配置區：請把你的 Token 貼在這裡 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# --- 1. 專業級數據抓取函數（帶有緩存） ---
@st.cache_data(ttl=3600) # 數據會暫存在網頁 1 小時，減少請求次數
def fetch_taiwan_stock_data(stock_id):
    """
    使用 FinMind API 抓取台股歷史數據
    """
    # 設定抓取時間（從一年前到今天）
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
        "token": FINMIND_TOKEN,
    }
    
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        data = res.json()
        
        if data['msg'] != 'success' or not data['data']:
            return None
            
        df = pd.DataFrame(data['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 計算技術指標
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        
        return df
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

# --- 2. 介面設計 ---
st.set_page_config(page_title="台股專業分析雲端版", layout="wide")
st.title("🏛️ 台股專業分析系統 (API 穩定版)")

with st.sidebar:
    st.header("查詢選單")
    st.info("本系統直接對接金融 API，不限流量且穩定運作。")
    stock_id = st.text_input("輸入台股代碼", value="2330")
    analyze_btn = st.button("啟動專業分析")

# --- 3. 繪圖與呈現 ---
if analyze_btn:
    with st.spinner(f'正在調用 API 獲取 {stock_id} 歷史數據...'):
        df = fetch_taiwan_stock_data(stock_id)
        
        if df is not None:
            # 建立高級 K 線圖
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df.index,
                    open=df['open'], high=df['max'],
                    low=df['min'], close=df['close'],
                    name='日K線'
                ),
                go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='yellow', width=1)),
                go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='cyan', width=1))
            ])
            
            fig.update_layout(
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                height=600,
                title=f"{stock_id} 一年期趨勢圖"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 數據儀表板
            last = df.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("當前收盤", f"{last['close']}")
            c2.metric("當日成交量", f"{int(last['Trading_Volume'])}")
            c3.metric("5日均價", f"{last['MA5']:.2f}")
            c4.metric("20日均價", f"{last['MA20']:.2f}")
        else:
            st.error("查無此代碼，或 API Token 已過期。請確認後再試！")
