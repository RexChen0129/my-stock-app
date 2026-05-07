import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據抓取與極精密對齊 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_final_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    try:
        # 1. 抓取股價
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        df = pd.DataFrame(res_p['data'])
        if df.empty:
            return None
            
        # 💡 將日期轉換為純 date 對象進行精確匹配
        df['date'] = pd.to_datetime(df['date']).dt.date
        df = df.sort_values('date')

        # 2. 抓取法人 (真實數據)
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN}).json()
        inst_data = res_i.get('data', [])
        
        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date']).dt.date
            # 💡 三大法人當日淨額加總
            inst_df['net'] = inst_df['buy'] - inst_df['sell']
            daily_inst = inst_df.groupby('date')['net'].sum().reset_index()
            
            # 使用 merge 進行左對齊，確保日期與股價日期完全吻合
            df = pd.merge(df, daily_inst, on='date', how='left').fillna(0)
            df.rename(columns={'net': 'Inst_Net'}, inplace=True)
        else:
            df['Inst_Net'] = 0

        # 3. 計算技術指標
        df.set_index('date', inplace=True)
        
        # 三均線 (MA5, MA10, MA20)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        # KD 指標 (9, 3, 3)
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        # MACD 指標 (12, 26, 9)
        e12 = df['close'].ewm(span=12, adjust=False).mean()
        e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"數據處理錯誤: {e}")
        return None

# --- 2. 介面呈現 ---
st.set_page_config(layout="wide")
st.title("📊 專業五指標交易儀表板")

with st.sidebar:
    st.header("功能設定")
    stock_id = st.text_input("輸入台股代碼", value="2330")
    btn = st.button("更新數據")

if btn or stock_id:
    df = fetch_final_data(stock_id)
    if df is not None:
        # 根據資料量計算總寬度，確保 K 線不擁擠
        total_width = len(df) * 40
        
        # 建立 5 個獨立子圖
        fig = make_subplots(
            rows=5, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.02,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線棒與 3MA (5/10/20)", "2. 成交量", "3. 三大法人買賣超", "4. KD 指標", "5. MACD")
        )

        # 指標 1: K線棒 + 3MA
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'],
            increasing_line_color='red', decreasing_line_color='green', name='K線'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name='MA5', line=dict(color='white', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], name='MA10', line=dict(color='yellow', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='magenta', width=1)), row=1, col=1)

        # 指標 2: 成交量
        v_colors = ['red' if df['close'].iloc[i] >= df['open'].iloc[i] else 'green' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color=v_colors, name='成交量'), row=2, col=1)

        # 指標 3: 法人買賣超 (核心修正：確保柱狀圖顯示)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Inst_Net'], 
            marker_color=i_colors, 
            name='法人買賣',
            # 確保法人柱狀圖在懸停時顯示數值
            hovertemplate='%{y:,.0f}'
        ), row=3, col=1)

        # 指標 4: KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K值', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D值', line=dict(color='dodgerblue')), row=4, col=1)

        # 指標 5: MACD
        m_colors = ['red' if x >= 0 else 'green' for x in df['MACD_h']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_h'], marker_color=m_colors, name='MACD柱'), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], name='快線', line=dict(color='white', width=1)), row=5, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], name='慢線', line=dict(color='yellow', width=1)), row=5, col=1)

        # 佈局與滾輪縮放設定
        fig.update_layout(
            width=max(1200, total_width), height=1500,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            dragmode='pan',
            showlegend=True
        )
        
        # 💡 重要：強制 Y 軸依據數據範圍自動調整，不讓法人圖表扁平化
        fig.update_yaxes(autorange=True, fixedrange=False)

        st.plotly_chart(fig, use_container_width=False, config={
            'displayModeBar': True,
            'scrollZoom': True,           # 保留滾輪縮放
            'displaylogo': False,
            'modeBarButtonsToRemove': [   # 移除不需要的按鈕
                'zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'select2d', 'lasso2d'
            ],
        })
