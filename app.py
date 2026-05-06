import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 配置區 ---
FINMIND_TOKEN = "你的_API_TOKEN_貼在這裡" 
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

@st.cache_data(ttl=3600)
def fetch_data(dataset, stock_id):
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    parameter = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        res_data = res.json()
        if 'data' in res_data:
            return pd.DataFrame(res_data['data'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 介面設定 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("📈 專業台股分析系統 (台股配色+全指標版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('正在分析各項指標...'):
        df = fetch_data("TaiwanStockPrice", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 技術指標計算
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            df['MA60'] = df['close'].rolling(60).mean()
            
            # KD
            low_9 = df['min'].rolling(9).min()
            high_9 = df['max'].rolling(9).max()
            df['K'] = 0.0
            df['D'] = 0.0
            rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
            df['K'] = rsv.ewm(com=2).mean()
            df['D'] = df['K'].ewm(com=2).mean()
            
            # MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['DIF'] = exp1 - exp2
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
            df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2

            # 建立多層圖表 (K線, 成交量, KD, MACD)
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.02, 
                                row_heights=[0.5, 0.15, 0.15, 0.2])

            # 1. K線 (漲紅跌綠)
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                name='K線', increasing_line_color='#FF0000', decreasing_line_color='#00FF00',
                increasing_fillcolor='#FF0000', decreasing_fillcolor='#00FF00'
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='white', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='yellow', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name='60MA', line=dict(color='magenta', width=1)), row=1, col=1)

            # 2. 成交量 (與 K 線同色)
            colors = ['#FF0000' if c >= o else '#00FF00' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=colors), row=2, col=1)

            # 3. KD
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='cyan')), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='orange')), row=3, col=1)

            # 4. MACD
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color='gray'), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=4, col=1)

            fig.update_layout(height=1000, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # 法人買賣單獨顯示 (避免 API 沒資料時導致全圖崩潰)
            st.subheader("🏛️ 法人買賣超資訊")
            inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
            if not inst_df.empty:
                st.dataframe(inst_df.tail(10), use_container_width=True)
            else:
                st.info("暫無法人買賣詳細數據。")
        else:
            st.error("找不到該代碼的數據，請確認代碼是否正確或 Token 是否有效。")
