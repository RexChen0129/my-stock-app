import yfinance as yf
import pandas as pd

def get_processed_data(stock_id):
    target = f"{stock_id}.TW"
    # 下載數據，設定 progress=False 避免日誌過多
    df = yf.download(target, period="1y", interval="1d", auto_adjust=True, progress=False)
    
    if df is None or df.empty:
        return None
    
    # 用最基本的 pandas 算均線，這絕對不會報錯
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    return df
