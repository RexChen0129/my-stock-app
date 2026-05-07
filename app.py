import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 資料抓取與合併 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_all_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 法人
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_df = pd.DataFrame(res_i.get('data', []))
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 💡 核心：使用 merge_asof 確保日期絕對對齊
            inst_daily = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum()).reset_index()
            inst_daily = inst_daily.sort_values('date')
            df = pd.merge_asof(df, inst_daily, on='date', direction='nearest')
            df.rename(columns={'net': 'Inst_Net'}, inplace=True)
            df['Inst_Net'] = df['Inst_Net'].fillna(0)
        else:
            df['Inst_Net'] = 0

        # 指標計算
        df.set_index('date', inplace=True)
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean(); df['D'] = df['K'].ewm(com=2).mean()
        e12 = df['close'].ewm(span=12, adjust=False).mean(); e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD_h'] = (e12 - e26) - (e12 - e26).ewm(span=9, adjust=False).mean()
        
        return df
    except: return None

# --- 2. 介面與 CSS ---
st.set_page_config(layout="wide")
st.title("📊 專業控盤系統 (滾輪縮放/隱藏按鈕版)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("分析"):
    df = fetch_all_data(stock_id)
    if df is not None:
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.6, 0.2, 0.2],
            subplot_titles=("K線", "法人買賣超", "KD指標")
        )

        # 1. K線
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                                     increasing_line_color='red', decreasing_line_color='green', name='K線'), row=1, col=1)

        # 2. 法人買賣超 (柱狀圖，買紅賣綠)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人淨額'), row=2, col=1)

        # 3. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=3, col=1)

        # 佈局設定
        fig.update_layout(
            height=900, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode='zoom', # 預設為縮放模式
            hovermode='x unified'
        )
        
        # 💡 強制讓法人 Y 軸自適應数据的起伏，解除壓扁狀態
        fig.update_yaxes(autorange=True, fixedrange=False, row=2, col=1)

        st.plotly_chart(fig, use_container_width=True, config={
            'displayModeBar': True,
            'displaylogo': False,
            # 💡 重點：開啟滾輪縮放，但移除所有縮放按鈕
            'scrollZoom': True,           
            'modeBarButtonsToRemove': [
                'zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'select2d', 'lasso2d'
            ],
        })
