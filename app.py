import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據抓取與極精密對齊 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_comprehensive_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 1. 抓取股價 (確保日期為 index 且為純日期)
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        df['date'] = pd.to_datetime(df['date']).dt.date # 強制純日期
        df = df.sort_values('date').set_index('date')

        # 2. 抓取法人 (徹底加總對齊)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date']).dt.date # 強制純日期
            inst_df['net'] = inst_df['buy'] - inst_df['sell']
            # 💡 核心修正：將同日的三大法人數據加總成一筆
            daily_inst = inst_df.groupby('date')['net'].sum()
            # 💡 核心修正：使用 join 確保依據 index (日期) 完美對齊
            df = df.join(daily_inst, how='left').fillna(0)
            df.rename(columns={'net': 'Inst_Net'}, inplace=True)
        else:
            df['Inst_Net'] = 0

        # 3. 計算技術指標 (MA, KD, MACD)
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
        st.error(f"數據處理出錯: {e}")
        return None

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")
st.title("🛡️ 專業五指標終極控盤系統")

stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("執行分析"):
    df = fetch_comprehensive_data(stock_id)
    if df is not None:
        # 設定寬度，確保 K 線不會過細
        total_w = len(df) * 45
        
        # 創建 5 個垂直子圖 (嚴格遵守使用者要求的 5 個資訊)
        fig = make_subplots(
            rows=5, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.02,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線棒 (含 MA 5/10/20)", "2. 成交量", "3. 法人買賣超", "4. KD 指標", "5. MACD")
        )

        # 指標 1: K線棒 + 三條 MA 線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            increasing_line_color='red', decreasing_line_color='green', name='K線'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='MA5', line=dict(color='white', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='MA10', line=dict(color='yellow', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='magenta', width=1.5)), row=1, col=1)

        # 指標 2: 成交量
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

        # 佈局設定
        fig.update_layout(
            width=total_w, height=1400, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            dragmode='pan'
        )
        
        # 💡 強制讓法人 Y 軸根據數據起伏，不鎖死座標軸
        fig.update_yaxes(autorange=True, fixedrange=False, row=3, col=1)

        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True,
            'scrollZoom': True,           # 💡 保留滾輪縮放
            'displaylogo': False,
            'modeBarButtonsToRemove': [   # 💡 移除放大鏡等按鈕
                'zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'select2d', 'lasso2d'
            ],
        })
