import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" # 👈 請在此輸入你的 Token

@st.cache_data(ttl=3600)
def fetch_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    # 抓取較長區間以供捲軸左右拉動
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # 抓取股價與法人資料
    try:
        res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN})
        res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN})
        
        df = pd.DataFrame(res_p.json()['data'])
        inst_df = pd.DataFrame(res_i.json()['data'])
        
        if df.empty: return None
        
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 核心：合併法人買賣超數據 (修正 Inst_Net 不見的問題)
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            # 彙總當天所有法人的淨買賣
            inst_net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
            df['Inst_Net'] = inst_net.reindex(df.index).fillna(0)
        else:
            df['Inst_Net'] = 0
            
        return df
    except Exception as e:
        return None

# --- 2. CSS 樣式：建立橫向捲軸容器 ---
st.markdown("""
    <style>
    .scroll-wrapper {
        overflow-x: auto !important; /* 強制橫向捲軸 */
        width: 100%;
        background-color: #0E1117;
        border: 1px solid #333;
    }
    /* 美化捲軸為灰色條 */
    .scroll-wrapper::-webkit-scrollbar { height: 12px; }
    .scroll-wrapper::-webkit-scrollbar-thumb { background: #888; border-radius: 6px; }
    .scroll-wrapper::-webkit-scrollbar-track { background: #222; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 介面邏輯 ---
st.title("📈 專業台股系統 (橫向捲軸版)")
stock_id = st.sidebar.text_input("代碼", "2330")

if st.sidebar.button("開始分析"):
    df = fetch_data(stock_id)
    if df is not None:
        # 💡 捲軸關鍵：資料點越多，圖表寬度越寬 (每根 K 線 25 像素)
        total_width = len(df) * 25
        
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, 
            vertical_spacing=0.05, row_heights=[0.7, 0.3],
            subplot_titles=("K線", "法人買賣超")
        )

        # K線
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], 
                                   low=df['min'], close=df['close'], name="K線"), row=1, col=1)
        
        # 法人買賣超 (確保顯示在 Row 2)
        i_colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color=i_colors, name="法人淨買賣"), row=2, col=1)

        # 💡 佈局設定：強制寬度不被壓縮
        fig.update_layout(
            width=total_width, 
            height=600,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode=False # 關閉 Plotly 內建縮放，改用下方捲軸
        )

        # --- 4. 渲染到捲軸容器中 ---
        st.write('<div class="scroll-wrapper">', unsafe_allow_html=True)
        # 關鍵：use_container_width 必須設為 False
        st.plotly_chart(fig, use_container_width=False)
        st.write('</div>', unsafe_allow_html=True)
