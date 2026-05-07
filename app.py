import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據抓取與精確對齊 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk"  # 如果你有 Token 請填入，沒有則留空使用限流模式

@st.cache_data(ttl=300)
def fetch_comprehensive_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 1. 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 2. 抓取法人 (修正對齊問題)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 先算出當天所有法人(外資+投信+自營)的淨買賣
            inst_df['net'] = inst_df['buy'] - inst_df['sell']
            daily_inst = inst_df.groupby('date')['net'].sum().reset_index()
            daily_inst = daily_inst.sort_values('date')
            
            # 使用 merge_asof 確保法人數據能精準掛載到股價日期上 (解決毫秒差)
            df = pd.merge_asof(df, daily_inst, on='date', direction='nearest')
            df.rename(columns={'net': 'Inst_Net'}, inplace=True)
            df['Inst_Net'] = df['Inst_Net'].fillna(0)
        else:
            df['Inst_Net'] = 0

        # 3. 計算技術指標 (MA, KD, MACD)
        df.set_index('date', inplace=True)
        # 三條 MA 線
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        # KD 指標
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        # MACD 指標
        e12 = df['close'].ewm(span=12, adjust=False).mean()
        e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"數據出錯: {e}")
        return None

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")
st.title("🛡️ 專業五指標終極控盤系統")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("執行分析"):
    df = fetch_comprehensive_data(stock_id)
    if df is not None:
        # 強制每根 K 線寬度，觸發橫向捲軸
        total_w = len(df) * 45
        
        # 創建 5 個垂直子圖
        fig = make_subplots(
            rows=5, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.02,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線 + 3MA (5/10/20)", "2. 成交量", "3. 法人買賣超 (張/股)", "4. KD指標", "5. MACD")
        )

        # 指標 1: K線棒 + 三條 MA 線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            increasing_line_color='red', decreasing_line_color='green', name='K線'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='MA5', line=dict(color='white', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='MA10', line=dict(color='yellow', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='magenta', width=1.5)), row=1, col=1)

        # 指標 2: 成交量 (紅漲綠跌)
        v_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=v_colors, name='成交量'), row=2, col=1)

        # 指標 3: 法人買賣 (紅漲綠跌柱狀圖)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name='法人淨額'), row=3, col=1)

        # 指標 4: KD 線
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K線', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D線', line=dict(color='dodgerblue')), row=4, col=1)

        # 指標 5: MACD 線
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_h']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_h'], marker_color=m_colors, name='MACD柱'), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        # 佈局設定: 移除右上角縮放按鈕，保留滾輪縮放功能
        fig.update_layout(
            width=total_w, height=1400, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            dragmode='pan' # 預設抓取平移
        )
        
        # 法人區塊 Y 軸強制自適應數據，避免縮成一條線
        fig.update_yaxes(autorange=True, fixedrange=False, row=3, col=1)

        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True,
            'scrollZoom': True,           # 💡 保留滾輪放大縮小
            'displaylogo': False,
            'modeBarButtonsToRemove': [   # 💡 移除你不要的所有放大鏡/選取按鈕
                'zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'select2d', 'lasso2d'
            ],
        })
