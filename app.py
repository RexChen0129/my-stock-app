import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. 終極抗封鎖數據抓取函數 ---
def get_processed_data(stock_id):
    if stock_id.isdigit():
        target = f"{stock_id}.TW"
    else:
        target = stock_id.upper()
        
    try:
        # 使用 download 並強制單線程，避免被判定為攻擊
        df = yf.download(
            target, 
            period="1y", 
            interval="1d", 
            auto_adjust=True, 
            progress=False,
            threads=False  # 關鍵：關閉多執行緒，比較不會被封
        )
        
        if df is None or df.empty:
            return None
            
        # 拍平多層標題
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 計算指標
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        return df
    except Exception as e:
        st.error(f"連線異常: {e}")
        return None

# --- 2. 介面設計 ---
st.set_page_config(page_title="全球股市分析系統", layout="wide")
st.title("📊 全球股市分析 (抗封鎖穩定版)")

with st.sidebar:
    st.header("數據查詢")
    stock_id = st.text_input("輸入股票代碼 (例: 2330 或 TSLA)", value="2330")
    analyze_btn = st.button("開始分析")
    st.divider()
    st.caption("註：若出現 Too Many Requests，請等候 5 分鐘再試。")

# --- 3. 執行邏輯 ---
if analyze_btn:
    with st.spinner(f'正在向數據庫請求 {stock_id} 資訊...'):
        df = get_processed_data(stock_id)
        
        if df is not None and not df.empty:
            # 畫 K 線圖
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name='K線'
                ),
                go.Scatter(x=df.index, y=df['MA5'], name='5日均線', line=dict(color='#FFA500', width=1.5)),
                go.Scatter(x=df.index, y=df['MA20'], name='20日均線', line=dict(color='#00CED1', width=1.5))
            ])
            
            fig.update_layout(
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=40, b=10),
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 數據儀表板
            latest = df.iloc[-1]
            c1, c2, c3 = st.columns(3)
            c1.metric("當前股價", f"{latest['Close']:.2f}")
            c2.metric("5MA", f"{latest['MA5']:.2f}")
            c3.metric("20MA", f"{latest['MA20']:.2f}")
        else:
            st.warning("目前暫時無法取得數據。這通常是 Yahoo 伺服器拒絕連線，請嘗試輸入其他代碼，或幾分鐘後再按一次。")
