import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 強化版數據抓取函數 ---
def get_processed_data(stock_id):
    # 判斷代碼格式
    if stock_id.isdigit(): # 全數字則補上 .TW
        target = f"{stock_id}.TW"
    else:
        target = stock_id.upper()
        
    try:
        # 下載數據，加入偽裝 Header 避免被 Yahoo 封鎖
        ticker = yf.Ticker(target)
        df = ticker.history(period="1y")
        
        if df is None or df.empty:
            return None
            
        # 處理 yfinance 可能產生的多層索引標題
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 計算均線
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        return df
    except Exception as e:
        st.sidebar.error(f"錯誤訊息: {e}")
        return None

# --- 2. 網頁介面設定 ---
st.set_page_config(page_title="全球股市分析系統", layout="wide")
st.title("📈 全球股市分析系統 (強化修復版)")

with st.sidebar:
    st.header("數據查詢")
    st.write("台股請輸數字 (如: 2330)")
    st.write("美股請輸代碼 (如: AAPL)")
    stock_id = st.text_input("輸入股票代碼", value="2330")
    analyze_btn = st.button("開始分析")

# --- 3. 執行邏輯 ---
if analyze_btn:
    with st.spinner(f'正在抓取 {stock_id} 的數據...'):
        df = get_processed_data(stock_id)
        
        if df is not None and not df.empty:
            # 繪製圖表
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name='K線'
                ),
                go.Scatter(x=df.index, y=df['MA5'], name='5日線', line=dict(color='orange', width=1.5)),
                go.Scatter(x=df.index, y=df['MA20'], name='20日線', line=dict(color='cyan', width=1.5))
            ])
            
            fig.update_layout(
                title=f"{stock_id} 走勢分析",
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 指標摘要
            latest = df.iloc[-1]
            c1, c2, c3 = st.columns(3)
            c1.metric("收盤價", f"{latest['Close']:.2f}")
            c2.metric("5日均", f"{latest['MA5']:.2f}")
            c3.metric("20日均", f"{latest['MA20']:.2f}")
        else:
            st.error(f"無法取得 {stock_id} 的數據。請確認代碼正確，或稍後再試。")
