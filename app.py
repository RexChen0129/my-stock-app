import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置區 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" # 👈 在這裡填入你的 API KEY

@st.cache_data(ttl=3600)
def fetch_full_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # A. 抓取股價
    res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN})
    df = pd.DataFrame(res_p.json().get('data', []))
    
    # B. 抓取法人
    res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN})
    inst_df = pd.DataFrame(res_i.json().get('data', []))

    if df.empty: return None

    # 數據預處理
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # 計算法人淨買賣 (修正 Inst_Net KeyError)
    if not inst_df.empty:
        inst_df['date'] = pd.to_datetime(inst_df['date'])
        inst_net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
        df['Inst_Net'] = inst_net.reindex(df.index).fillna(0)
    else:
        df['Inst_Net'] = 0

    # 計算 KD 指標
    low_9 = df['min'].rolling(9).min()
    high_9 = df['max'].rolling(9).max()
    rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()

    # 計算 MACD 指標
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2
    
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    
    return df

# --- 2. 介面與 CSS ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .scroll-wrapper {
        overflow-x: auto !important;
        width: 100%;
        background-color: #0E1117;
    }
    .scroll-wrapper::-webkit-scrollbar {
        height: 14px; /* 設定捲軸厚度 */
    }
    .scroll-wrapper::-webkit-scrollbar-thumb {
        background: #888888; /* 灰色條 */
        border-radius: 7px;
    }
    .scroll-wrapper::-webkit-scrollbar-track {
        background: #262730;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📈 專業控盤系統 (獨立灰色捲軸)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = fetch_full_data(stock_id)
    
    if df is not None:
        # 💡 強制設定超寬度 (每根 K 線 25px)，這樣下方才會出現獨立灰色拉條
        total_w = len(df) * 25
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.4, 0.1, 0.1, 0.1, 0.3],
            subplot_titles=("K線與均線", "成交量", "法人買賣超", "KD指標", "MACD指標")
        )

        # A. K線與均線
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta')), row=1, col=1)
        
        # B. 成交量
        v_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='量', marker_color=v_colors), row=2, col=1)
        
        # C. 法人買賣超
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人', marker_color=i_colors), row=3, col=1)
        
        # D. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)
        
        # E. MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(
            width=total_w, height=900, template="plotly_dark",
            xaxis_rangeslider_visible=False, dragmode=False, showlegend=False
        )

        # --- 渲染 HTML 容器與捲軸 ---
        st.write('<div class="scroll-wrapper">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
        st.write('</div>', unsafe_allow_html=True)
        
    else:
        st.error("API 抓取失敗，請檢查 Token 或代碼。")
