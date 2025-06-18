# ✅ 전략 포지션 유지/청산 판단 공통 함수
from utils.risk import judge_trade_type
from utils.balance import update_balance_after_sell, remove_holding, get_holdings, save_holdings_to_file
from utils.candle import get_candles
from utils.price import get_current_price
from utils.trade import sell_market_order
from sell_strategies.sell_utils import get_indicators


def evaluate_exit(symbol, quantity, source):
    print(f"📌 [{source}] 잔여 종목 평가 → {symbol}")

    candles_15 = get_candles(symbol, interval="15", count=20)
    if not candles_15 or len(candles_15) < 2:
        print(f"⚠️ 캔들 부족 → 유지 판단 불가")
        return False

    hourly_candles = get_candles(symbol, interval="60", count=10)
    is_swing = judge_trade_type(hourly_candles)

    current_price = get_current_price(symbol)

    # ✅ 진입가 불러오기
    entry_price = get_holdings().get(symbol, {}).get("entry_price", 0)

    # ✅ 손절 조건: -2% 도달 시 무조건 청산
    if entry_price and current_price <= entry_price * 0.98:
        print(f"❌ 손절 조건 충족 → 현재가 {current_price} < 진입가 대비 -2%")
        sell_market_order(symbol)
        update_balance_after_sell(symbol, current_price, quantity)
        remove_holding(symbol)
        return False

    # ✅ 최고가 추적
    holding = get_holdings().get(symbol, {})
    max_price = holding.get("max_price", current_price)
    if current_price > max_price:
        holding["max_price"] = current_price
        save_holdings_to_file()

    # ✅ VWAP, OBV 계산
    indicators = get_indicators(candles_15)

    vwap = indicators.get("vwap")
    obv = indicators.get("obv")
    obv_prev = indicators.get("obv_prev")

    # ✅ 조건: 최고가 대비 0.7% 이상 하락 + 종가 < VWAP + OBV 하락
    trailing_high = holding.get("max_price", current_price)
    if (
        current_price <= trailing_high * 0.993 and
        candles_15[0]["trade_price"] < vwap and
        obv < obv_prev
    ):
        print("🎯 트레일링 익절 조건 충족 → 시장가 익절")
        sell_market_order(symbol)
        update_balance_after_sell(symbol, current_price, quantity)
        remove_holding(symbol)
        return False



    # ✅ 단타/스윙 유지 여부 판단
    body = abs(candles_15[0]["trade_price"] - candles_15[0]["opening_price"])
    high = candles_15[0]["high_price"]
    low = candles_15[0]["low_price"]
    range_ratio = (high - low) / current_price * 100 if current_price else 0

    if is_swing:
        print(f"✅ 스윙 조건 충족 → 유지")
        return True

    elif range_ratio >= 1.5 and body >= (high - low) * 0.3:
        print(f"✅ 단타 조건 충족 → 유지")
        return True

    else:
        print(f"❌ 조건 미충족 → 시장가 청산")
        sell_market_order(symbol)
        update_balance_after_sell(symbol, current_price, quantity)
        remove_holding(symbol)
        return False
