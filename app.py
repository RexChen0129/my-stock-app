import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 原本在模組裡的功能，現在直接寫在這裡 ---
def get_processed_data(stock_id):
    """
    強化版數據抓取：自動處理台股後置碼與多層標題
    """
    # 1. 自動補上 .TW
    if not ("." in stock_id):
        target = f"{stock_id}.TW"
    else:
        target = stock_id
        
    try:
        # 2. 使用 yfinance 下載
        df = yf.download(target, period="1y", interval="1d", auto_adjust=True, progress=False)
        
        # 3. 處理多層標題 (yfinance 0.2.x 之後常出現的問題)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df is None or len(df) < 10: # 確保至少有 10 天數據才能算均線
            return None
            
        # 4. 強制轉換數值型態，避免計算錯誤
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        
        # 5. 計算均線
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # 6. 剔除空值並回傳
        return df.dropna(subset=['Close'])
        
    except Exception as e:
        print(f"Error: {e}")
        return None

# --- 2. Streamlit 網頁介面設定 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")

st.title("⚡ 專業股市分析系統 (整合穩定版)")

# 側邊欄設定
with st.sidebar:
    st.header("數據查詢")
    stock_id = st.text_input("請輸入台股代碼", value="2330")
    analyze_btn = st.button("點擊開始分析")

# --- 3. 主要邏輯控制 ---
if analyze_btn:
    with st.spinner('正在從 Yahoo Finance 抓取數據...'):
        df = get_processed_data(stock_id)
        
        if df is not None:
            # 建立 Plotly K 線圖
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name='K線'
                ),
                go.Scatter(x=df.index, y=df['MA5'], name='5日線', line=dict(color='orange', width=1)),
                go.Scatter(x=df.index, y=df['MA20'], name='20日線', line=dict(color='blue', width=1))
            ])
            
            fig.update_layout(
                title=f"{stock_id} 歷史走勢圖",
                xaxis_title="日期",
                yaxis_title="股價",
                xaxis_rangeslider_visible=False,
                template="plotly_dark", # 使用深色主題，這通常比較好看
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 顯示最新數據摘要
            col1, col2, col3 = st.columns(3)
            latest = df.iloc[-1]
            col1.metric("最新收盤價", round(latest['Close'], 2))
            col2.metric("5日線價格", round(latest['MA5'], 2))
            col3.metric("20日線價格", round(latest['MA20'], 2))
            
            # 顯示原始數據表格
            with st.expander("查看原始數據"):
                st.dataframe(df.tail(10))
        else:
            st.error(f"找不到代碼 {stock_id} 的數據，請檢查代碼是否正確（例如：2330）")

st.info("提示：如果遇到安裝問題，請確認 requirements.txt 只有 streamlit, yfinance, plotly 三個項目。")
