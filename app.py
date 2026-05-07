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
    # 抓取 365 天數據，確保拖曳條有足夠長度
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    parameter = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        data = res.json().get('data', [])
        return pd.DataFrame(data) if data else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 介面設定 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("📺 專業台股分析 (YouTube 式拖曳版)")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('計算技術指標中...'):
        df = fetch_data("TaiwanStockPrice", stock_id)
        inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 1. 均線
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            
            # 2. 法人買賣超 (修正欄位加總)
            if not inst_df.empty:
                inst_df['date'] = pd.to_datetime(inst_df['date'])
                # 法人資料通常有多筆(外資、投信、自營商)，需依日期加總
                inst_summary = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
                df['Inst_Net'] = inst_summary.reindex(df.index).fillna(0)
            else:
                df['Inst_Net'] = 0

            # 3. KD 與 MACD 計算 (與先前一致)
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

            # --- 繪圖區 ---
            fig = make_subplots(
                rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02, 
                row_heights=[0.4, 0.1, 0.1, 0.1, 0.2],
                subplot_titles=("K線", "成交量", "法人買賣", "KD", "MACD")
            )

            # K線
            fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1)), row=1, col=1)
            
            # 成交量
            v_colors = ['red' if c >= o else 'green' for c, o in zip(df['close'], df['open'])]
            fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], name='成交量', marker_color=v_colors), row=2, col=1)
            
            # 法人買賣 (修正顯示)
            i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
            fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人', marker_color=i_colors), row=3, col=1)
            
            # KD
            fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)
            
            # MACD
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='柱狀圖', marker_color=['red' if x >= 0 else 'green' for x in df['MACD_hist']]), row=5, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

            # --- 💡 重點：YouTube 式拖曳條與鎖定配置 ---
            last_date = df.index[-1]
            start_view = df.index[-60] # 預設只看最後 60 天，K 線才夠粗

            fig.update_layout(
                height=900,
                template="plotly_dark",
                hovermode="x unified",
                showlegend=False,
                dragmode=False, # 🚫 徹底禁用滑鼠框選縮放
                
                # 💡 建立橫放拖曳條 (RangeSlider)
                xaxis=dict(
                    range=[start_view, last_date], # 初始視野
                    rangeslider=dict(
                        visible=True, 
                        thickness=0.05, # 讓條稍微厚一點好拉
                        bgcolor="#222222"
                    ),
                    type="date"
                ),
                margin=dict(t=30, b=10, l=10, r=10)
            )

            # 關閉所有滑鼠互動工具列
            st.plotly_chart(fig, use_container_width=True, config={
                'displayModeBar': False, # 隱藏工具列
                'scrollZoom': False      # 禁用滾輪
            })
            
        else:
            st.error("查無數據，請確認代碼或 API Token 是否正確。")
