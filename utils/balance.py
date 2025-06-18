import json
import os
import datetime
from utils.candle import get_candles


# ✅ 잔고 로드 (holdings.json)
import os
import json

# ✅ 잔고 로드 (data/holdings.json)
try:
    filepath = "data/holdings.json"

    if not os.path.exists(filepath):
        raise FileNotFoundError("holdings.json 없음")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            raise ValueError("파일 내용 없음")

        balance = json.loads(content)

        # ✅ 구조 보정
        if "holdings" not in balance or not isinstance(balance["holdings"], dict):
            balance["holdings"] = {}
        if "KRW" not in balance:
            balance["KRW"] = 1000000
        if "switched" not in balance:
            balance["switched"] = False

except Exception as e:
    print(f"❌ holdings.json 로드 실패: {e}")
    balance = {
        "KRW": 1000000,
        "holdings": {},          # ✅ 반드시 dict
        "switched": False
    }



def clear_holdings():
    global holdings
    holdings = []

def get_krw_balance():
    return balance["KRW"]

def update_balance_after_buy(amount):
    global balance
    balance["KRW"] -= amount
    save_holdings_to_file()


def update_balance_after_sell(symbol, sell_price, quantity):
    global balance
    proceeds = sell_price*quantity*0.999
    balance["KRW"] += proceeds

    save_holdings_to_file()

def update_holding_field(symbol, field, value):
    global balance
    print(f"🧪 update_holding_field 실행됨 → {symbol} / {field} = {value}")
    if symbol in balance["holdings"]:
        balance["holdings"][symbol][field] = value
        print(f"🔧 {symbol} → {field} 필드 업데이트: {value}")
        save_holdings_to_file()
        print("💾 holdings 저장 완료")
    else:
        print(f"⚠️ {symbol} 존재하지 않음 → 업데이트 실패")


def get_holdings():
    return balance["holdings"]

def get_holding_symbols():
    return [h["symbol"] for h in balance["holdings"].values()]

def get_holding_count():
    return len(balance["holdings"])

def get_holding_info():
    return balance["holdings"]


# 💾 보유 종목 JSON 파일 저장
def save_holdings_to_file(filepath="data/holdings.json"):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "holdings": balance["holdings"],     # ✅ dict 그대로 저장
            "KRW": balance["KRW"],
            "switched": balance.get("switched", False)
        }, f, indent=2, ensure_ascii=False)

    # ✅ 여기! 저장이 끝난 후에 로그 출력
    print("💾 holdings.json 저장 시도 완료")

# ✅ record_holding 함수 내부에서 아래처럼 저장되도록 수정
def record_holding(symbol, entry_price, quantity, score=None, expected_profit=None, source=None, entry_time=None, target_2=0, target_3=0, extra=None):
    if symbol in balance["holdings"]:
        del balance["holdings"][symbol]
        print(f"🗑 보유 목록에서 제거됨 → {symbol}")

    if entry_time is None:
        entry_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    holding = {
        "symbol": symbol,
        "entry_price": entry_price,
        "quantity": quantity,
        "max_price": entry_price,   # 최고가 초기값
        "prev_cci": None,            # 이전 CCI 초기화
        "score": score,
        "expected_profit": expected_profit,
        "target_2": target_2,
        "target_3": target_3,
        "entry_time": entry_time
    }

    if extra:
        holding.update(extra)
    if score is not None:
        holding["score"] = score
    if expected_profit is not None:
        holding["expected_profit"] = expected_profit
    if source is not None:
        holding["source"] = source


    balance["holdings"][symbol] = holding

    # 💾 보유 종목 저장
    save_holdings_to_file()

    print(f"✅ 진입 기록 완료: {symbol} / 진입가: {entry_price} / 수량: {quantity}")

# 🔁 재시작 시 복구용 로드 함수
def load_holdings_from_file(filepath="data/holdings.json"):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("❌ holdings.json → 딕셔너리 아님")

            balance["holdings"] = data.get("holdings", {})  # ✅ 리스트(X) → 딕셔너리(O)
            balance["KRW"] = data.get("KRW", 1000000)

            balance["switched"] = data.get("switched", False)


            print("🔄 holdings.json → 보유 종목 복구 완료")
        except Exception as e:
            print(f"❌ holdings.json 로드 실패: {e}")


def reset_switch_flag():
    global balance
    balance["switched"] = False

def set_switch_flag():
    global balance
    balance["switched"] = True

def has_switched():
    return balance.get("switched", False)

def remove_holding(symbol):
    if symbol in balance["holdings"]:
        del balance["holdings"][symbol]

        print(f"🗑 보유 목록에서 제거됨 → {symbol}")

def get_current_price(symbol):
    candles = get_candles(symbol, interval="1", count=1)
    if candles:
        return candles[0]["trade_price"]
    return 0
