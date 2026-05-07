import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_complete_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        
        df = pd.DataFrame(res_p.get('data', []))
        if df.empty: return None
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 指標計算
        inst_data = res_i.get('data', [])
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = net.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0
            
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
    except:
        return None

# --- 2. CSS：強制灰色橫向捲軸樣式 ---
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
        height: 15px;
        display: block !important;
    }
    .force-scroll::-webkit-scrollbar-thumb {
        background: #888888 !important;
        border-radius: 10px;
    }
    .force-scroll::-webkit-scrollbar-track {
        background: #222;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📈 全能專業控盤系統")
stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_complete_data(stock_id)
    if df is not None:
        # 💡 重點：設定每一根 K 線佔 40 像素，確保夠大，並觸發捲軸
        chart_width = len(df) * 40
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線(5/10/20MA)", "2. 成交量", "3. 法人買賣超", "4. KD指標", "5. MACD指標")
        )

        # 1. K線 + 懸停數據提示 (hovertool)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            name='K線', hovertext=df.apply(lambda x: f"開:{x['open']}<br>高:{x['max']}<br>低:{x['min']}<br>收:{x['close']}", axis=1)
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta')), row=1, col=1)

        # 2. 成交量
        v_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)

        # 3. 法人買賣超 (確保一定會顯示)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人', marker_color=i_colors), row=3, col=1)

        # 4. KD 指標
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD 指標
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(
            width=max(chart_width, 1200), # 最小 1200，資料多就撐開
            height=1100,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified', # 滑鼠移過去顯示整排數據
            margin=dict(l=10, r=10, t=50, b=50)
        )

        # 恢復工具欄 (放大鏡、縮放)
        st.write('<div class="force-scroll">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': True, 'scrollZoom': True})
        st.write('</div>', unsafe_allow_html=True)
        
    else:
        st.error("查無資料，請確認 Token。")
