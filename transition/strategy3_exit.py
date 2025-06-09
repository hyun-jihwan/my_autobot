from utils.balance import get_holdings, get_current_price, update_balance_after_sell, remove_holding
from utils.candle import get_candles
from utils.risk import judge_trade_type
from datetime import datetime

def handle_strategy3_exit(config):
    print("🔁 전략3 종료 조건 평가 시작")
    holdings = get_holdings()

    # 전략3 포지션이 없다면 → 전략1 자동 전환 시작
    if not holdings:
        print("📭 전략3 보유 없음 → 전략1 전환 허용")
        config["ready_for_strategy1"] = True
        return []

    released = []

    for h in holdings:
        if h.get("source") != "strategy3":
            continue  # 전략3 포지션만 처리

        symbol = h["symbol"]
        entry_time = h.get("entry_time", "N/A")
        quantity = h["quantity"]

        print(f"📌 전략3 잔여 종목 확인: {symbol} / 진입 시간: {entry_time}")

        # 1시간봉 기준 스윙 판단
        hourly_candles = get_candles(symbol, interval="60", count=10)
        is_swing = judge_trade_type(hourly_candles)

        # 15분봉 기준 단타 판단
        candles_15 = get_candles(symbol, interval="15", count=20)
        last = candles_15[0]
        body = abs(last["trade_price"] - last["opening_price"])
        high = last["high_price"]
        low = last["low_price"]
        body_ratio = body / (high - low) if (high - low) > 0 else 0

        if is_swing:
            print(f"✅ 스윙 조건 충족 → 유지 결정: {symbol}")
            continue
        elif body_ratio > 0.5:
            print(f"✅ 단타 조건 충족 (강한 캔들) → 유지 결정: {symbol}")
            continue
        else:
            print(f"❌ 조건 미충족 → 시장가 청산: {symbol}")
            current_price = get_current_price(symbol)
            update_balance_after_sell(current_price * quantity)
            remove_holding(symbol)
            released.append(symbol)

    return released
