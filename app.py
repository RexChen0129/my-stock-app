import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 資料抓取與精確對齊 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_all_indicators(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        # 抓取法人 (修正合併邏輯)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_df = pd.DataFrame(res_i.get('data', []))
        
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 先將當天所有法人買賣加總，避免一對多合併造成數據爆炸
            inst_daily = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = inst_daily.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0

        # 技術指標計算
        # MA
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        # KD
        l9 = df['min'].rolling(9).min(); h9 = df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean(); df['D'] = df['K'].ewm(com=2).mean()
        # MACD
        e12 = df['close'].ewm(span=12, adjust=False).mean(); e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26; df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean(); df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"錯誤: {e}"); return None

# --- 2. CSS：強制橫向捲軸 ---
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    .scroll-box { overflow-x: auto !important; width: 100%; background: #0E1117; border: 1px solid #444; }
    .scroll-box::-webkit-scrollbar { height: 14px; }
    .scroll-box::-webkit-scrollbar-thumb { background: #888; border-radius: 7px; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 專業全指標控盤系統 (修正版)")
stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("分析"):
    df = fetch_all_indicators(stock_id)
    if df is not None:
        # 強制 K 線寬度：每根 40 像素，確保捲軸一定出現且 K 線夠粗
        chart_w = len(df) * 40
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1.K線(5/10/20MA)", "2.成交量", "3.法人買賣超", "4.KD", "5.MACD")
        )

        # 1. K線：紅漲綠跌
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], 
                                     increasing_line_color='red', decreasing_line_color='green', name='K線'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='5MA', line=dict(color='gold', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='10MA', line=dict(color='cyan', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='20MA', line=dict(color='magenta', width=1.5)), row=1, col=1)

        # 2. 成交量：紅漲綠跌
        v_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=v_colors, name='成交量'), row=2, col=1)

        # 3. 法人買賣超：買超紅、賣超綠
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人'), row=3, col=1)

        # 4. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], marker_color=m_colors, name='MACD柱'), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(
            width=chart_w, height=1200, template="plotly_dark",
            xaxis_rangeslider_visible=False, dragmode=False, hovermode='x unified'
        )
        # 固定座標軸，強迫使用橫向捲軸，並開啟工具列放大鏡
        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)

        st.write('<div class="scroll-box">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': True})
        st.write('</div>', unsafe_allow_html=True)
