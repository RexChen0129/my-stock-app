import streamlit as st
import sys
import os

# 1. 這三行是關鍵：強制讓程式去搜尋目前的資料夾
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 2. 匯入你的模組（名稱必須跟 GitHub 上的檔名一模一樣）
import stock_module_v2 as sm

st.set_page_config(page_title="專業台股分析系統", layout="wide")
st.title("⚡ 專業股市分析系統 (完整功能版)")

with st.sidebar:
    st.header("數據查詢")
    stock_id = st.text_input("請輸入台股代碼", value="2330")
    analyze_btn = st.button("點擊開始分析")

if analyze_btn:
    with st.spinner('正在分析中...'):
        df = stock_module_v2.get_processed_data(stock_id)
        
        if df is not None:
            df_view = df.tail(60) # 顯示最近 60 天
            
            # 建立五層專業圖表
            fig = make_subplots(
                rows=5, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                subplot_titles=('K線與均線', '成交量', '法人買賣', 'KD指標', 'MACD'),
                row_heights=[0.4, 0.15, 0.15, 0.15, 0.15]
            )

            # 1. K線圖
            fig.add_trace(go.Candlestick(
                x=df_view.index, open=df_view['Open'], high=df_view['High'],
                low=df_view['Low'], close=df_view['Close'], name='K線',
                increasing_line_color='red', decreasing_line_color='green'
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_view.index, y=df_view['MA5'], name='MA5', line=dict(color='gold')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_view.index, y=df_view['MA20'], name='MA20', line=dict(color='#00ccff')), row=1, col=1)

            # 2. 成交量
            v_colors = ['red' if df_view['Close'].iloc[i] >= df_view['Open'].iloc[i] else 'green' for i in range(len(df_view))]
            fig.add_trace(go.Bar(x=df_view.index, y=df_view['Volume'], name='成交量', marker_color=v_colors), row=2, col=1)

            # 3. 法人買賣 (Inst_Net)
            i_colors = ['red' if x >= 0 else 'green' for x in df_view['Inst_Net']]
            fig.add_trace(go.Bar(x=df_view.index, y=df_view['Inst_Net'], name='法人買賣', marker_color=i_colors), row=3, col=1)

            # 4. KD 指標
            k_col = [c for c in df.columns if 'STOCHk' in c][0]
            d_col = [c for c in df.columns if 'STOCHd' in c][0]
            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[k_col], name='K值', line=dict(color='#00ff88')), row=4, col=1)
            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[d_col], name='D值', line=dict(color='#00ccff')), row=4, col=1)

            # 5. MACD
            macd_col = [c for c in df.columns if 'MACD_' in c and 'h' not in c and 's' not in c][0]
            macd_h_col = [c for c in df.columns if 'MACDh' in c][0]
            macd_s_col = [c for c in df.columns if 'MACDs' in c][0]
            m_colors = ['red' if x >= 0 else 'green' for x in df_view[macd_h_col]]
            
            fig.add_trace(go.Bar(x=df_view.index, y=df_view[macd_h_col], name='MACD柱', marker_color=m_colors), row=5, col=1)
            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[macd_col], name='DIF', line=dict(color='#ff00ff')), row=5, col=1)
            fig.add_trace(go.Scatter(x=df_view.index, y=df_view[macd_s_col], name='DEA', line=dict(color='#ffff00')), row=5, col=1)

            # 全域樣式設定
            fig.update_layout(
                height=1000, 
                template="plotly_dark", 
                xaxis_rangeslider_visible=False,
                # 💡 關鍵修正：讓滑鼠移到該位置時，自動顯示所有指標的數據
                hovermode="x unified", 
                hoverlabel=dict(
                    bgcolor="rgba(30, 30, 30, 0.9)",
                    font_size=13,
                    font_family="Arial"
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # 強制讓 K 線在懸浮時顯示更多細節
            fig.update_traces(
                hoverinfo="all", 
                selector=dict(type='candlestick')
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("❌ 找不到資料。")
