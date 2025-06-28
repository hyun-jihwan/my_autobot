import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import datetime
from utils.candle import get_candles, get_all_krw_symbols
from utils.balance import (
    get_holding_symbols, get_holdings,
    record_holding, update_balance_after_buy,
    update_balance_after_sell, remove_holding,
    get_krw_balance
)
from utils.price import get_current_price
from utils.telegram import notify_transition
from utils.error_handler import handle_error


def is_active_time():
    now = datetime.datetime.now().time()
    return now >= datetime.time(9, 16) or now <= datetime.time(8, 59)


def recent_high_breakout(candles, current_price):
    highs = [c["high_price"] for c in candles[:-1]]
    return current_price > max(highs)


def calculate_score(price_change, volume_ratio):
    return price_change * volume_ratio * 10


def is_good_candle(candle):
    o, h, l, c = candle["opening_price"], candle["high_price"], candle["low_price"], candle["trade_price"]
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    candle_range = h - l if h != l else 1

    body_ratio = body / candle_range
    upper_ratio = upper_wick / body if body != 0 else 1

    return body_ratio >= 0.4 and upper_ratio <= 0.5


def check_strategy1_exit_conditions(holding):
    # 조건 1: 하락 전환
    symbol = holding["symbol"]
    candles = get_candles(symbol, interval="15", count=3)
    if not candles or len(candles) < 2:
        return False

    if candles[0]["trade_price"] < candles[1]["trade_price"]:
        return True

    # 조건 2: 기대 수익률 하락
    entry_price = holding.get("entry_price", 0)
    now_price = get_current_price(symbol)
    if now_price < entry_price * 1.02:  # 기대 수익률 2% 미만
        return True

    # 조건 3: 박스권 흐름
    last_range = candles[0]["high_price"] - candles[0]["low_price"]
    if last_range / candles[0]["trade_price"] < 0.005:  # 0.5% 이내
        return True

    return False



def run_strategy3(config):
    try:
        if not is_active_time():
            print("⛔ 전략3 실행 시간 아님")
            return None

        if len(get_holding_symbols()) >= 1:
            print("❌ 이미 1종목 보유 중 → 전략3 신규 진입 차단")
            return None

        watchlist = get_all_krw_symbols()
        best_candidate = None
        best_score = 0

        for symbol in watchlist:
            if symbol in get_holding_symbols():
                continue

            candles = get_candles(symbol, interval="1", count=4)
            if len(candles) < 4:
                continue

            c1 = candles[-2]
            c0 = candles[-1]
            price_change = ((c0["trade_price"] - c1["trade_price"]) / c1["trade_price"]) * 100
            volume_now = c0["candle_acc_trade_volume"]
            volume_avg = sum(c["candle_acc_trade_volume"] for c in candles[-4:-1]) / 3
            volume_ratio = volume_now / volume_avg if volume_avg != 0 else 0

            if price_change < 1.3 or volume_ratio < 2:
                continue

            if not recent_high_breakout(candles, c0["trade_price"]):
                continue

            score = calculate_score(price_change, volume_ratio)

            now = datetime.datetime.now().time()
            if (now < datetime.time(18, 0) or now > datetime.time(1, 0)) and score < 80:
                continue
            elif score < 60:
                continue

            if not is_good_candle(c0):
                continue

            previous_close = c1["trade_price"]
            current_price = c0["trade_price"]
            if current_price > previous_close * 1.03:
                continue

            expected_profit = 0.04

            if score > best_score:
                best_candidate = {
                    "symbol": symbol,
                    "price": current_price,
                    "score": round(score, 2)
                }
                best_score = score

        if best_candidate:
            symbol = best_candidate["symbol"]
            price = best_candidate["price"]
            score = best_candidate["score"]

            holdings = get_holdings()
            if holdings:
                h = list(holdings.values())[0]
                held_symbol = h["symbol"]
                sell_price = get_current_price(held_symbol)
                quantity = h["quantity"]

                if check_strategy1_exit_conditions(h):
                    update_balance_after_sell(held_symbol, sell_price, quantity)
                    remove_holding(held_symbol)
                    notify_transition(
                        symbol=held_symbol,
                        from_strategy="1",
                        to_strategy="3",
                        success=True,
                        config=config
                    )
                else:
                    notify_transition(
                        symbol=held_symbol,
                        from_strategy="1",
                        to_strategy="3",
                        success=False,
                        exit_type="유지",
                        config=config
                    )
                    return None

            capital = config.get("operating_capital", 100000)
            if capital < 5000 or get_krw_balance() < 5000:
                print("❌ 운영 자금 부족")
                return None

            print(f"⏳ 5초 대기 후 진입 시도: {symbol} @ {price}")
            time.sleep(5)

            position = capital  # 현재 구조에서는 position = capital로 간주
            quantity = round(position / price, 4)
            total_cost = quantity * price * 1.0005  # 수수료 포함

            if get_krw_balance() < total_cost:
                print(f"❌ 잔고 부족: 필요 {total_cost:.0f}, 보유 {get_krw_balance():.0f}")
                return None

            update_balance_after_buy(total_cost)
            print(f"✅ 매수 후 잔고: {get_krw_balance():,.0f}원")

            record_holding(
                symbol=symbol,
                entry_price=price,
                quantity=quantity,
                score=score,
                expected_profit=expected_profit,
                source="strategy3"
            )

            result = {
                "종목": symbol,
                "전략": "strategy3",
                "진입가": price,
                "진입시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "점수": score,
                "진입금액": int(total_cost),
                "잔고": int(get_krw_balance()),
                "전개방식": "단타",
                "예상수익률": round(expected_profit * 100, 2),
                "목표수익률": 4.0,
                "status": "buy"
            }
            print(f"✅ 전략3 진입 완료 → {result}")
            return result

        print("📭 전략3 조건 충족 종목 없음")
        return None

    except Exception as e:
        handle_error(e, location="run_strategy3", config=config)
        return None

