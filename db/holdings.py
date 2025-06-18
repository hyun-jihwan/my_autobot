# db/holdings.py

from utils.balance import balance
import json

HOLDINGS_FILE_PATH = "data/holdings.json"

def get_holding_symbols():
    return list(balance["holdings"].keys())

def get_holding_data(symbol):
    return balance["holdings"].get(symbol)

def save_holdings_to_file():
    from utils.position import get_current_holdings  # 필요한 경우
    with open(HOLDINGS_FILE_PATH, "r") as f:
        data = json.load(f)

    with open(HOLDINGS_FILE_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def remove_holding(symbol):
    with open(HOLDINGS_FILE_PATH, "r") as f:
        data = json.load(f)

    if "holdings" in data and symbol in data["holdings"]:
        del data["holdings"][symbol]

        with open(HOLDINGS_FILE_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"🗑 보유 목록에서 제거됨 → {symbol}")
    else:
        print(f"⚠️ 제거 실패: {symbol} 은 holdings에 없음")
