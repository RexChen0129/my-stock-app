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
        # 抓取股價與法人資料
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        
        df = pd.DataFrame(res_p.get('data', []))
        if df.empty: return None
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 指標 3：法人買賣超處理
        inst_data = res_i.get('data', [])
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = net.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0
            
        # 指標 1, 4, 5：MA, KD, MACD 計算
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        # KD (9, 3, 3)
        low_9 = df['min'].rolling(9).min()
        high_9 = df['max'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        # MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = exp1 - exp2
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except:
        return None

# --- 2. CSS：強制產生灰色捲軸 ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .scroll-box {
        overflow-x: scroll !important; /* 強制水平捲軸 */
        overflow-y: hidden;
        width: 100%;
        background-color: #0E1117;
        border: 1px solid #444;
    }
    /* 這裡就是你要的灰色一條 */
    .scroll-box::-webkit-scrollbar {
        height: 14px;
        display: block !important;
    }
    .scroll-box::-webkit-scrollbar-thumb {
        background: #888888 !important;
        border-radius: 7px;
    }
    .scroll-box::-webkit-scrollbar-track {
        background: #222;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 全指標控盤系統 (強制灰色捲軸版)")
stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_complete_data(stock_id)
    if df is not None:
        # 💡 重點：設定 5000 像素寬，確保 K 線不擠壓且一定會出現捲軸
        chart_width = 5000 
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
            row_heights=[0.4, 0.1, 0.1, 0.15, 0.25],
            subplot_titles=("1.K線與三條均線", "2.成交量", "3.法人買賣超", "4.KD指標", "5.MACD指標")
        )

        # 1. K線 (Candlestick) + 三條 MA
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1)), row=1, col=1)

        # 2. 成交量
        v_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)

        # 3. 法人買賣超
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人', marker_color=i_colors), row=3, col=1)

        # 4. KD 線
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD 線
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(
            width=chart_width, height=1000, template="plotly_dark",
            xaxis_rangeslider_visible=False, dragmode=False, showlegend=False,
            margin=dict(l=10, r=10, t=40, b=40)
        )

        # --- 3. 渲染：用 CSS 盒子強制包住圖表 ---
        st.write('<div class="scroll-box">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
        st.write('</div>', unsafe_allow_html=True)
        
    else:
        st.error("查無資料，請確認 Token 或代碼。")
