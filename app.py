import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據抓取：精確處理法人與股價對齊 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        # 股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # 法人：解決「沒起伏」問題，必須加總三大法人
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_df = pd.DataFrame(res_i.get('data', []))
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 💡 核心修正：將每日所有法人淨額相加 (買 - 賣)
            inst_daily = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = inst_daily.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0

        # 指標計算 (MA, KD, MACD)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        # KD
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean(); df['D'] = df['K'].ewm(com=2).mean()
        # MACD
        e12 = df['close'].ewm(span=12, adjust=False).mean(); e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26; df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean(); df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except: return None

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")
st.markdown("<style>.main { background-color: #0E1117; } .stPlotlyChart { overflow-x: auto !important; }</style>", unsafe_allow_html=True)

st.title("🛡️ 專業控盤系統 (功能全開修復版)")
stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("分析"):
    df = fetch_data(stock_id)
    if df is not None:
        # 💡 強制寬度：解決 K 線太細的問題，確保一根至少 40px
        total_width = len(df) * 40
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("K線與均線", "成交量", "法人買賣超", "KD線", "MACD柱圖")
        )

        # 1. K線 (紅漲綠跌)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
                                     increasing_line_color='red', decreasing_line_color='green', name='K線'), row=1, col=1)
        for m, c in zip(['MA5', 'MA10', 'MA20'], ['white', 'yellow', 'magenta']):
            fig.add_trace(go.Scatter(x=df.index, y=df[m], name=m, line=dict(color=c, width=1.5)), row=1, col=1)

        # 2. 成交量
        v_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=v_colors, name='成交量'), row=2, col=1)

        # 3. 法人買賣超 (柱狀圖，買紅賣綠)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人'), row=3, col=1)

        # 4. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_h']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_h'], marker_color=m_colors, name='MACD柱'), row=5, col=1)

        # 💡 佈局設定：強制顯示所有功能按鈕
        fig.update_layout(
            width=total_width, height=1200, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified', dragmode='pan'
        )
        
        # 顯示圖表：強制開啟 config 裡的縮放功能
        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True,        # 💡 強制顯示工具列
            'displaylogo': False,
            'scrollZoom': True,           # 💡 允許滑鼠滾輪縮放
            'modeBarButtonsToAdd': [      # 💡 強制加入放大縮小按鈕
                'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'
            ],
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        })
