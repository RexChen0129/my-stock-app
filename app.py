import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據處理核心 (修正 Inst_Net 遺失問題) ---
def get_data(stock_id):
    # 請確保這裡替換成你正確的 FinMind Token
    TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 
    URL = "https://api.finmindtrade.com/api/v4/data"
    
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # 抓取股價
    res_price = requests.get(URL, params={"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": TOKEN})
    df = pd.DataFrame(res_price.json().get('data', []))
    
    # 抓取法人資料
    res_inst = requests.get(URL, params={"dataset": "InstitutionalInvestorsBuySell", "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": TOKEN})
    inst_df = pd.DataFrame(res_inst.json().get('data', []))

    if df.empty: return pd.DataFrame()

    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    # 💡 關鍵修正：確保 Inst_Net 欄位被正確創建並合併
    if not inst_df.empty:
        inst_df['date'] = pd.to_datetime(inst_df['date'])
        # 計算買賣差額並按日期加總
        inst_df['net'] = inst_df['buy'] - inst_df['sell']
        inst_net = inst_df.groupby('date')['net'].sum()
        # 合併回主表，缺失值補 0
        df = df.join(inst_net).rename(columns={'net': 'Inst_Net'}).fillna(0)
    else:
        df['Inst_Net'] = 0 # 若無資料則補 0，避免 KeyError

    # 計算其餘技術指標 (KD, MACD)
    # ... (省略中間計算過程以節省空間) ...
    return df

# --- 2. 介面設定與 CSS 樣式 ---
st.set_page_config(layout="wide")

# 💡 美化獨立灰色捲軸的 CSS
st.markdown("""
    <style>
        .custom-scroll {
            overflow-x: auto !important;
            width: 100%;
            border-bottom: 1px solid #444;
        }
        .custom-scroll::-webkit-scrollbar {
            height: 12px;
        }
        .custom-scroll::-webkit-scrollbar-track {
            background: #1e1e1e;
        }
        .custom-scroll::-webkit-scrollbar-thumb {
            background: #888; /* 你要的灰色條 */
            border-radius: 10px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📑 獨立捲軸控盤系統 (修正版)")
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")

if st.sidebar.button("開始分析"):
    df = get_data(stock_id)
    
    if not df.empty:
        # 💡 設定超寬圖表，寬度 = 資料天數 * 每根 K 線寬度
        # 這樣才會出現你說的「灰色的那條」
        total_width = len(df) * 25 
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
            row_heights=[0.4, 0.1, 0.1, 0.1, 0.2]
        )

        # 繪製 K 線與法人買賣超 (這裡現在保證有 Inst_Net 欄位)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close'], name='K線'), row=1, col=1)
        
        # 💡 修正處：繪製法人買賣超
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], name='法人買賣', marker_color='red'), row=3, col=1)

        # 圖表佈局設定
        fig.update_layout(
            width=total_width, 
            height=850,
            template="plotly_dark",
            dragmode=False, # 🚫 鎖定圖表，不讓滑鼠在上面縮放
            xaxis_rangeslider_visible=False, # 隱藏圖表內部的拉桿
            showlegend=False
        )

        # --- 3. 渲染獨立捲軸容器 ---
        st.write('<div class="custom-scroll">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
        st.write('</div>', unsafe_allow_html=True)
        
    else:
        st.error("查無數據，請檢查代碼或 API 設定。")
