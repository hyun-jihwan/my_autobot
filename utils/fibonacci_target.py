# utils/fibonacci_target.py

def calculate_fibonacci_targets(candles: list, mode: str = "스윙"):
    """
    피보나치 기반 목표가 계산 함수
    - candles: OHLCV 리스트 (최신이 앞에 있어야 함)
    - mode: "스윙" or "단타"
    """

    # 캔들은 최신순으로 들어오는 경우가 많기 때문에 역순 정렬
    candles = list(reversed(candles))

    lookback = 5  # A 추세 시작점 탐색 범위
    A, B, C = None, None, None
    a_idx, b_idx, c_idx = None, None, None

    # A: 추세 시작점 탐색
    for i in range(len(candles) - lookback - 2):
        c = candles[i]
        next_c = candles[i + 1]
        low_range = [x["low_price"] for x in candles[i:i + lookback]]

        if (
            c["low_price"] == min(low_range) and
            next_c["candle_acc_trade_volume"] > c["candle_acc_trade_volume"] * 1.5 and
            next_c["trade_price"] > next_c["opening_price"]
        ):
            A = c["low_price"]
            a_idx = i
            break

    if A is None:
        return None, None, None

    # B: 고점 탐색 (a_idx 이후 20개 내)
    high_range = [c["high_price"] for c in candles[a_idx:a_idx + 20]]
    B = max(high_range)
    b_idx = a_idx + high_range.index(B)

    # C: 되돌림 저점 탐색
    for j in range(b_idx, b_idx + 10):
        try:
            c = candles[j]
            next1 = candles[j + 1]
            next2 = candles[j + 2]

            low_range = [x["low_price"] for x in candles[b_idx:b_idx + 10]]

            if (
                c["low_price"] == min(low_range) and
                next1["trade_price"] > next1["opening_price"] and
                next2["trade_price"] > next2["opening_price"]
            ):
                C = c["low_price"]
                c_idx = j
                break
        except IndexError:
            break

    if A is None or B is None or C is None:
        return None, None, None

    # 피보나치 계산
    diff = B - A

    if mode == "스윙":
        target_1 = C + diff * 1.0
        target_2 = C + diff * 1.272
        target_3 = C + diff * 1.618

    elif mode == "단타":
        target_1 = C + diff * 0.9  # 중간값
        target_2 = C + diff * 1.272
        target_3 = C + diff * 1.414

    else:
        raise ValueError("mode는 '스윙' 또는 '단타'여야 합니다.")

    # 예상 수익률 (%) 반환
    expected_profit_percent = ((target_1 - C) / C) * 100

    return round(expected_profit_percent, 2), round(target_2, 3), round(target_3, 3)
