import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置 (請填入你的 Token) ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_full_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN})
        df = pd.DataFrame(res_p.json().get('data', []))
        
        # 抓取法人
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN})
        inst_data = res_i.json().get('data', [])

        if df.empty: return None

        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 💡 強制補齊法人欄位，避免圖表跑不出來
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 加總當天所有法人數據
            net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = net.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0
            
        return df
    except:
        return None

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")

# 💡 這是靈魂：強制讓外層容器出現橫向滾動條
st.markdown("""
    <style>
    /* 這裡鎖定 Streamlit 的區塊，強迫它不准縮小圖表 */
    .stPlotlyChart {
        overflow-x: auto !important;
        background-color: #0E1117;
    }
    /* 自定義捲軸樣式 */
    div[data-testid="stHorizontalBlock"] {
        overflow-x: auto;
    }
    ::-webkit-scrollbar {
        height: 12px;
    }
    ::-webkit-scrollbar-thumb {
        background: #888; 
        border-radius: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #222;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📈 專業控盤系統 (捲軸強制開啟版)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_full_data(stock_id)
    
    if df is not None:
        # 💡 寬度設定：每根 K 線 25px，一年約 250 個交易日 = 6250px
        # 這麼寬，瀏覽器就「不得不」生出捲軸給你拉
        total_w = len(df) * 25
        
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, 
            vertical_spacing=0.1, 
            row_heights=[0.6, 0.4],
            subplot_titles=("K線", "法人買賣超")
        )

        # K線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], 
            low=df['min'], close=df['close'], name='K線'
        ), row=1, col=1)
        
        # 法人買賣超 (柱狀圖)
        colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Inst_Net'], name='法人', marker_color=colors
        ), row=2, col=1)

        fig.update_layout(
            width=total_w, # 設定超寬度
            height=700,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode=False,
            showlegend=False,
            margin=dict(l=10, r=10, t=50, b=50)
        )

        # 顯示圖表，use_container_width 必須為 False
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
        
    else:
        st.error("❌ 沒抓到資料！請確認 1. API Token 是否填寫 2. 代碼是否正確")
