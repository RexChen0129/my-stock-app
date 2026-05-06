import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 配置區 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

@st.cache_data(ttl=3600)
def fetch_data(dataset, stock_id):
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    parameter = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        res_data = res.json()
        return pd.DataFrame(res_data['data']) if 'data' in res_data else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 介面設定 ---
st.set_page_config(page_title="專業台股分析系統 (互動加強版)", layout="wide")
st.title("⚡ 專業股市分析系統 (互動加強版)")

stock_id = st.sidebar.text_input("請輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("點擊開始分析")

if analyze_btn:
    with st.spinner('正在分析指標...'):
        df = fetch_data("TaiwanStockPrice", stock_id)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # --- 算法邏輯 (維持與 v2 相同) ---
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA10'] = df['close'].rolling(10).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            low_9 = df['min'].rolling(9).min()
            high_9 = df['max'].rolling(9).max()
            rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
            df['K'] = rsv.ewm(com=2).mean()
            df['D'] = df['K'].ewm(com=2).mean()
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['DIF'] = exp1 - exp2
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
            df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2

            # --- 繪圖設定 ---
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.02, 
                row_heights=[0.5, 0.15, 0.15, 0.2],
                # 在每一層左側加上子圖標題 (註釋)
                subplot_titles=("【K線 / 均線分析】", "【成交量 (法人估計)】", "【KD 指標】", "【MACD 指標】")
            )

            # 1. K線：客製化 hovertemplate 顯示中文標籤
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                name='價格資訊',
                increasing_line_color='#FF0000', decreasing_line_color='#00FF00',
                increasing_fillcolor='#FF0000', decreasing_fillcolor='#00FF00',
                hovertemplate="日期: %{x}<br>開盤: %{open}<br>最高: %{high}<br>最低: %{low}<br>收盤: %{close}<extra></extra>"
            ), row=1, col=1)

            # 均線
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1.2), hoverinfo='skip'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan', width=1.2), hoverinfo='skip'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1.5), hoverinfo='skip'), row=1, col=1)

            # 2. 成交量
            v_colors = ['#FF0000' if c >= o else '#00FF00' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(
                x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors,
                hovertemplate="日期: %{x}<br>成交量: %{y}<extra></extra>"
            ), row=2, col=1)

            # 3. KD 線
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K值', line=dict(color='orange'), hovertemplate="K: %{y:.2f}"), row=3, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D值', line=dict(color='dodgerblue'), hovertemplate="D: %{y:.2f}"), row=3, col=1)

            # 4. MACD
            m_colors = ['#FF0000' if x >= 0 else '#00FF00' for x in df['MACD_hist']]
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='柱狀體', marker_color=m_colors), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=4, col=1)

            # --- 佈局優化 ---
            fig.update_layout(
                height=1000, 
                template="plotly_dark", 
                # 💡 核心修正：開啟 X 軸滑桿，實現拖曳與縮放
                xaxis_rangeslider_visible=True, 
                xaxis_rangeslider_thickness=0.05,
                showlegend=True,
                hovermode="x unified", # 同一時間軸的數據會整合成一個框顯示
                margin=dict(t=50, b=50, l=50, r=50)
            )
            
            # 設定左側標題的位置與樣式
            for i in fig['layout']['annotations']:
                i['font'] = dict(size=16, color='#FFFFFF', family="Arial Black")
                i['x'] = 0 # 將標題靠左
                i['xanchor'] = 'left'

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f"找不到代碼 {stock_id} 的數據。")
