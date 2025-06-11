from utils.candle import get_candles


def sell_market_order(symbol):
    print(f"✅ 실전 매도 실행 (시장가): {symbol}")
    return True


def calculate_targets(symbol):
    candles_1h = get_candles(symbol, interval="60", count=50)

    # 1. A (추세 시작점)
    A, a_idx = None, None
    for i in range(len(candles_1h) - 20):
        curr = candles_1h[i]
        next_ = candles_1h[i + 1]
        if (
            curr["low_price"] == min([c["low_price"] for c in candles_1h[i:i + 20]]) and
            next_["candle_acc_trade_volume"] > curr["candle_acc_trade_volume"] * 1.5 and
            next_["trade_price"] > next_["opening_price"]
        ):
            A = curr["low_price"]
            a_idx = i
            break

    if A is None:
        return None, None

    # 2. B (1차 고점)
    highs = [c["high_price"] for c in candles_1h[a_idx:a_idx + 20]]
    B = max(highs)
    b_idx = a_idx + highs.index(B)

    # 3. C (되돌림 저점)
    C = None
    for j in range(b_idx, b_idx + 10):
        if j + 2 >= len(candles_1h):
            break
        candle = candles_1h[j]
        next_c1 = candles_1h[j + 1]
        next_c2 = candles_1h[j + 2]

        if (
            candle["low_price"] == min([c["low_price"] for c in candles_1h[b_idx:b_idx + 10]]) and
            next_c1["trade_price"] > next_c1["opening_price"] and
            next_c2["trade_price"] > next_c2["opening_price"]
        ):
            C = candle["low_price"]
            break

    if C is None:
        return None, None

    # 2차/3차 목표가
    target_2 = round(C + (B - A) * 1.272, 4)
    target_3 = round(C + (B - A) * 1.618, 4)

    return target_2, target_3
