def classify_trade_mode(current_candle, rsi, obv_slope, macd_hist):
    """
    진입 직후 단타/스윙 자동 분류
    """
    body = abs(current_candle["trade_price"] - current_candle["opening_price"])
    total = current_candle["high_price"] - current_candle["low_price"]
    body_ratio = body / total if total != 0 else 0

    if body_ratio >= 0.5 and rsi > 70 and macd_hist < 0:
        return "단타"

    if 60 <= rsi <= 70 and obv_slope and macd_hist > 0:
        return "스윙"

    return "단타"

