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
    # 💡 抓取 365 天數據，這樣左右拖曳才有「更前面」的資料可以看
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
st.set_page_config(page_title="台股分析系統 (專業拖曳版)", layout="wide")
st.title("📊 專業台股分析系統 (全數據互動版)")

stock_id = st.sidebar.text_input("請輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("點擊開始分析")

if analyze_btn:
    with st.spinner('正在讀取一整年份數據...'):
        # 1. 抓取價格
        df = fetch_data("TaiwanStockPrice", stock_id)
        # 2. 抓取法人 (分開抓取)
        inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 處理法人數據：合併到主表
            if not inst_df.empty:
                inst_df['date'] = pd.to_datetime(inst_df['date'])
                inst_summary = inst_df.groupby('date')['buy'].sum() - inst_df.groupby('date')['sell'].sum()
                df['Inst_Net'] = inst_summary
                df['Inst_Net'] = df['Inst_Net'].fillna(0)
            else:
                df['Inst_Net'] = 0

            # --- 指標計算 ---
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

            # --- 繪圖：分為 5 層 (K線, 成交量, 法人, KD, MACD) ---
            fig = make_subplots(
                rows=5, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.02, 
                row_heights=[0.4, 0.12, 0.12, 0.12, 0.24],
                subplot_titles=("【K線 / 均線】", "【成交量】", "【法人買賣超】", "【KD 指標】", "【MACD 指標】")
            )

            # A. K線
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                name='價格', increasing_line_color='#FF0000', decreasing_line_color='#00FF00',
                increasing_fillcolor='#FF0000', decreasing_fillcolor='#00FF00'
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1.5)), row=1, col=1)

            # B. 成交量 (修正長條圖)
            v_colors = ['#FF0000' if c >= o else '#00FF00' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(
                x=df.index, y=df['Trading_Volume'], name='成交量', 
                marker_color=v_colors, opacity=0.8
            ), row=2, col=1)

            # C. 法人買賣超 (獨立分開)
            i_colors = ['#FF0000' if x >= 0 else '#00FF00' for x in df['Inst_Net']]
            fig.add_trace(go.Bar(
                x=df.index, y=df['Inst_Net'], name='法人買賣', 
                marker_color=i_colors
            ), row=3, col=1)

            # D. KD
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

            # E. MACD
            m_colors = ['#FF0000' if x >= 0 else '#00FF00' for x in df['MACD_hist']]
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

            # --- 佈局：重點在於範圍選擇器 ---
            last_date = df.index[-1]
            start_view = last_date - datetime.timedelta(days=60) # 預設只看最近 60 天，才不會太擠

            fig.update_layout(
                height=1200, 
                template="plotly_dark",
                hovermode="x unified",
                xaxis_rangeslider_visible=True,
                # 💡 設定初始顯示範圍 (從 60 天前到今天)，但你可以往左拉看整年
                xaxis=dict(range=[start_view, last_date]), 
                showlegend=False
            )
            
            # 優化標題樣式
            for i in fig['layout']['annotations']:
                i['font'] = dict(size=14, color='#E0E0E0')
                i['x'] = 0
                i['xanchor'] = 'left'

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("查無數據，請確認代碼。")
