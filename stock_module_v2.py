import yfinance as yf
import pandas as pd

def get_processed_data(stock_id):
    target = f"{stock_id}.TW"
    df = yf.download(target, period="1y", interval="1d", auto_adjust=True)
    
    if df.empty:
        return None
    
    # 手動計算均線，不依賴 pandas-ta
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    # 簡單計算 RSI (代替 pandas-ta)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    return df
