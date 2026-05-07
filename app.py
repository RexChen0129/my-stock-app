import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 配置區 ---
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" 
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

@st.cache_data(ttl=3600)
def fetch_data(dataset, stock_id):
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    parameter = {"dataset": dataset, "data_id": stock_id, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
    try:
        res = requests.get(FINMIND_URL, params=parameter)
        res_data = res.json()
        return pd.DataFrame(res_data['data']) if 'data' in res_data else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 介面設定 ---
st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("📊 專業台股分析系統 (極大化版面 + 獨立捲軸)")

# Sidebar 查詢
stock_id = st.sidebar.text_input("輸入台股代碼", value="2330")
analyze_btn = st.sidebar.button("開始分析")

if analyze_btn:
    with st.spinner('數據處理中...'):
        df = fetch_data("TaiwanStockPrice", stock_id)
        inst_df = fetch_data("InstitutionalInvestorsBuySell", stock_id)
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # 指標計算
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            # (KD, MACD 計算省略，維持與前版本一致...)

            # --- 💡 重點 1: 獨立的橫向滑動條 (Streamlit Slider) ---
            # 我們用一個單獨的元件來選擇「顯示哪一段時間」
            date_list = df.index.tolist()
            start_idx, end_idx = st.select_slider(
                "📅 拖曳下方拉桿調整時間範圍 (不影響圖表縮放工具)",
                options=date_list,
                value=(date_list[-60], date_list[-1]), # 預設顯示最後 60 天
                format_func=lambda x: x.strftime('%Y-%m-%d')
            )

            # 根據滑動條篩選數據
            filtered_df = df.loc[start_idx:end_idx]

            # --- 💡 重點 2: 繪圖 (使用 filtered_df) ---
            fig = make_subplots(
                rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                row_heights=[0.5, 0.1, 0.1, 0.1, 0.2],
                subplot_titles=("K線與均線", "成交量", "法人買賣", "KD", "MACD")
            )

            # 主圖：K線
            fig.add_trace(go.Candlestick(
                x=filtered_df.index, open=filtered_df['open'], high=filtered_df['max'], 
                low=filtered_df['min'], close=filtered_df['close'], name='K線'
            ), row=1, col=1)

            # 均線
            fig.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df['MA5'], name='5MA', line=dict(color='gold', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=filtered_df.index, y=filtered_df['MA20'], name='20MA', line=dict(color='magenta', width=1.5)), row=1, col=1)

            # (其餘成交量、法人、KD、MACD 依照 filtered_df 繪製...)
            # ... [省略重複的 add_trace 代碼] ...

            # --- 💡 重點 3: 配置調整 (移除 RangeSlider 與自定義按鈕) ---
            fig.update_layout(
                height=900, # 增加高度讓版面最大化
                template="plotly_dark",
                hovermode="x unified",
                showlegend=False,
                xaxis_rangeslider_visible=False, # 關閉 Plotly 內建滑動條，改用我們上面做的
                # 這裡不需要設定 xaxis.range，因為我們直接篩選了 Dataframe
                dragmode="zoom", # 預設開啟「放大鏡」功能
                margin=dict(t=30, b=10, l=10, r=10) # 極小化邊距
            )

            # 使用 Streamlit 顯示，不需額外按鍵
            st.plotly_chart(fig, use_container_width=True, config={
                'displayModeBar': True, # 顯示頂部工具列（內含放大鏡、縮放工具）
                'modeBarButtonsToAdd': ['drawline', 'drawrect', 'eraseshape'] # 額外增加一些工具
            })
            
        else:
            st.error("查無數據。")
