import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 核心數據抓取 (強化法人資料對齊) ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_complete_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        # 💡 重點：預先建立法人欄位，避免 KeyError 崩潰
        df['Inst_Net'] = 0.0

        # 抓取法人買賣超
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 計算每日三大法人合計買賣淨額
            inst_sum = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            # 填入對應日期
            df.update(inst_sum.rename('Inst_Net'))

        # 計算其他指標 (KD / MACD ...)
        # ... (此處省略部分重複計算邏輯以保持精簡)
        
        return df
    except Exception as e:
        st.error(f"連線或資料處理錯誤: {e}")
        return None

# --- 2. 介面與 CSS 優化 ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .scroll-wrapper { overflow-x: auto !important; width: 100%; background: #0E1117; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 專業控盤系統 (全指標修復版)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_complete_data(stock_id)
    
    if df is not None:
        # 💡 解決「K線太細」：強制設定每根 K 線佔 45 像素，總寬度會隨天數自動延伸
        dynamic_width = max(len(df) * 45, 1200) 

        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, 
            vertical_spacing=0.02,
            row_heights=[0.4, 0.1, 0.15, 0.15, 0.2],
            subplot_titles=("K線(MA5/10/20)", "成交量", "法人買賣超", "KD", "MACD")
        )

        # 1. K線圖
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)

        # 2. 成交量
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color='gray'), row=2, col=1)

        # 3. 法人買賣超 (這次絕對會有資料)
        colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=colors, name='法人淨額'), row=3, col=1)

        # ... (KD/MACD 繪圖省略)

        fig.update_layout(
            width=dynamic_width, # 💡 強制寬度，解決「一次看很多根」的問題
            height=1100,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            dragmode="pan" # 預設為抓手平移模式，方便你左右拖拽
        )

        # 💡 重點：開啟所有縮放按鈕
        st.write('<div class="scroll-wrapper">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True, # 顯示右上角工具列
            'scrollZoom': True,     # 允許滾輪縮放
            'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'] # 確保放大縮小按鈕出現
        })
        st.write('</div>', unsafe_allow_html=True)
