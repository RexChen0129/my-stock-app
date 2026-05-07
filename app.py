import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 配置與數據抓取 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_stock_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價 (包含成交量)
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # 抓取法人買賣超 (修正對齊)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_df = pd.DataFrame(res_i['data'])
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 加總三大法人每日買賣淨額
            inst_daily = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum()).rename('Inst_Net')
            df = df.join(inst_daily, how='left').fillna({'Inst_Net': 0})
        else:
            df['Inst_Net'] = 0
            
        return df
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
        return None

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")
st.title("專業控盤系統 (功能全開版)")

# 使用 CSS 強制產生橫向捲軸，並確保內部圖表可以被展開
st.markdown("""
    <style>
    .plot-container { overflow-x: auto !important; }
    .main { background-color: #0E1117; }
    </style>
""", unsafe_allow_html=True)

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
if st.sidebar.button("分析"):
    df = fetch_stock_data(stock_id)
    if df is not None:
        # 建立 5 個子圖表空間
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.4, 0.1, 0.15, 0.15, 0.2],
            subplot_titles=("K線與均線", "成交量", "法人買賣超", "KD指標", "MACD")
        )

        # 1. K線圖 (設定固定的寬度，讓它不會縮得太小)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], 
            low=df['min'], close=df['close'], name='K線'
        ), row=1, col=1)

        # 2. 成交量
        vol_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)

        # 3. 法人買賣超 (修正版)
        inst_colors = ['red' if val >= 0 else 'green' for val in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人淨額', marker_color=inst_colors), row=3, col=1)

        # 4. KD 指標 (示意略)
        # 5. MACD (示意略)

        # 佈局與工具列設定
        fig.update_layout(
            height=1000,
            width=2500, # 💡 這裡設定大寬度，讓 K 線變粗並觸發捲軸
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            showlegend=False,
            # 開啟所有的操作工具
            dragmode='pan', 
            hovermode='x unified'
        )

        # 💡 重點：顯示 Plotly 內建的放大/縮小按鈕
        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True, # 強制顯示工具列
            'scrollZoom': True,     # 允許滑鼠滾輪縮放
            'modeBarButtonsToAdd': [
                'drawline', 'drawopenpath', 'drawclosedpath', 
                'drawcircle', 'drawrect', 'eraseshape'
            ],
            'displaylogo': False
        })
