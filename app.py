import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 核心數據處理 (確保欄位絕對存在) ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def get_all_indicators(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # A. 股價數據
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # B. 法人買賣超 (預防 KeyError)
        df['Inst_Net'] = 0.0
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            inst_sum = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df.update(inst_sum.rename('Inst_Net'))

        # C. 計算 MA (5/10/20)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()

        # D. 計算 KD 指標
        low_min = df['min'].rolling(9).min()
        high_max = df['max'].rolling(9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()

        # E. 計算 MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = exp1 - exp2
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['DIF'] - df['DEA']

        return df
    except Exception as e:
        st.error(f"數據加載出錯: {e}")
        return None

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")
st.title("📊 專業全指標控盤系統 (5合1最終修正版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
if st.sidebar.button("執行全指標分析"):
    df = get_all_indicators(stock_id)
    if df is not None:
        # 建立 5 個子圖
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, 
            vertical_spacing=0.02,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線與均線", "2. 成交量", "3. 法人買賣超", "4. KD指標", "5. MACD")
        )

        # 🎨 顏色邏輯：漲紅跌綠
        # K線顏色
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            increasing_line_color='red', decreasing_line_color='green', name='K線'
        ), row=1, col=1)
        
        # 均線
        for ma, color in zip(['MA5', 'MA10', 'MA20'], ['white', 'yellow', 'magenta']):
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(width=1.5, color=color)), row=1, col=1)

        # 🎨 成交量顏色：今日收盤 > 昨日收盤 為紅
        vol_colors = ['red' if df['close'].iloc[i] >= df['close'].iloc[i-1] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)

        # 🎨 法人買賣超顏色：正數紅、負數綠
        inst_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=inst_colors, name='法人淨額'), row=3, col=1)

        # 4. KD線
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K線', line=dict(color='skyblue')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D線', line=dict(color='orange')), row=4, col=1)

        # 5. MACD (包含柱狀圖紅綠色)
        macd_colors = ['red' if x >= 0 else 'green' for x in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=macd_colors, name='MACD柱狀'), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        # 圖表整體佈局與縮放
        fig.update_layout(
            height=1200, width=1600,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode='pan',
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True, config={
            'displayModeBar': True,
            'scrollZoom': True,
            'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'autoScale2d']
        })
