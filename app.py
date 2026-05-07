import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置與資料抓取 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_complete_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        # 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p.get('data', []))
        if df.empty: return None
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 抓取法人買賣超 (修正邏輯，確保 Inst_Net 欄位一定存在)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 計算三大法人合計買賣超
            net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = net.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0 # 若無資料則補0，防止 KeyError
            
        # 計算技術指標
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        # KD
        low_9 = df['min'].rolling(9).min()
        high_9 = df['max'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = exp1 - exp2
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2
        return df
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return None

# --- 2. CSS：強制橫向捲軸樣式 ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .force-scroll {
        overflow-x: scroll !important;
        width: 100%;
        background-color: #0E1117;
        border: 1px solid #444;
        margin-bottom: 20px;
    }
    .force-scroll::-webkit-scrollbar {
        height: 12px;
        display: block !important;
    }
    .force-scroll::-webkit-scrollbar-thumb {
        background: #666 !important;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📈 專業控盤系統 (僅工具列縮放版)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_complete_data(stock_id)
    if df is not None:
        # 強制每根 K 線寬度，確保捲軸觸發
        chart_width = len(df) * 35
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.4, 0.1, 0.1, 0.2, 0.2],
            subplot_titles=("K線與均線", "成交量", "法人買賣超", "KD指標", "MACD指標")
        )

        # 1. K線 + 懸停數據提示 (hovertool)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            name='K線', hoverinfo="all" # 滑鼠移入出現開高低收
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1)), row=1, col=1)

        # 2. 成交量
        v_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)

        # 3. 法人買賣超 (修正欄位 KeyError 問題)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人買賣', marker_color=i_colors), row=3, col=1)

        # 4. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(
            width=max(chart_width, 1000),
            height=1000,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            showlegend=False,
            margin=dict(l=10, r=10, t=30, b=10),
            # --- 重要：鎖定圖表，禁止滑鼠拖拽放大 ---
            dragmode=False, 
            hovermode='x unified'
        )
        
        # 針對所有坐標軸禁用滑鼠縮放 (只能用工具列放大鏡)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)

        # 輸出到 Streamlit
        st.write('<div class="force-scroll">', unsafe_allow_html=True)
        # config 中保留 displayModeBar (放大鏡) 但關閉 scrollZoom
        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True, 
            'scrollZoom': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        })
        st.write('</div>', unsafe_allow_html=True)
