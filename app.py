import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_stock_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        # 抓取股價與法人
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        
        df = pd.DataFrame(res_p.get('data', []))
        if df.empty: return None
        
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 處理法人買賣超 (確保 Inst_Net 欄位一定有值)
        inst_data = res_i.get('data', [])
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = net.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0
            
        # 計算 KD / MACD
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        low_9 = df['min'].rolling(9).min()
        high_9 = df['max'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        return df
    except:
        return None

# --- 2. 強制捲軸的 CSS (這是解決問題的關鍵) ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    /* 強迫產生橫向捲軸的容器 */
    .force-scroll {
        overflow-x: scroll !important;
        overflow-y: hidden;
        width: 100%;
        background-color: #0E1117;
        border: 1px solid #444;
        margin-bottom: 20px;
    }
    /* 客製化灰色捲軸條 */
    .force-scroll::-webkit-scrollbar {
        height: 15px !important;
        display: block !important;
    }
    .force-scroll::-webkit-scrollbar-thumb {
        background: #888 !important; /* 你要的灰色條 */
        border-radius: 10px;
    }
    .force-scroll::-webkit-scrollbar-track {
        background: #222 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 橫向捲軸控盤系統 (CSS 強制版)")
stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_stock_data(stock_id)
    if df is not None:
        # 💡 重點：設定圖表寬度為 5000 像素，強迫它超出螢幕
        chart_w = 5000 
        
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            row_heights=[0.5, 0.25, 0.25],
            subplot_titles=("K線與均線", "法人買賣超", "KD指標")
        )

        # 繪製各項資料
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold')), row=1, col=1)
        
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人'), row=2, col=1)
        
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=3, col=1)

        fig.update_layout(
            width=chart_w, # 這裡設定 5000 
            height=800,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode=False, # 禁止圖表內縮放
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=40)
        )

        # --- 3. 渲染：用 HTML 容器包住 Plotly ---
        # 這是唯一能確保長出「灰色一條」的方法
        st.write('<div class="force-scroll">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
        st.write('</div>', unsafe_allow_html=True)
        
    else:
        st.error("找不到資料，請檢查 Token。")
