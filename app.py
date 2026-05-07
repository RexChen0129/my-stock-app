import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import datetime

# --- 1. 數據抓取 (抓取一年份) ---
@st.cache_data(ttl=3600)
def fetch_data(stock_id):
    FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiUmF5X0NoZW4iLCJlbWFpbCI6ImNoZW5ydWl4aWFuMDBAZ21haWwuY29tIiwidG9rZW5fdmVyc2lvbiI6MH0.cRmVp07f_wOgMG3EZNfzZP5cmBRRX7VQX5ugV9fyVEk" # 請替換你的 Token
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    
    # 抓取股價與法人資料
    datasets = ["TaiwanStockPrice", "InstitutionalInvestorsBuySell"]
    results = {}
    for ds in datasets:
        url = f"https://api.finmindtrade.com/api/v4/data?dataset={ds}&data_id={stock_id}&start_date={start_date}&end_date={end_date}&token={FINMIND_TOKEN}"
        res = requests.get(url).json()
        results[ds] = pd.DataFrame(res.get('data', []))
    
    return results["TaiwanStockPrice"], results["InstitutionalInvestorsBuySell"]

# --- 2. 介面設定 ---
st.set_page_config(layout="wide")
st.title("📑 獨立捲軸控盤系統")

stock_id = st.sidebar.text_input("輸入代碼", value="2330")

if st.sidebar.button("開始分析"):
    df, inst_df = fetch_data(stock_id)
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 計算指標 (均線、KD、MACD、法人)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        if not inst_df.empty:
            inst_df['date'] = pd.to_datetime(inst_df['date'])
            df['Inst_Net'] = inst_df.groupby('date').apply(lambda x: x['buy'].sum() - x['sell'].sum()).reindex(df.index).fillna(0)
        
        # --- 3. 建立「超寬」圖表 ---
        # 這裡的 width 決定了你可以拉多長，3000~5000 左右會有很棒的延展感
        chart_width = len(df) * 20 
        
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02, 
            row_heights=[0.4, 0.1, 0.1, 0.1, 0.2],
            subplot_titles=("K線", "成交量", "法人", "KD", "MACD")
        )

        # (繪圖代碼：Candlestick, MA, Bar 等，維持與先前邏輯一致)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['max'], low=df['min'], close=df['close']), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='gold')), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Trading_Volume'], marker_color='gray'), row=2, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Inst_Net'], marker_color='red'), row=3, col=1)
        # ... [其餘指標繪製省略] ...

        # 💡 重點配置：鎖定互動，強制超寬
        fig.update_layout(
            width=max(chart_width, 1200), # 確保至少跟螢幕一樣寬
            height=900,
            template="plotly_dark",
            dragmode=False, # 🚫 禁止圖表內縮放
            xaxis_rangeslider_visible=False,
            showlegend=False,
            margin=dict(t=30, b=50, l=10, r=10)
        )

        # --- 💡 4. 使用 CSS 建立獨立捲軸容器 ---
        # 我們把 Plotly 放進一個具有橫向滾動條的 div 裡
        st.markdown("""
            <style>
                .scroll-container {
                    overflow-x: auto; /* 強制顯示水平捲軸 */
                    overflow-y: hidden;
                    white-space: nowrap;
                    width: 100%;
                    border-bottom: 2px solid #333; /* 底部裝飾線 */
                }
                /* 美化捲軸：讓它看起來像你截圖中的灰色條 */
                .scroll-container::-webkit-scrollbar {
                    height: 12px;
                }
                .scroll-container::-webkit-scrollbar-track {
                    background: #1e1e1e;
                }
                .scroll-container::-webkit-scrollbar-thumb {
                    background: #888; 
                    border-radius: 6px;
                }
                .scroll-container::-webkit-scrollbar-thumb:hover {
                    background: #555;
                }
            </style>
        """, unsafe_allow_html=True)

        with st.container():
            # 將圖表包在自定義的滾動類別中
            st.write('<div class="scroll-container">', unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})
            st.write('</div>', unsafe_allow_html=True)
            
        st.info("💡 請使用下方的灰色捲軸左右拖曳查看歷史數據。")

    else:
        st.error("查無資料")
