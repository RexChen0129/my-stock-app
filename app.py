import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 核心數據處理 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk"  # 請填入你的 FinMind Token

@st.cache_data(ttl=300)
def fetch_all_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        # 抓取法人並修正對齊與計算 (張數)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_df = pd.DataFrame(res_i.get('data', []))
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 每日加總外資、投信、自營商，並除以 1000 轉為張數
            inst_daily = inst_df.groupby('date').apply(lambda x: (x['buy'].sum() - x['sell'].sum()) / 1000)
            df['Inst_Net'] = inst_daily.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0

        # 計算 MA, KD, MACD
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean(); df['D'] = df['K'].ewm(com=2).mean()
        
        e12 = df['close'].ewm(span=12, adjust=False).mean()
        e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"數據加載失敗: {e}")
        return None

# --- 2. 介面與 CSS ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .scroll-wrapper { overflow-x: auto !important; width: 100%; background: #0E1117; border: 1px solid #444; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 專業控盤系統 - 五大指標修正版")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("分析"):
    df = fetch_all_data(stock_id)
    if df is not None:
        # 強制 K 線寬度：每根 40px，觸發橫向捲軸
        total_w = len(df) * 40
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1.K線(5/10/20MA)", "2.成交量", "3.法人買賣超(張)", "4.KD指標", "5.MACD")
        )

        # 1. K線：紅漲綠跌
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], 
                                     increasing_line_color='red', decreasing_line_color='green', name='K線'), row=1, col=1)
        for ma, color in zip(['MA5', 'MA10', 'MA20'], ['white', 'yellow', 'magenta']):
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(color=color, width=1.5)), row=1, col=1)

        # 2. 成交量：今日收盤 > 昨日收盤 為紅
        v_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=v_colors, name='成交量'), row=2, col=1)

        # 3. 法人買賣超：買超紅、賣超綠 (張數)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人淨額'), row=3, col=1)

        # 4. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_h']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_h'], marker_color=m_colors, name='MACD柱'), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        # 佈局設定：修正 Y 軸自適應與日期
        fig.update_layout(
            width=total_w, height=1200, template="plotly_dark",
            xaxis_rangeslider_visible=False, dragmode=False, hovermode='x unified'
        )
        # 強制顯示放大縮小工具與日期格式
        fig.update_xaxes(fixedrange=True, tickformat='%Y-%m-%d')
        fig.update_yaxes(fixedrange=True)
        fig.update_yaxes(autorange=True, row=3, col=1) # 💡 特別讓法人 Y 軸自動起伏

        st.write('<div class="scroll-wrapper">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True,
            'scrollZoom': True,
            'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'resetScale2d'],
            'displaylogo': False
        })
        st.write('</div>', unsafe_allow_html=True)
