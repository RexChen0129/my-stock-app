import pandas as pd
import yfinance as yf
import pandas_ta as ta

def get_processed_data(stock_id):
    target = f"{stock_id}.TW"
    df = yf.download(target, period="1y", interval="1d", auto_adjust=True)
    
    if df.empty: 
        return None
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df.columns = [str(col).capitalize() for col in df.columns]

    # 1. 計算均線
    df['MA5'] = ta.sma(df['Close'], length=5)
    df['MA10'] = ta.sma(df['Close'], length=10)
    df['MA20'] = ta.sma(df['Close'], length=20)
    
    # 2. 計算 KD (9, 3, 3)
    kd = df.ta.stoch(high='High', low='Low', close='Close', window=9, smooth_k=3, smooth_d=3)
    df = pd.concat([df, kd], axis=1)
    
    # 3. 計算 MACD (12, 26, 9)
    macd = df.ta.macd(close='Close', fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    
    # 4. 模擬法人買賣超 (對齊你原本的顏色邏輯)
    df['Inst_Net'] = (df['Volume'] / 100).apply(lambda x: x * (pd.Series([1, -1]).sample().iloc[0]))
    
    return df