# strategies/strategy2.py
import sys
import os
import json
import math
import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")


from utils.candle import get_candles
from utils.balance import (
    get_krw_balance, update_balance_after_buy,
    get_holding_symbols, record_holding, has_switched,
    get_holdings, save_holdings_to_file, get_max_buyable_amount
)
from holding_manager import handle_existing_holdings
from switch_logic import try_switch, should_switch_to_other, execute_switch_to_new
from switch_manager import has_switched_today, set_switch_today
from utils.error_handler import handle_error


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
    try:
        print(f"\n🕒 [전략2] 실행: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        config["strategy_switch_mode"] = True

        if not is_within_strategy_time():
            print("⛔ 전략2 실행 시간 아님 (09:00~09:15 한정)")
            return None

        holdings = get_holdings()
        if holdings and not has_switched_today():
            h = list(holdings.values())[0]
            sym = h["symbol"]
            ep = h["entry_price"]
            qt = h["quantity"]
            et = h["entry_time"]

            if should_switch_to_other(sym, ep, et):
                from external_api import get_top_gainer
                new_symbol = get_top_gainer()
                now_price = get_candles(sym, interval="1", count=1)[0]["trade_price"]
                execute_switch_to_new(sym, now_price, qt, new_symbol, config)

        switched_symbol, switch_status = try_switch()

        if switch_status == "mode_change_only":
            print(f"🔄 보유 종목 전략만 변경 → {switched_symbol}")

        holdings = get_holdings()
        if switched_symbol in holdings:
            holdings[switched_symbol]["source"] = "strategy2"
            holdings[switched_symbol]["score"] = None
            holdings[switched_symbol]["expected_profit"] = None
            holdings[switched_symbol]["target_2"] = 0
            holdings[switched_symbol]["target_3"] = 0
            save_holdings_to_file()
            print(f"✅ 전략 전환 완료 → {switched_symbol} → strategy2")
        else:
            print(f"⚠️ 전략 전환 대상 보유 종목 없음 → {switched_symbol} 누락")

        if switch_status == "switched":
            print(f"✅ 갈아타기 완료 → 기존 종목: {switched_symbol}")
        elif switch_status != "mode_change_only":
            print("❌ 갈아타기 조건 불충족 or 이미 오늘 갈아탐")

        watchlist = config.get("watchlist", [])
        selected = []

        holding_count = len(get_holding_symbols())
        if holding_count >= 1:
            print("❌ 이미 1종목 보유 중 → 전략2 신규 진입 차단")
            return None

        for symbol in watchlist:
            if has_switched():
                print("🚫 이미 갈아타기 진행됨 → 추가 진입 차단")
                return None

            if symbol == switched_symbol:
                continue

            candles = get_candles(symbol, interval="1", count=16)
            if len(candles) < 16:
                continue

            prev = candles[-2]
            current = candles[-1]
            c = current["trade_price"]
            v_prev = prev["candle_acc_trade_volume"]
            v_now = current["candle_acc_trade_volume"]

            if v_now < v_prev * 1.3:
                continue

            if not recent_high_breakout(candles, c):
                continue

            entry_type = analyze_candle_structure(current)
            if entry_type == "진입금지":
                continue

            if symbol in get_holding_symbols():
                continue

            current_price = c
            capital = config["operating_capital"]

            if capital < 5000:
                continue

            quantity = math.floor((capital / current_price) * 10000) / 10000
            total_cost = quantity * current_price * 1.0005

            if total_cost > capital:
                continue

            if get_krw_balance() < total_cost:
                continue

            update_balance_after_buy(total_cost)
            update_balance_from_upbit()

            record_holding(
                symbol=symbol,
                entry_price=current_price,
                quantity=quantity,
                score=None,
                expected_profit=None,
                target_2=0,
                target_3=0,
                extra={
                    "entry_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "max_price": current_price
                },
                source="strategy2"
            )

            result = {
                "종목": symbol,
                "전략": "strategy2",
                "진입가": current_price,
                "진입시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "진입유형": entry_type,
                "진입금액": total_cost,
                "잔고": get_krw_balance(),
                "전개방식": entry_type,
                "예상수익률": None,
                "목표수익률": None,
                "status": "buy"
            }

            selected.append(result)
            print(f"✅ 전략2 {entry_type} 진입 완료 → {symbol} / {quantity:.4f} @ {current_price}")
            break  # 1종목만 진입

        if not selected:
            print("📭 전략2 조건 충족 종목 없음")
        return selected if selected else None

    except Exception as e:
        handle_error(e, location="run_strategy2", config=config)
        return None
