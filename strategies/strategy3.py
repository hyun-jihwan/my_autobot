import datetime
from utils.candle import get_candles, get_all_krw_symbols
from utils.balance import (
    get_holding_symbols, get_holdings,
    record_holding, update_balance_after_buy,
    update_balance_after_sell, remove_holding
)
from utils.price import get_current_price


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
    if not is_active_time():
        print("⛔ 전략3 실행 시간 아님")
        return None

    watchlist = get_all_krw_symbols()
    selected = []

    best_candidate = None
    best_score = 0

    for symbol in watchlist:
        if symbol in get_holding_symbols():
            continue  # 중복 진입 방지

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

        # ✅ 시간대 별 조건 강화
        now = datetime.datetime.now().time()
        if now < datetime.time(18, 0) or now > datetime.time(1, 0):
            if score < 80:
                continue
        else:
            if score < 60:
                continue

        if not is_good_candle(c0):
            continue

        # ✅ 점수 최고 종목만 진입
        if score > best_score:
            best_candidate = {
                "symbol": symbol,
                "price": c0["trade_price"],
                "score": round(score, 2)
            }
            best_score = score

    if best_candidate:
        symbol = best_candidate["symbol"]
        price = best_candidate["price"]
        score = best_candidate["score"]
        print(f"🔥 전략3 급등 감지 → {symbol} / 점수: {score}")

        # ✅ 전략1 보유 시 청산 판단
        holdings = get_holdings()
        if holdings:
            h = holdings[0]
            if check_strategy1_exit_conditions(h):
                print(f"❌ 전략1 → 수익성 하락 / 박스권 → 청산 후 전략3 진입")
                update_balance_after_sell(get_current_price(h["symbol"]) * h["quantity"])
                remove_holding(h["symbol"])
            else:
                print(f"⏸ 전략1 → 유지 조건 → 전략3 진입 차단")
                return None

        # ✅ 진입
        capital = config.get("operating_capital", 0)
        if capital < 5000:
            print("❌ 운영 자금 부족")
            return None

        quantity = capital / price
        update_balance_after_buy(capital)
        record_holding(symbol, price, quantity, score=score, source="strategy3")

        result = {
            "종목": symbol,
            "전략": "strategy3",
            "진입가": price,
            "진입시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "점수": score
        }
        selected.append(result)
        print(f"✅ 전략3 진입 완료 → {symbol} / 진입가: {price} / 수량: {quantity:.2f}")

    else:
        print("📭 전략3 조건 충족 종목 없음")

    return selected if selected else None

