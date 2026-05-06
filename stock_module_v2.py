import yfinance as yf
import pandas as pd

def get_processed_data(stock_id):
    target = f"{stock_id}.TW"
    # 下載數據
    df = yf.download(target, period="1y", interval="1d", auto_adjust=True)
    
    if df.empty:
        return None
    
    # 手動計算均線 (不需要 pandas-ta)
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    return df
