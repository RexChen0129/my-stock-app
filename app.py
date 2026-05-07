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
    # 抓取 365 天數據，確保左右拖曳有完整資料
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
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("🔘 專業台股分析系統 (按鈕縮放+拖曳版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('正在讀取數據...'):
        df = fetch_data("TaiwanStockPrice", stock_id)
        inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 法人數據處理
            if not inst_df.empty:
                inst_df['date'] = pd.to_datetime(inst_df['date'])
                inst_summary = inst_df.groupby('date')['buy'].sum() - inst_df.groupby('date')['sell'].sum()
                df['Inst_Net'] = inst_summary.reindex(df.index).fillna(0)
            else:
                df['Inst_Net'] = 0

            # 指標計算 (MA, KD, MACD)
            df['MA5'] = df['close'].rolling(5).mean()
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

            # --- 繪圖 ---
            fig = make_subplots(
                rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02, 
                row_heights=[0.4, 0.1, 0.1, 0.15, 0.25],
                subplot_titles=("【K線與均線】", "【成交量】", "【法人買賣超】", "【KD指標】", "【MACD指標】")
            )

            # 繪製各項指標 (K線, 成交量, 法人, KD, MACD)
            fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta')), row=1, col=1)
            
            v_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)
            
            i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
            fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人買賣', marker_color=i_colors), row=3, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)
            
            m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_hist']]
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD柱', marker_color=m_colors), row=5, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

            # --- 💡 重點：設定按鈕與滑動條 ---
            last_date = df.index[-1]
            
            # 定義不同倍率的視野範圍
            view_60 = [df.index[-60], last_date]
            view_120 = [df.index[-120], last_date]
            view_all = [df.index[0], last_date]

            fig.update_layout(
                height=1000,
                template="plotly_dark",
                hovermode="x unified",
                # 1. 開啟下方的左右拖曳條
                xaxis_rangeslider_visible=True,
                xaxis=dict(range=view_60), # 預設顯示最近 60 天
                
                # 2. 建立自定義按鈕
                updatemenus=[
                    dict(
                        type="buttons",
                        direction="right",
                        active=0,
                        x=0.01,
                        y=1.1,
                        buttons=list([
                            dict(label="🔍 放大 (60天)", method="relayout", args=[{"xaxis.range": view_60}]),
                            dict(label="⚖️ 中等 (120天)", method="relayout", args=[{"xaxis.range": view_120}]),
                            dict(label="🌐 全部 (1年)", method="relayout", args=[{"xaxis.range": view_all}]),
                        ]),
                    )
                ],
                showlegend=False
            )
            
            # 標題樣式優化
            for i in fig['layout']['annotations']:
                i['x'] = 0
                i['xanchor'] = 'left'

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("查無數據。")
