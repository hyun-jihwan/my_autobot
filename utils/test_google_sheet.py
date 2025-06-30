# utils/test_google_sheet.py

from utils.google_sheet_logger import log_trade_to_sheet
from datetime import datetime

if __name__ == "__main__":
    test_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "symbol": "KRW-BTC",
        "type": "매수",
        "strategy": "전략1-단타",
        "buy_amount": 50000,
        "sell_amount": 0,
        "profit_rate": 0,
        "profit_amount": 0,
        "balance": 1050000
    }
    log_trade_to_sheet(test_data)
