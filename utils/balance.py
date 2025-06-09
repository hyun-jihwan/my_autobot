import json
import os
import datetime
from utils.candle import get_candles


# ✅ 잔고 로드 (holdings.json)
try:
    if os.path.exists("holdings.json"):
        with open("holdings.json", "r") as f:
            content = f.read().strip()
            if not content:
                raise ValueError("파일 내용 없음")
            balance = json.loads(content)
    else:
        raise FileNotFoundError("holdings.json 없음")
except Exception as e:
    print(f"❌ holdings.json 로드 실패: {e}")
    balance = {
        "KRW": 1000000,
        "holdings": [],
        "switched": False  # ✅ 갈아타기 여부
    }

def clear_holdings():
    global holdings
    holdings = []

def get_krw_balance():
    return balance["KRW"]

def update_balance_after_buy(amount):
    balance["KRW"] -= amount

def update_balance_after_sell(amount):
    balance["KRW"] += amount


def get_holdings():
    return balance["holdings"]

def get_holding_symbols():
    return [h["symbol"] for h in balance["holdings"]]

def get_holding_count():
    return len(balance["holdings"])

def get_holding_info():
    return balance["holdings"]


# 💾 보유 종목 JSON 파일 저장
def save_holdings_to_file(filepath="data/holdings.json"):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(balance["holdings"], f, indent=2, ensure_ascii=False)

# ✅ record_holding 함수 내부에서 아래처럼 저장되도록 수정
def record_holding(symbol, entry_price, quantity, score=None, expected_profit=None, source=None, entry_time=None):
    balance["holdings"] = [h for h in balance["holdings"] if h["symbol"] != symbol]
    print(f"🗑 보유 목록에서 제거됨 → {symbol}")

    if entry_time is None:
        entry_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    holding = {
        "symbol": symbol,
        "entry_price": entry_price,
        "quantity": quantity,
        "entry_time": entry_time
    }
    if score is not None:
        holding["score"] = score
    if expected_profit is not None:
        holding["expected_profit"] = expected_profit
    if source is not None:
        holding["source"] = source


    balance["holdings"].append(holding)

    # 💾 보유 종목 저장
    save_holdings_to_file()

    print(f"✅ 진입 기록 완료: {symbol} / 진입가: {entry_price} / 수량: {quantity}")

# 🔁 재시작 시 복구용 로드 함수
def load_holdings_from_file(filepath="data/holdings.json"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                balance["holdings"] = json.load(f)
                print("🔄 holdings.json → 보유 종목 복구 완료")
            except Exception as e:
                print(f"❌ holdings.json 로드 실패: {e}")

def reset_switch_flag():
    balance["switched"] = False

def set_switch_flag():
    balance["switched"] = True

def has_switched():
    return balance.get("switched", False)

def remove_holding(symbol):
    balance["holdings"] = [h for h in balance["holdings"] if h["symbol"] != symbol]
    print(f"🗑 보유 목록에서 제거됨 → {symbol}")

def get_current_price(symbol):
    candles = get_candles(symbol, interval="1", count=1)
    if candles:
        return candles[0]["trade_price"]
    return 0
