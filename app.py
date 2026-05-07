import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 資料獲取與處理 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" # 建議填入您的 Token

@st.cache_data(ttl=300)
def fetch_stock_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價數據
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p.get('data', []))
        if df.empty: return None
        
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 抓取法人買賣超
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 整合當日所有法人合計買賣超
            inst_sum = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = inst_sum.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0
            
        # 計算技術指標
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        # KD 指標 (固定線條寬度)
        low_9 = df['min'].rolling(9).min()
        high_9 = df['max'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        return df
    except Exception as e:
        st.error(f"數據讀取錯誤: {e}")
        return None

# --- 2. CSS 介面優化：強制捲軸顯示 ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .scroll-container {
        overflow-x: auto !important;
        width: 100%;
        background-color: #0E1117;
        border: 2px solid #333;
        padding: 10px;
        margin-bottom: 30px;
    }
    /* 強制顯示灰色捲軸 */
    .scroll-container::-webkit-scrollbar {
        height: 14px;
        display: block !important;
    }
    .scroll-container::-webkit-scrollbar-thumb {
        background: #888 !important;
        border-radius: 7px;
    }
    .scroll-container::-webkit-scrollbar-track {
        background: #333;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 專業控盤系統 (K線放大橫向捲軸版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
if st.sidebar.button("執行分析"):
    df = fetch_stock_data(stock_id)
    
    if df is not None:
        # 【核心邏輯】計算圖表總寬度，強制放大 K 線
        # 設定每根 K 線佔 40px，讓它在大天數時必須產生捲軸
        total_bars = len(df)
        min_chart_width = total_bars * 40 
        
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, 
            vertical_spacing=0.05,
            row_heights=[0.6, 0.2, 0.2],
            subplot_titles=("K線與均線 (請使用下方捲軸左右滑動)", "法人買賣超", "KD指標")
        )

        # 1. K 線圖 (放大樣式)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            name='K線', increasing_line_color='#FF3333', decreasing_line_color='#00AA00'
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='yellow', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1.5)), row=1, col=1)

        # 2. 法人買賣超 (柱狀圖)
        colors = ['#FF3333' if x >= 0 else '#00AA00' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Inst_Net'], name='法人淨買賣',
            marker_color=colors
        ), row=2, col=1)

        # 3. KD 指標
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K線', line=dict(color='orange', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D線', line=dict(color='dodgerblue', width=2)), row=3, col=1)

        # 圖表佈局設定
        fig.update_layout(
            width=max(min_chart_width, 1200), # 強制寬度，確保捲軸出現
            height=850,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode=False, # 關閉滑鼠縮放，改用捲軸控制
            hovermode="x unified",
            showlegend=False,
            margin=dict(l=50, r=50, t=50, b=50)
        )

        # 禁用坐標軸自動縮放，維持 K 線大小
        fig.update_xaxes(type='category', tickformat='%m-%d', fixedrange=True)
        fig.update_yaxes(fixedrange=True)

        # 放置於自定義捲軸容器中
        st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)
