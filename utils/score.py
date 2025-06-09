def calculate_score_full(candles, pattern_matched, indicator_result, expected_profit, expected_loss):
    score = 0

    # 1. 📈 패턴 강도 (최대 20점)
    if pattern_matched:
        # 기본 10점
        pattern_score = 10

        # 양봉 여부 확인
        last_candle = candles[-1]
        is_bullish = last_candle["trade_price"] > last_candle["opening_price"]

        # 거래량 비교: 직전봉 대비 1.2배 이상
        if len(candles) >= 2:
            current_vol = last_candle["candle_acc_trade_volume"]
            prev_vol = candles[-2]["candle_acc_trade_volume"]
            volume_ratio = current_vol / prev_vol if prev_vol != 0 else 0
            if is_bullish and volume_ratio >= 1.2:
                pattern_score += 10  # 조건 명확하면 총 20점
            elif is_bullish:
                pattern_score += 5  # 일부 충족 시 15점
        score += pattern_score
    else:
        score += 0

    # 2. 📊 거래량 신뢰도 (최대 15점)
    if len(candles) >= 2:
        current_vol = candles[-1]["candle_acc_trade_volume"]
        prev_vol = candles[-2]["candle_acc_trade_volume"]
        volume_ratio = current_vol / prev_vol if prev_vol != 0 else 0

        if volume_ratio >= 2.0:
            score += 15
        elif 1.2 <= volume_ratio < 2.0:
            score += 10
        else:
            score += 0

    # 3. ⚙️ 보조지표 충족 수 (최대 25점)
    satisfied = sum(1 for val in indicator_result.values() if val)
    if satisfied == 6:
        score += 25
    elif satisfied == 5:
        score += 20
    elif satisfied == 4:
        score += 15

    # 4. 💰 예상 수익률 (최대 20점)
    if expected_profit >= 5:
        score += 20
    elif 3 <= expected_profit < 5:
        score += 15
    elif 2 <= expected_profit < 3:
        score += 10

    # 5. ❗ 리스크 대비 수익 (최대 10점)
    diff = expected_profit - expected_loss
    if diff >= 3:
        score += 10
    elif diff >= 2:
        score += 7
    elif diff >= 1:
        score += 5
    else:
        score += 0

    # 6. 🧠 캔들 강도 (최대 10점)
    last = candles[-1]
    body = abs(last["trade_price"] - last["opening_price"])
    upper_shadow = last["high_price"] - max(last["trade_price"], last["opening_price"])
    lower_shadow = min(last["trade_price"], last["opening_price"]) - last["low_price"]

    total_range = body + upper_shadow + lower_shadow
    if total_range == 0:
        candlestick_strength = 0
    else:
        candlestick_strength = body / total_range  # 실체 비율

    if candlestick_strength >= 0.7:
        score += 10
    elif candlestick_strength >= 0.5:
        score += 7
    elif candlestick_strength >= 0.3:
        score += 5

    return round(score)
