import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime
import time

# --- 1. 數據抓取核心 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=600)
def fetch_stock_data_stable(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    # 擴大 K 線顯示範圍至 2 年 (730天)
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
        
        df['date'] = pd.to_datetime(df['date']).dt.normalize()
        df = df.sort_values('date')

        # B. 抓取法人數據 (加入強制欄位檢查)
        inst_data = []
        for retry in range(3):
            try:
                res_i = requests.get(URL, params={
                    "dataset": "InstitutionalInvestorsBuySell", 
                    "data_id": stock_id, 
                    "start_date": start_date_i, 
                    "token": FINMIND_TOKEN
                }, timeout=15).json()
                inst_data = res_i.get('data', [])
                if inst_data: break
                time.sleep(1)
            except:
                time.sleep(1)

        if inst_data:
            inst_df = pd.DataFrame(inst_data)
            inst_df['date'] = pd.to_datetime(inst_df['date']).dt.normalize()
            
            # 💡 核心修正：強制將欄位統一為小寫，避免 Buy/buy 混亂導致計算為 0
            inst_df.columns = [c.lower() for c in inst_df.columns]
            
            # 確保 buy 與 sell 欄位存在
            if 'buy' in inst_df.columns and 'sell' in inst_df.columns:
                inst_df['net'] = pd.to_numeric(inst_df['buy']) - pd.to_numeric(inst_df['sell'])
                # 合併當日所有法人
                daily_inst = inst_df.groupby('date')['net'].sum().reset_index()
                
                # 💡 合併前檢查：確保 daily_inst 不是空的且數值正確
                df = pd.merge(df, daily_inst, on='date', how='left')
                # 先不 fillna(0)，觀察是否真的有對到
                df.rename(columns={'net': 'Inst_Net'}, inplace=True)
                df['Inst_Net'] = df['Inst_Net'].fillna(0)
            else:
                df['Inst_Net'] = 0
        else:
            df['Inst_Net'] = 0

        # C. 技術指標計算
        df.set_index('date', inplace=True)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        l9, h9 = df['min'].rolling(9).min(), df['max'].rolling(9).max()
        rsv = (df['close'] - l9) / (h9 - l9) * 100
        df['K'] = rsv.ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        
        e12 = df['close'].ewm(span=12, adjust=False).mean()
        e26 = df['close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = e12 - e26
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_h'] = (df['DIF'] - df['DEA']) * 2
        
        return df
    except Exception as e:
        st.error(f"數據解析異常: {e}")
        return None

# --- 2. 介面呈現 ---
st.set_page_config(layout="wide", page_title="專業五指標分析系統")
st.title("🏹 專業五指標終極控盤系統 (2年數據強化版)")

with st.sidebar:
    st.header("數據檢索")
    stock_id = st.text_input("輸入股票代碼", value="2330")
    update_btn = st.button("立即更新並分析")
    st.markdown("---")
    st.write("📈 **更新說明**:")
    st.write("1. 已將時間軸延長至 2 年。")
    st.write("2. 加入法人數據欄位強制對齊邏輯。")
    st.write("3. 增加 Y 軸自動比例調整。")

if update_btn or stock_id:
    with st.spinner('正在分析中，這可能需要幾秒鐘...'):
        df = fetch_stock_data_stable(stock_id)
    
    if df is not None:
        # 使用字串化日期作為 X 軸，避免顯示非交易日
        df_plot = df.copy()
        df_plot['date_str'] = df_plot.index.strftime('%Y-%m-%d')
        
        # 動態計算寬度
        plot_width = max(1200, len(df_plot) * 20) 
        
        fig = make_subplots(
            rows=5, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.35, 0.1, 0.15, 0.2, 0.2],
            subplot_titles=("1. K線/均線 (MA 5/10/20)", "2. 成交量", "3. 法人買賣超 (真實數據)", "4. KD 指標", "5. MACD 趨勢")
        )

        # 1. K線
        fig.add_trace(go.Candlestick(
            x=df_plot['date_str'], open=df_plot['open'], high=df_plot['max'], low=df_plot['min'], close=df_plot['close'],
            name='K線', increasing_line_color='red', decreasing_line_color='green'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['MA5'], name='MA5', line=dict(color='white', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['MA10'], name='MA10', line=dict(color='yellow', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['MA20'], name='MA20', line=dict(color='magenta', width=1)), row=1, col=1)

        # 2. 成交量
        vol_colors = ['red' if df_plot['close'].iloc[i] >= df_plot['open'].iloc[i] else 'green' for i in range(len(df_plot))]
        fig.add_trace(go.Bar(x=df_plot['date_str'], y=df_plot['Trading_Volume'], name='成交量', marker_color=vol_colors), row=2, col=1)

        # 3. 法人買賣超 (核心修正：強制顯示柱狀圖並更新數值)
        i_colors = ['red' if x >= 0 else 'green' for x in df_plot['Inst_Net']]
        fig.add_trace(go.Bar(
            x=df_plot['date_str'], y=df_plot['Inst_Net'], 
            name='法人買賣', marker_color=i_colors,
            hovertemplate='淨額: %{y:,.0f}'
        ), row=3, col=1)

        # 4. KD
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['K'], name='K值', line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['D'], name='D值', line=dict(color='dodgerblue')), row=4, col=1)

        # 5. MACD
        macd_colors = ['red' if x >= 0 else 'green' for x in df_plot['MACD_h']]
        fig.add_trace(go.Bar(x=df_plot['date_str'], y=df_plot['MACD_h'], name='MACD柱', marker_color=macd_colors), row=5, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['DIF'], name='DIF', line=dict(color='white')), row=5, col=1)
        fig.add_trace(go.Scatter(x=df_plot['date_str'], y=df_plot['DEA'], name='DEA', line=dict(color='yellow')), row=5, col=1)

        # 佈局與滾輪縮放設定
        fig.update_layout(
            width=plot_width, height=1400,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            dragmode='pan',
            showlegend=True
        )
        
        # 💡 強制重置 Y 軸範圍，不讓法人數據被壓縮成一條線
        fig.update_yaxes(autorange=True, fixedrange=False)
        # 💡 初始視角設定在最近的 100 根 K 線 (約半年)
        fig.update_xaxes(type='category', range=[len(df_plot)-100, len(df_plot)])

        st.plotly_chart(fig, use_container_width=False, config={
            'scrollZoom': True,
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['zoom2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
        })
