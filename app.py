import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 配置區：請貼上你的 Token ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" # 記得保留雙引號
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

@st.cache_data(ttl=3600)
def fetch_data(dataset, stock_id):
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    parameter = {
        "dataset": dataset, 
        "data_id": stock_id, 
        "start_date": start_date, 
        "end_date": end_date, 
        "token": FINMIND_TOKEN
    }
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        res_data = res.json()
        if 'data' in res_data:
            return pd.DataFrame(res_data['data'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 2. 網頁介面 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("📈 專業台股分析系統 (整合穩定版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('正在分析指標...'):
        # 直接抓取數據，不依賴外部檔案
        df = fetch_data("TaiwanStockPrice", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # --- 採用你原本要求的專業指標算法 ---
            # 1. 均線 (MA5, MA10, MA20)
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA10'] = df['close'].rolling(10).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            
            # 2. KD (9, 3, 3)
            low_9 = df['min'].rolling(9).min()
            high_9 = df['max'].rolling(9).max()
            rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
            df['K'] = rsv.ewm(com=2).mean()
            df['D'] = df['K'].ewm(com=2).mean()
            
            # 3. MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['DIF'] = exp1 - exp2
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
            df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2

            # --- 繪圖邏輯 (台股紅漲綠跌) ---
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.03, 
                                row_heights=[0.5, 0.15, 0.15, 0.2])

            # A. K線與均線
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                name='K線', increasing_line_color='#FF0000', decreasing_line_color='#00FF00',
                increasing_fillcolor='#FF0000', decreasing_fillcolor='#00FF00'
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1.2)), row=1, col=1)

            # B. 成交量 (與K線同步變色)
            v_colors = ['#FF0000' if c >= o else '#00FF00' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)

            # C. KD線
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K值', line=dict(color='orange')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D值', line=dict(color='dodgerblue')), row=3, col=1)

            # D. MACD
            m_colors = ['#FF0000' if x >= 0 else '#00FF00' for x in df['MACD_hist']]
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=4, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # 單獨顯示法人資料
            st.subheader("🏛️ 法人買賣動態")
            inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
            if not inst_df.empty:
                st.dataframe(inst_df.tail(10), use_container_width=True)
        else:
            st.error("查無數據，請確認代碼或 Token 是否正確。")
