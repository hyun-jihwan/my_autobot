# sell_utils.py : 매도 전략에서 쓰는 공통 함수 모음

def get_indicators(symbol, candles):
    #테스트용
    if symbol == "KRW-B":
        print("✅ candles 구조 확인:", type(candles), candles[:1])
        return {
            "rsi": 68,
            "rsi_prev": 72,
            "vwap": 1075.0,          # 현재가(101.5) < VWAP → 조건 1 충족
            "bb_upper": 1078,      # 고가(104) > 상단 & 현재가 101.5 < 상단 → 조건 2 충족
            "cci": 80,              # 이전 >100 / 현재 75 → 조건 3 충족
            "obv": 60000,
            "obv_prev": 62000,      # OBV 하락 → 조건 4 충족 
        }

    #테스트 끝
    close_prices = [c["trade_price"] for c in candles]
    volumes = [c["candle_acc_trade_volume"] for c in candles]

    # ✅ VWAP 계산
    total_volume = sum(volumes)
    total_price_volume = sum([c["trade_price"] * c["candle_acc_trade_volume"] for c in candles])
    vwap = total_price_volume / total_volume if total_volume else close_prices[-1]

    # ✅ RSI 계산 (간단 계산)
    gains, losses = [], []
    for i in range(1, len(close_prices)):
        diff = close_prices[i] - close_prices[i - 1]
        (gains if diff > 0 else losses).append(abs(diff))

    avg_gain = sum(gains) / len(gains) if gains else 0.0001
    avg_loss = sum(losses) / len(losses) if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # rsi_prev
    if len(close_prices) >= 3:
        diff_prev = close_prices[-2] - close_prices[-3]
        gain_prev = diff_prev if diff_prev > 0 else 0
        loss_prev = -diff_prev if diff_prev < 0 else 0
        avg_gain_prev = gain_prev or 0.0001
        avg_loss_prev = loss_prev or 0.0001
        rs_prev = avg_gain_prev / avg_loss_prev
        rsi_prev = 100 - (100 / (1 + rs_prev))
    else:
        rsi_prev = rsi


    # ✅ OBV 계산
    obv, obvs = 0, []
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

        if mean_dev == 0:
            cci = 0
        else:
            cci = (recent_tps[-1] - ma) / (0.015 * mean_dev)


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


def check_sell_signal_strategy1(holding, candles, indicators):
    """
    단타 매도 조건 확인
    """
    symbol = holding["symbol"]
    entry_price = holding["entry_price"]
    expected_profit = holding.get("expected_profit")
    current_price = candles[-1]["trade_price"]
    high_prices = [c["high_price"] for c in candles[:-5]]
    recent_high = max(high_prices)

    # ✅ 최고가 갱신 로직 (계속 추적)
    current_high = candles[-1]["high_price"]
    trailing_high = holding.get("trailing_high", entry_price)

    if current_high > trailing_high:
        holding["trailing_high"] = current_high
        print(f"📈 최고가 갱신됨 → {symbol}: {trailing_high} → {current_high}")


    # 📊 지표
    rsi = indicators["rsi"]
    rsi_prev = indicators["rsi_prev"]
    obv = indicators["obv"]
    obv_prev = indicators["obv_prev"]
    vwap = indicators["vwap"]
    upper_band = indicators["bb_upper"]

    # 🕯 현재 캔들 정보
    c = candles[-1]
    close = c["trade_price"]
    open_ = c["opening_price"]
    high = c["high_price"]
    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    # 📈 거래량
    v_now = c["candle_acc_trade_volume"]
    v_avg = sum([c["candle_acc_trade_volume"] for c in candles[1:4]]) / 3


    # ✅ 손절 먼저 체크
    if current_price <= entry_price * 0.98:
        return "❌ -2% 손실 도달 → 전량 손절"

    if (
        current_price <= entry_price * 0.993 and
        close < open_ and
        v_now > v_avg * 1.3
    ):
        return "⚠️ 급락 + 음봉 + 거래량 급등 → 전량 손절"


    # ✅ 익절 조건
    profit_rate = (current_price - entry_price) / entry_price

    print(f"🧾 {symbol} 진입가: {entry_price}, 현재가: {current_price}, 수익률: {profit_rate:.2%}")

    # ✅ 익절 1: 목표가 도달 → 50% 익절 + 최고가 추적 후 -0.7% 하락 시 전량 익절
    if expected_profit and profit_rate >= expected_profit:
        holding["trailing_high"] = max(high, holding.get("trailing_high", high))  # 최고가 추적
        return "🎯 목표 수익률 도달 → 50% 익절"

    if "trailing_high" in holding:
        trailing_high = holding["trailing_high"]
        if current_price <= trailing_high * 0.993:  # 0.7% 하락
            return "📉 최고가 대비 0.7% 하락 → 전량 익절"

    # ✅ 익절 2: 2개 연속 고점 실패 + 거래량 평균 대비20% 이상 감소
    if high_prices[0] < high_prices[1] and high_prices[1] < high_prices[2] and v_now < v_avg * 0.8:
        return "🔻 2개 연속 고점 실패 + 거래량 감소 → 전량 익절"

    # ✅ 익절 3: 최고가 기준 0.7% 이상 하락 + RSI 하락 전환 + VWAP 이탈
    if current_price <= recent_high * 0.993 and rsi < rsi_prev and close < vwap:
        return "📉 최고가 하락 + RSI + VWAP 이탈 → 전량 익절"

    # ✅ 익절 4: 윗꼬리 음봉 + OBV 하락 + 볼밴 상단 이탈
    is_tail = upper_wick > body * 1.5
    if close < open_ and is_tail and close > upper_band and obv < obv_prev:
        return "⚠️ 윗꼬리 음봉 + OBV 하락 + 볼밴 상단 이탈 → 전량 익절"

    return None

def check_sell_signal_strategy_swing(holding, candles, indicators):
    symbol = holding["symbol"]
    entry = holding["entry_price"]
    target_1 = holding.get("target_2")
    target_2 = holding.get("target_3")
    target_3 = holding.get("target_3")  # 동일 값 유지

    current = candles[-1]
    current_price = current["trade_price"]
    volume_now = current["candle_acc_trade_volume"]
    open_ = current["opening_price"]

    # ✅ 최고가 갱신 로직 (계속 추적)
    current_high = current["high_price"]
    trailing_high = holding.get("trailing_high", entry)

    if current_high > trailing_high:
        holding["trailing_high"] = current_high
        print(f"📈 [스윙] 최고가 갱신됨 → {symbol}: {trailing_high} → {current_high}")

    # 손절 조건
    if current_price <= entry * 0.98:
        return "❌ 진입가 -2% 손절"
    if (
        current_price <= entry * 0.993 and
        current_price < open_ and
        volume_now > candles[1]["candle_acc_trade_volume"] * 1.5
    ):
        return "❌ 급락 + 음봉 + 거래량 급등 → 손절"

    # ✅ 1차 목표가 도달
    if target_1 and current_price >= target_1:
        highs = [c["high_price"] for c in candles[-3:-1]]
        is_breakout = current_price > max(highs)
        high5 = max(c["high_price"] for c in candles[-5:])
        retrace = (high5 - current_price) / high5
        avg_vol = sum([c["candle_acc_trade_volume"] for c in candles[-4:-1]]) / 3

        if is_breakout and retrace <= 0.0382 and volume_now >= avg_vol:
            return "✅ 1차 목표가 도달 + 조건 충족 → 유지"
        else:
            return "✅ 1차 목표가 도달 → 40% 분할 익절"

    # ✅ 2차 목표가 도달
    if target_2 and current_price >= target_2:
        highs = [c["high_price"] for c in candles[-3:-1]]
        is_breakout = current_price > max(highs)
        avg_vol = sum([c["candle_acc_trade_volume"] for c in candles[-4:-1]]) / 3
        ma = sum([c["trade_price"] for c in candles]) / len(candles)
        std = (sum([(c["trade_price"] - ma) ** 2 for c in candles]) / len(candles)) ** 0.5
        bb_upper = ma + 2 * std

        if current_price > bb_upper and is_breakout and volume_now >= avg_vol:
            return "✅ 2차 목표가 + 조건 충족 → 3차 목표가까지 유지"
        else:
            return "✅ 2차 목표가 도달 → 전량 익절"

    # ✅ 3차 목표가 도달 → 전량 익절
    if target_3 and current_price >= target_3:
        return "✅ 3차 목표가 도달 → 전량 익절"

    # ✅ 3차 목표가 도달 실패 + 2시간 고점 갱신 실패
    if target_3:
        touches = sum(1 for c in candles[:12] if c["high_price"] >= target_3)
        recent_high = max([c["high_price"] for c in candles[1:9]])
        if touches >= 2 and recent_high < target_3:
            return "❌ 3차 목표가 도달 실패 + 2시간 고점 미갱신 → 전량 익절"

    # ✅ 보조지표 A그룹 조건
    A_trigger = (
        (indicators["obv"] < indicators["obv_prev"] and indicators["is_shooting_star"]) or
        indicators.get("vwap_break_2bars", False)
    )

    # ✅ B 그룹 조건 체크 (3개 중 2개 이상)
    B_count = 0
    if indicators.get("macd_dead_cross"): B_count += 1
    if indicators.get("rsi") < 70 and indicators.get("rsi_prev", 80) > 70: B_count += 1
    if indicators.get("bb_middle_break_down"): B_count += 1

    if A_trigger or B_count >= 2:
        return "⚠️ 보조지표 조건 충족 (A or B) → 전량 익절"

    # ✅ 최근 지지선 이탈 + 거래량 증가
    if len(candles) >= 5:
        recent_lows = [c["low_price"] for c in candles[1:5]]
        support = min(recent_lows)
        if (
            current["low_price"] < support and
            volume_now > candles[1]["candle_acc_trade_volume"]
        ):
            return "📉 단기 지지선 이탈 + 거래량 증가 → 전량 익절"

    return None
