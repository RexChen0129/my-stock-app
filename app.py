import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據抓取：使用 merge_asof 進行暴力對齊 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_all_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價並確保排序
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 抓取法人
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            inst_df['net'] = inst_df['buy'] - inst_df['sell']
            # 先將當天三大法人合併
            daily_inst = inst_df.groupby('date')['net'].sum().reset_index()
            daily_inst = daily_inst.sort_values('date')
            
            # 💡 核心修正：使用 merge_asof 解決日期微差問題，強迫對齊
            df = pd.merge_asof(df, daily_inst, on='date', direction='nearest')
            df.rename(columns={'net': 'Inst_Net'}, inplace=True)
            df['Inst_Net'] = df['Inst_Net'].fillna(0)
        else:
            df['Inst_Net'] = 0

        # 指標計算
        df.set_index('date', inplace=True)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean(); df['D'] = df['K'].ewm(com=2).mean()
        e12 = df['close'].ewm(span=12, adjust=False).mean(); e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26; df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean(); df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"數據處理失敗: {e}")
        return None

# --- 2. 頁面設定 ---
st.set_page_config(layout="wide")
st.markdown("<style>.stPlotlyChart { overflow: visible !important; }</style>", unsafe_allow_html=True)

st.title("📊 專業控盤系統 (法人對齊與功能精簡版)")
stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("分析"):
    df = fetch_all_data(stock_id)
    if df is not None:
        total_w = len(df) * 40
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("K線", "成交量", "法人買賣超", "KD指標", "MACD")
        )

        # 1. K線
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                                     increasing_line_color='red', decreasing_line_color='green', name='K線'), row=1, col=1)
        for ma, color in zip(['MA5', 'MA10', 'MA20'], ['white', 'yellow', 'magenta']):
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(color=color, width=1.5)), row=1, col=1)

        # 2. 成交量
        v_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=v_colors, name='成交量'), row=2, col=1)

        # 3. 法人買賣超 (柱狀圖)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人淨額'), row=3, col=1)

        # 4. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_h']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_h'], marker_color=m_colors, name='MACD柱'), row=5, col=1)

        # 佈局設定
        fig.update_layout(
            width=total_w, height=1300, template="plotly_dark",
            xaxis_rangeslider_visible=False, hovermode='x unified',
            dragmode='pan' # 💡 預設改為抓取平移，不再是縮放
        )
        
        # 💡 強制讓法人 Y 軸根據數據起伏
        fig.update_yaxes(autorange=True, fixedrange=False, row=3, col=1)

        # 💡 移除放大鏡：從 modeBarButtonsToRemove 中移除不需要的功能
        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True,
            'scrollZoom': False, # 💡 關閉滾輪縮放
            'displaylogo': False,
            'modeBarButtonsToRemove': [
                'zoom2d', 'zoomIn2d', 'zoomOut2d', 'select2d', 'lasso2d', 'autoScale2d'
            ], # 💡 這裡徹底刪除了所有縮放與放大鏡按鈕
        })
