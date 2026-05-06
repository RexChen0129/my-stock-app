import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 配置區 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" # 請確保引號留著
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

@st.cache_data(ttl=3600)
def fetch_data(dataset, stock_id):
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    parameter = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
    res = requests.get(FINMIND_URL, params=parameter)
    return pd.DataFrame(res.json()['data'])

# --- 1. 介面設定 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("📈 專業台股分析系統 (台股配色+全指標版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('正在讀取各項專業指標...'):
        # 抓取股價與法人資料
        df = fetch_data("TaiwanStockPrice", stock_id)
        inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
        
        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # --- 計算指標 ---
            # 1. MA 線
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            df['MA60'] = df['close'].rolling(60).mean()
            
            # 2. KD 線
            low_list = df['min'].rolling(9).min()
            high_list = df['max'].rolling(9).max()
            rsv = (df['close'] - low_list) / (high_list - low_list) * 100
            df['K'] = rsv.ewm(com=2).mean()
            df['D'] = df['K'].ewm(com=2).mean()
            
            # 3. MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['DIF'] = exp1 - exp2
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
            df['MACD'] = (df['DIF'] - df['DEA']) * 2

            # --- 建立多圖層圖表 ---
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, 
                                row_heights=[0.5, 0.15, 0.15, 0.2])

            # A. K 線圖 (台股配色：漲紅跌綠)
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                name='K線', increasing_line_color='#FF0000', decreasing_line_color='#00FF00',
                increasing_fillcolor='#FF0000', decreasing_fillcolor='#00FF00'
            ), row=1, col=1)
            
            # 三條 MA 線
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='white', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='yellow', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name='60MA', line=dict(color='magenta', width=1)), row=1, col=1)

            # B. 成交量
            fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color='gray'), row=2, col=1)

            # C. KD 線
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K值', line=dict(color='cyan')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D值', line=dict(color='orange')), row=3, col=1)

            # D. MACD
            fig.add_trace(go.Bar(x=df.index, y=df['MACD'], name='MACD柱狀圖'), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=4, col=1)

            # 設定佈局
            fig.update_layout(height=900, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            st.success(f"{stock_id} 分析完成！")
        else:
            st.error("讀取失敗，請檢查代碼或 Token。")
