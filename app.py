import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. API 配置區 ---
# ⚠️ 請一定要在這裡換成你的 Token，不然會跑不出東西！
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 

@st.cache_data(ttl=300)
def fetch_full_data(stock_id):
    URL = "https://api.finmindtrade.com/api/v4/data"
    # 抓取 365 天數據
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # 抓取股價
    res_p = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN})
    # 抓取法人
    res_i = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "token": FINMIND_TOKEN})
    
    data_p = res_p.json().get('data', [])
    data_i = res_i.json().get('data', [])

    if not data_p: return None

    df = pd.DataFrame(data_p)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # 💡 處理法人數據，確保 Inst_Net 欄位一定存在
    if data_i:
        inst_df = pd.DataFrame(data_i)
        inst_df['date'] = pd.to_datetime(inst_df['date'])
        # 同一天多個法人資料要加總
        inst_net = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum())
        df['Inst_Net'] = inst_net.reindex(df.index).fillna(0)
    else:
        df['Inst_Net'] = 0
    
    return df

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")

# 💡 CSS：強制產生你想要的「灰色橫向捲軸」
st.markdown("""
    <style>
    .stPlotlyChart {
        overflow-x: auto !important;
        background-color: #0E1117;
    }
    .custom-scroll {
        overflow-x: auto !important;
        width: 100%;
        border-bottom: 2px solid #444;
    }
    .custom-scroll::-webkit-scrollbar {
        height: 14px; /* 捲軸厚度 */
    }
    .custom-scroll::-webkit-scrollbar-thumb {
        background: #888888; /* 灰色捲軸條 */
        border-radius: 7px;
    }
    .custom-scroll::-webkit-scrollbar-track {
        background: #262730;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📑 專業控盤系統 (捲軸修復版)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("開始分析"):
    with st.spinner('數據讀取中...'):
        df = fetch_full_data(stock_id)
        
        if df is not None:
            # 💡 關鍵：設定超寬圖表 (每根K線25px) 才會出現你要的橫拉條
            total_w = len(df) * 25
            
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                row_heights=[0.7, 0.3],
                subplot_titles=("K線", "法人買賣超")
            )

            # A. K線
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['open'], high=df['max'], 
                low=df['min'], close=df['close'], name='K線'
            ), row=1, col=1)
            
            # B. 法人買賣超 (確保顯示)
            colors = ['red' if x >= 0 else 'green' for x in df['Inst_Net']]
            fig.add_trace(go.Bar(
                x=df.index, y=df['Inst_Net'], name='法人', marker_color=colors
            ), row=2, col=1)

            fig.update_layout(
                width=total_w, # 超寬度
                height=700,
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                dragmode=False, # 鎖定縮放，專注於捲軸移動
                showlegend=False
            )

            # --- 3. 渲染獨立捲軸區域 ---
            st.write('<div class="custom-scroll">', unsafe_allow_html=True)
            # use_container_width=False 絕對不能改成 True，否則捲軸會消失
            st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
            st.write('</div>', unsafe_allow_html=True)
            
        else:
            st.error("❌ 跑不出東西！請檢查你的 API Token 是否填寫正確，或代碼是否有誤。")
