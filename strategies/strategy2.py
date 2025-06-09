# strategies/strategy2.py

import datetime
from utils.candle import get_candles
from utils.balance import (
    get_krw_balance, update_balance_after_buy,
    get_holding_symbols, record_holding
)
from holding_manager import handle_existing_holdings
from switch_logic import try_switch
from switch_manager import has_switched_today, set_switch_today


def is_within_strategy_time():
    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, now.day, 9, 0)
    end = datetime.datetime(now.year, now.month, now.day, 9, 15, 59)
    return start <= now <= end


def recent_high_breakout(candles, current_price):
    highs = [c["high_price"] for c in candles[:-1]]  # 최근 15분 기준
    return current_price > max(highs)


def analyze_candle_structure(candle):
    o, h, l, c = candle["opening_price"], candle["high_price"], candle["low_price"], candle["trade_price"]
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    range_ = h - l if h != l else 1  # 0으로 나누지 않게 처리

    body_ratio = body / range_
    upper_ratio = upper_wick / body if body != 0 else 1
    lower_ratio = lower_wick / body if body != 0 else 1

    if body_ratio >= 0.6 and upper_ratio <= 0.3:
        return "공격진입"
    elif body_ratio >= 0.4 and upper_ratio <= 0.4:
        return "보수진입"
    else:
        return "진입금지"


def run_strategy2(config):
    if not is_within_strategy_time():
        print("⛔ 전략2 실행 시간 아님 (09:00~09:15 한정)")
        return None

    # ✅ 장시작 전 보유 종목 정리
    handle_existing_holdings(config)

    # ✅ 갈아타기 판단 (하루 1회 제한)
    switched_symbol, _ = try_switch()

    watchlist = config.get("watchlist", [])
    selected = []


    for symbol in watchlist:
        if symbol == switched_symbol:
            continue  # 방금 청산한 종목이면 재진입 금지


        candles = get_candles(symbol, interval="1", count=16)  # 15개 + 현재 캔들

        if len(candles) < 16:
            continue

        prev = candles[-2]
        current = candles[-1]

        o, h, l, c = current["opening_price"], current["high_price"], current["low_price"], current["trade_price"]
        v_prev = prev["candle_acc_trade_volume"]
        v_now = current["candle_acc_trade_volume"]

        if v_now < v_prev * 1.3:
            continue  # 거래량 부족

        if not recent_high_breakout(candles, c):
            continue  # 고점 돌파 실패

        entry_type = analyze_candle_structure(current)
        if entry_type == "진입금지":
            continue

        if symbol in get_holding_symbols():
            print(f"❌ 이미 보유 중 → {symbol}")
            continue

        # ✅ 진입 실행
        capital = config.get("operating_capital", 0)

        if capital < 5000:
            print("❌ 운영 자금 부족 (최소 5000원 필요)")
            continue

        quantity = capital / c
        update_balance_after_buy(capital)
        record_holding(symbol, c, quantity)

        result = {
            "종목": symbol,
            "전략": "strategy2",
            "진입가": c,
            "진입시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "진입유형": entry_type
        }

        selected.append(result)
        print(f"✅ 전략2 {entry_type} 완료 → {symbol} / 진입가: {c} / 수량: {quantity:.2f}")
        break  # 1종목만 진입

    return selected if selected else None
