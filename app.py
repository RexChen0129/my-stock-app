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
    # 抓取較長的時間範圍以利計算指標
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=500)).strftime("%Y-%m-%d")
    parameter = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        res_data = res.json()
        return pd.DataFrame(res_data['data']) if 'data' in res_data else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 介面設定 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("📊 專業台股分析系統 (修正版：鎖定縮放 + 全指標)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('正在分析各項技術指標...'):
        df = fetch_data("TaiwanStockPrice", stock_id)
        inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # --- 核心計算 (確保所有指標在過濾前就計算好) ---
            # 1. 均線
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            
            # 2. 法人數據
            if not inst_df.empty:
                inst_df['date'] = pd.to_datetime(inst_df['date'])
                inst_summary = inst_df.groupby('date')['buy'].sum() - inst_df.groupby('date')['sell'].sum()
                df['Inst_Net'] = inst_summary.reindex(df.index).fillna(0)
            else:
                df['Inst_Net'] = 0

            # 3. KD 指標 (9, 3, 3)
            low_9 = df['min'].rolling(9).min()
            high_9 = df['max'].rolling(9).max()
            rsv = (df['close'] - low_9) / (high_9 - low_9) * 100
            df['K'] = rsv.ewm(com=2).mean()
            df['D'] = df['K'].ewm(com=2).mean()

            # 4. MACD 指標
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['DIF'] = exp1 - exp2
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
            df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2

            # --- 💡 重點 1: 下方獨立拖曳條 (控制顯示範圍) ---
            date_list = df.index.tolist()
            # 讓拉桿顯示在圖表下方
            st.markdown("---")
            start_date_pick, end_date_pick = st.select_slider(
                "↔️ 左右拖曳調整觀察區間 (圖表已鎖定，滑鼠無法縮放)",
                options=date_list,
                value=(date_list[-60], date_list[-1]),
                format_func=lambda x: x.strftime('%Y-%m-%d')
            )

            # 根據拉桿選擇過濾數據
            f_df = df.loc[start_date_pick:end_date_pick]

            # --- 💡 重點 2: 繪圖配置 (禁用滑鼠縮放功能) ---
            fig = make_subplots(
                rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                row_heights=[0.4, 0.1, 0.1, 0.15, 0.25],
                subplot_titles=("【K線與均線】", "【成交量】", "【法人買賣超】", "【KD指標】", "【MACD指標】")
            )

            # 各項繪圖 Trace (使用 f_df)
            fig.add_trace(go.Candlestick(x=f_df.index, open=f_df['open'], high=f_df['max'], low=f_df['min'], close=f_df['close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_df.index, y=f_df['MA5'], name='5MA', line=dict(color='gold')), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_df.index, y=f_df['MA20'], name='20MA', line=dict(color='magenta')), row=1, col=1)
            
            v_colors = ['red' if c >= o else 'green' for c, o in zip(f_df['close'], f_df['open'])]
            fig.add_trace(go.Bar(x=f_df.index, y=f_df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)
            
            i_colors = ['red' if x >= 0 else 'green' for x in f_df['Inst_Net']]
            fig.add_trace(go.Bar(x=f_df.index, y=f_df['Inst_Net'], name='法人', marker_color=i_colors), row=3, col=1)
            
            fig.add_trace(go.Scatter(x=f_df.index, y=f_df['K'], name='K', line=dict(color='orange')), row=4, col=1)
            fig.add_trace(go.Scatter(x=f_df.index, y=f_df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)
            
            m_colors = ['red' if x >= 0 else 'green' for x in f_df['MACD_hist']]
            fig.add_trace(go.Bar(x=f_df.index, y=f_df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
            fig.add_trace(go.Scatter(x=f_df.index, y=f_df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
            fig.add_trace(go.Scatter(x=f_df.index, y=f_df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

            # --- 💡 核心配置：完全禁用滑鼠拖曳縮放 ---
            fig.update_layout(
                height=900,
                template="plotly_dark",
                hovermode="x unified",
                xaxis_rangeslider_visible=False,
                dragmode=False, # 🚫 禁用所有拖曳行為（包括放大鏡）
                showlegend=False,
                margin=dict(t=50, b=10, l=10, r=10)
            )

            # 移除所有互動按鈕，僅保留資訊顯示
            st.plotly_chart(fig, use_container_width=True, config={
                'staticPlot': False,
                'displayModeBar': False, # 隱藏上方工具列
                'scrollZoom': False     # 禁止滾輪縮放
            })
            
        else:
            st.error("查無數據。")
