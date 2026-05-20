import subprocess
import sys

if __name__ == "__main__":
    print("🚀 正在啟動第三版 APP 股市分析網頁 (Port: 8502)...")
    # 強制將第三版執行在 8502 連接埠，避免與第二版 (8501) 衝突
    subprocess.run([
        sys.executable, 
        "-m", 
        "streamlit", 
        "run", 
        "stock_app_v3.py", 
        "--server.port", 
        "8502"
    ])
