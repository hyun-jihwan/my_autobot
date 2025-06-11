# sell_utils.py : 매도 전략에서 쓰는 공통 함수 모음

def get_indicators(candles):
    close_prices = [c["trade_price"] for c in candles]
    volumes = [c["candle_acc_trade_volume"] for c in candles]
    obvs = []

    # ✅ VWAP 계산
    total_volume = sum(volumes)
    total_price_volume = sum([c["trade_price"] * c["candle_acc_trade_volume"] for c in candles])
    vwap = total_price_volume / total_volume if total_volume != 0 else close_prices[0]

    # ✅ RSI 계산 (간단 계산)
    gains = []
    losses = []
    for i in range(1, len(close_prices)):
        diff = close_prices[i] - close_prices[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains) / len(gains) if gains else 0.0001
    avg_loss = sum(losses) / len(losses) if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # ✅ OBV 계산
    obv = 0
    prev_close = close_prices[0]
    for i in range(1, len(close_prices)):
        if close_prices[i] > prev_close:
            obv += volumes[i]
        elif close_prices[i] < prev_close:
            obv -= volumes[i]
        prev_close = close_prices[i]
        obvs.append(obv)
    obv_now = obvs[-1] if obvs else 0
    obv_prev = obvs[-2] if len(obvs) >= 2 else obv_now

    # CCI 계산 (14개 기준)
    period = 14
    cci = None
    if len(candles) >= period:
        typical_prices = [(c["high_price"] + c["low_price"] + c["trade_price"]) / 3 for c in candles]
        recent_tps = typical_prices[-period:]
        ma = sum(recent_tps) / period
        mean_dev = sum([abs(tp - ma) for tp in recent_tps]) / period
        if mean_dev != 0:
            cci = (recent_tps[-1] - ma) / (0.015 * mean_dev)
        else:
            cci = 0


    # ✅ 볼린저밴드 계산 (상단만 사용)
    ma = sum(close_prices) / len(close_prices)
    std = (sum([(x - ma) ** 2 for x in close_prices]) / len(close_prices)) ** 0.5
    bb_upper = ma + 2 * std
    bb_middle = ma

    # ✅ 현재가 기준 볼밴 돌파 여부 판단
    current_price = close_prices[-1]
    bb_upper_break = current_price > bb_upper
    bb_middle_break_down = current_price < bb_middle  # 중심선 이탈

    # ✅ 최근 지지선(최근 4개봉 저점 중 최저값) 계산
    if len(candles) >= 5:
        recent_lows = [c["low_price"] for c in candles[-5:-1]]
        support_level = min(recent_lows)
        support_break = candles[-1]["low_price"] < support_level and \
                        candles[-1]["candle_acc_trade_volume"] > candles[-2]["candle_acc_trade_volume"] * 1.2
    else:
        support_break = False

    # ✅ 유성형 캔들 여부 (가장 최근 봉 기준)
    last_candle = candles[-1]
    o = last_candle["opening_price"]
    c = last_candle["trade_price"]
    h = last_candle["high_price"]
    l = last_candle["low_price"]

    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    total_range = h - l if h != l else 1

    is_shooting_star = (
        body / total_range < 0.3 and
        upper_wick > body * 2 and
        lower_wick < body and
        c < o  # 종가 < 시가 → 음봉
    )

    # ✅ MACD 계산 (EMA 직접 계산)
    macd_dead_cross = False
    if len(close_prices) >= 35:
        def calc_ema(data, period):
            k = 2 / (period + 1)
            ema_list = []
            ema = sum(data[:period]) / period
            ema_list.append(ema)
            for price in data[period:]:
                ema = price * k + ema * (1 - k)
                ema_list.append(ema)
            return ema_list

        ema12 = calc_ema(close_prices, 12)
        ema26 = calc_ema(close_prices, 26)

        if len(ema12) >= len(ema26):
            macd_line = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
            signal_line = calc_ema(macd_line, 9)

            if len(macd_line) >= 2 and len(signal_line) >= 2:
                macd_now = macd_line[-1]
                macd_prev = macd_line[-2]
                signal_now = signal_line[-1]
                signal_prev = signal_line[-2]

                if macd_prev > signal_prev and macd_now < signal_now:
                    macd_dead_cross = True

    return {
        "rsi": rsi,
        "vwap": vwap,
        "obv": obv_now,
        "obv_prev": obv_prev,
        "cci": cci,
        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_upper_break": bb_upper_break,
        "bb_middle_break_down": bb_middle_break_down,
        "support_break": support_break,
        "is_shooting_star": is_shooting_star,
        "macd_dead_cross": macd_dead_cross
    }

