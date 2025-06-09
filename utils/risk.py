def calculate_expected_risk(candles):
    entry_price = candles[-1]["trade_price"]

    # 최근 고점 (20봉 중 최고가)
    highs = [c["high_price"] for c in candles[-20:]]
    resistance = max(highs)

    # 예상 수익률 (%)
    expected_profit = ((resistance - entry_price) / entry_price) * 100

    # 예상 손실률 (고정 -2%)
    expected_loss = 2.0

    # 손익비 계산
    rr = expected_profit / expected_loss if expected_loss != 0 else 0

    return round(expected_profit, 2), round(expected_loss, 2), round(rr, 2)

def judge_trade_type(candles):
    """
    캔들 패턴과 거래량 기반 단타/스윙 자동 판단 함수
    - 빠르게 상승하고 거래량 급증: 단타
    - 완만한 상승 + RSI/OBV 강세: 스윙
    """
    from utils.indicators import calculate_indicators

    indicators = calculate_indicators(candles)

    # 조건: 스윙 판별
    if indicators.get("RSI") and indicators.get("OBV") and not indicators.get("MA"):
        return True  # 스윙 조건
    return False  # 단타 조건

# 단타매매
def calculate_scalping_target(candles):
    current_price = candles[0]["trade_price"]

    # 직전 고점 찾기 (3~5봉 전)
    highs = [c["high_price"] for c in candles[1:6]]
    resistance = max(highs)

    # 손절 기준: -2% 고정
    stop_loss = current_price * 0.98

    # 손익비 고려한 목표가: 최소 RR 1:2
    min_target = current_price + ((current_price - stop_loss) * 2)

    # 저항선이 그보다 낮으면? → 손익비 부족 → 진입불가
    expected_target = min(min_target, resistance)
    expected_profit = (expected_target - current_price) / current_price * 100
    expected_loss = (current_price - stop_loss) / current_price * 100
    rr = expected_profit / expected_loss if expected_loss > 0 else 0

    return round(expected_profit, 2), round(expected_loss, 2), round(rr, 2)

# 스윙매매
def calculate_swing_target_with_fibonacci(candles):
    current_price = candles[0]["trade_price"]

    # 최근 30봉에서 최저가와 최고가 찾기 (파동 기준)
    lows = [c["low_price"] for c in candles[:30]]
    highs = [c["high_price"] for c in candles[:30]]

    lowest = min(lows)    # 기준파동 저점
    highest = max(highs)  # 기준파동 고점

    # ✅ 피보나치 확장 계산 (0.618, 1.0, 1.618)
    range_diff = highest - lowest
    fib_0618 = highest + range_diff * 0.618
    fib_1000 = highest + range_diff * 1.0
    fib_1618 = highest + range_diff * 1.618

   # ✅ 시장 강도 자동 감지 (예시: 마지막 3봉 기준)
    close_prices = [c["trade_price"] for c in candles[:3]]
    up_count = sum(1 for i in range(2) if close_prices[i] < close_prices[i + 1])

    if up_count == 0:
        market_mode = "보수장"
    elif up_count == 1:
        market_mode = "중립장"
    else:
        market_mode = "강세장"

    # 손절 기준 (기본 -4%)
    stop_loss = current_price * 0.96
    expected_loss = ((current_price - stop_loss) / current_price) * 100

    # ✅ 시장 상황에 따라 목표가 결정
    if market_mode == "보수장":
        target_price = fib_0618
    elif market_mode == "중립장":
        target_price = fib_1000
    else:
        target_price = fib_1618

    # 예상 수익률 및 손익비 계산
    expected_profit = ((target_price - current_price) / current_price) * 100
    rr = expected_profit / expected_loss if expected_loss > 0 else 0

    return (
        round(expected_profit, 2),
        round(expected_loss, 2),
        round(rr, 2),
        fib_0618,
        fib_1000,
        fib_1618,
        market_mode
    )
