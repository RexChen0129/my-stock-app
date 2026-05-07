import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime
import time

# --- 1. 數據抓取核心 ---
# FinMind API Token (若有可以填入，沒有則使用公用流量)
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=600)
def fetch_stock_data_stable(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    # 拉長時間軸：抓取 2 年的資料
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date_p = (datetime.date.today() - datetime.timedelta(days=730)).strftime("%Y-%m-%d")
    start_date_i = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # A. 抓取股價 (2年)
        res_p = requests.get(URL, params={
            "dataset": "TaiwanStockPrice", 
            "data_id": stock_id, 
            "start_date": start_date_p, 
            "token": FINMIND_TOKEN
        }).json()
        
        df = pd.DataFrame(res_p['data'])
        if df.empty:
            return None
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # B. 抓取法人數據 (重試邏輯：讓網頁「跑久一點」)
        inst_data = []
        for retry in range(3): # 最多重試 3 次
            try:
                res_i = requests.get(URL, params={
                    "dataset": "InstitutionalInvestorsBuySell", 
                    "data_id": stock_id, 
                    "start_date": start_date_i, 
                    "token": FINMIND_TOKEN
                }, timeout=15).json()
                inst_data = res_i.get('data', [])
                if inst_data: break
                time.sleep(1) # 失敗則等待 1 秒再試
            except:
                time.sleep(1)

        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            inst_df['net'] = inst_df['buy'] - inst_df['sell']
            # 合併當日三大法人
            daily_inst = inst_df.groupby('date')['net'].sum().reset_index()
            # 合併到主表
            df = pd.merge(df, daily_inst, on='date', how='left').fillna(0)
            df.rename(columns={'net': 'Inst_Net'}, inplace=True)
        else:
            df['Inst_Net'] = 0

        # C. 指標計算
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        l9 = df['min'].rolling(9).min()
        h9 = df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = exp12 - exp26
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return None

# --- 2. 介面呈現 ---
st.set_page_config(layout="wide", page_title="專業五指標分析系統")
st.title("🏹 專業五指標終極控盤系統 (強化版)")

with st.sidebar:
    st.header("數據檢索")
    stock_id = st.text_input("輸入股票代碼 (例: 2330)", value="2330")
    update_btn = st.button("立即分析 (含重試機制)")
    st.info("💡 這次加入了 API 自動重試機制，若法人數據較大，系統會多花一點時間等待。")

if update_btn or stock_id:
    with st.spinner('正在從伺服器抓取真實數據並對齊中，請稍候...'):
        df = fetch_stock_data_stable(stock_id)
    
    if df is not None:
        df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
        # 適配更長的時間軸：動態調整總寬度
        plot_width = max(1200, len(df) * 20) 
        
        fig = make_subplots(
            rows=5, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線/均線 (MA 5/10/20)", "2. 成交量", "3. 法人買賣超 (真實數據)", "4. KD 指標", "5. MACD 趨勢")
        )

        # 軌道 1: K線
        fig.add_trace(go.Candlestick(
            x=df['date_str'], open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            name='K線', increasing_line_color='red', decreasing_line_color='green'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['MA5'], name='MA5', line=dict(color='white', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['MA10'], name='MA10', line=dict(color='yellow', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['MA20'], name='MA20', line=dict(color='magenta', width=1)), row=1, col=1)

        # 軌道 2: 成交量
        vol_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df['date_str'], y=df['Trading_Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)

        # 軌道 3: 法人買賣超 (真實數據)
        inst_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(
            x=df['date_str'], 
            y=df['Inst_Net'], 
            name='法人買賣', 
            marker_color=inst_colors,
            hovertemplate='淨額: %{y:,.0f}'
        ), row=3, col=1)

        # 軌道 4: KD
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['K'], name='K值', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['D'], name='D值', line=dict(color='dodgerblue')), row=4, col=1)

        # 軌道 5: MACD
        macd_colors = ['red' if x >= 0 else 'green' for x in df['MACD_h']]
        fig.add_trace(go.Bar(x=df['date_str'], y=df['MACD_h'], name='MACD柱', marker_color=macd_colors), row=5, col=1)
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df['date_str'], y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        # 佈局設定
        fig.update_layout(
            width=plot_width,
            height=1400,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            dragmode='pan'
        )
        
        # 確保法人軌道不會變一條線
        fig.update_yaxes(autorange=True, fixedrange=False, row=3, col=1)
        fig.update_xaxes(type='category', range=[len(df)-60, len(df)]) # 初始顯示最近 60 筆

        st.plotly_chart(fig, use_container_width=False, config={
            'scrollZoom': True,
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
        })
