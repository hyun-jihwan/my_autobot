# 전략 1 단타 매도 조건 - 완성 버전
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")


from sell_strategies.sell_utils import get_indicators
from utils.balance import balance, save_holdings_to_file, remove_holding


def sell_strategy1(config):
    print("📤 매도 전략 1 실행됨")
    from utils.balance import balance, save_holdings_to_file

    to_delete = []

    for symbol, data in balance["holdings"].items():
        print(f"📤 매도 체크: {symbol}")
        # 여기에 간단히 조건: 무조건 매도
        print(f"✅ 매도 완료: {symbol}")
        to_delete.append(symbol)

    for symbol in to_delete:
        remove_holding(symbol)

    save_holdings_to_file()



def check_sell_signal_strategy1(holding, candles, indicators):
    entry_price = holding["entry_price"]
    expected_profit = holding.get("expected_profit")
    current_price = candles[0]["trade_price"]
    high_prices = [c["high_price"] for c in candles[:5]]
    recent_high = max(high_prices)

    # ➕ 수익률 계산
    profit_rate = (current_price - entry_price) / entry_price

    # 📊 지표
    rsi = indicators["rsi"]
    obv = indicators["obv"]
    obv_prev = indicators["obv_prev"]
    vwap = indicators["vwap"]
    upper_band = indicators["bb_upper"]

    # 🕯 현재 캔들 정보
    c = candles[0]
    close = c["trade_price"]
    open_ = c["opening_price"]
    high = c["high_price"]
    body = abs(close - open_)
    upper_wick = high - max(close, open_)

    # 📈 거래량
    v_now = c["candle_acc_trade_volume"]
    v_avg = sum([c["candle_acc_trade_volume"] for c in candles[1:4]]) / 3

    # ✅ 익절 1: 목표가 도달 → 50% 익절 + 최고가 추적 후 -0.7% 하락 시 전량 익절
    if profit_rate >= expected_profit:
        holding["trailing_high"] = max(high, holding.get("trailing_high", high))  # 최고가 추적
        return "🎯 목표 수익률 도달 → 50% 익절"
    if "trailing_high" in holding:
        trailing_high = holding["trailing_high"]
        if current_price <= trailing_high * 0.993:  # 0.7% 하락
            return "📉 최고가 대비 0.7% 하락 → 전량 익절"

    # ✅ 익절 2: 2개 연속 고점 실패 + 거래량 평균 대비20% 이상 감소
    if (
        high_prices[0] < high_prices[1] and
        high_prices[1] < high_prices[2] and
        v_now < v_avg * 0.8
    ):
        return "🔻 2개 연속 고점 실패 + 거래량 감소 → 전량 익절"

    # ✅ 익절 3: 최고가 기준 0.7% 이상 하락 + RSI 하락 전환 + VWAP 이탈
    if (
        current_price <= recent_high * 0.993 and
        rsi < indicators["rsi_prev"] and
        close < vwap
    ):
        return "📉 최고가 하락 + RSI + VWAP 이탈 → 전량 익절"

    # ✅ 익절 4: 윗꼬리 음봉 + OBV 하락 + 볼밴 상단 이탈
    is_tail = upper_wick > body * 1.5
    if (
        close < open_ and
        is_tail and
        close > upper_band and
        obv < obv_prev
    ):
        return "⚠️ 윗꼬리 음봉 + OBV 하락 + 볼밴 상단 이탈 → 전량 익절"

    # ❌ 손절 1: -2% 손실
    if current_price <= entry_price * 0.98:
        return "❌ -2% 손실 도달 → 전량 손절"

    # ❌ 손절 2: -0.7% 급락 + 음봉 + 거래량 급등
    if (
        current_price <= entry_price * 0.993 and
        close < open_ and
        v_now > v_avg * 1.3
    ):
        return "⚠️ 급락 + 음봉 + 거래량 급등 → 전량 손절"

    return None

def evaluate_swing_exit(symbol, entry_price, target_1, target_2, target_3):
    result = {"action": None, "reason": None}
    candles = get_candles(symbol, interval="60", count=50)
    if not candles or len(candles) < 30:
        return result

    current = candles[0]
    current_price = current["trade_price"]
    highest = max([c["high_price"] for c in candles[:10]])  # 최근 10시간 고점
    volume_now = current["candle_acc_trade_volume"]

    # ✅ 손절조건 1 -2%
    if current_price <= entry_price * 0.98:
        result["action"] = "sell"
        result["reason"] = "진입가 대비 -2% 손절"
        return result

    # ✅ 손절조건 2
    price_drop = (entry_price - current_price) / entry_price * 100
    is_red = current["trade_price"] < current["opening_price"]
    rsi = get_rsi(candles, period=14)
    if price_drop >= 0.7 and is_red and volume_now > candles[1]["candle_acc_trade_volume"] * 1.5:
        if rsi < 50 or is_macd_histogram_decreasing(candles, periods=2):
            result["action"] = "sell"
            result["reason"] = "급락 + 음봉 + RSI or MACD 조건 충족 손절"
            return result

    # ✅ 익절조건 1: 목표가 수익률 기반
    # 1차 도달 시
    if target_1 and current_price >= target_1:
        # 고점 돌파 체크 (최근 2개봉 기준 고점 돌파 여부)
        prev_highs = [c["high_price"] for c in candles[-3:-1]]
        is_breakout = current_price > max(prev_highs)

        # 눌림 여부 판단 (최고가 대비 retrace 비율)
        highest_price = max([c["high_price"] for c in candles[-5:]])
        retrace_ratio = (highest_price - current_price) / highest_price
        is_no_retrace = retrace_ratio <= 0.0382  # 눌림 거의 없음

        # 거래량 유지 여부 (최근 평균보다 낮지 않은가)
        avg_volume = sum([c["candle_acc_trade_volume"] for c in candles[-4:-1]]) / 3
        is_volume_ok = volume_now >= avg_volume

        if is_breakout and is_no_retrace and is_volume_ok:
            result["action"] = "hold"  # 40% 익절 or 유지 판단은 따로 처리
            result["reason"] = "1차 목표가 도달 + 조건 충족 → 유지"
        else:
            result["action"] = "partial_sell"
            result["reason"] = "1차 목표가 도달 → 40% 분할 익절"
        return result


    # 2차 도달 시
    if target_2 and current_price >= target_2:
        # 거래량 유지 여부
        avg_volume = sum([c["candle_acc_trade_volume"] for c in candles[-4:-1]]) / 3
        is_volume_ok = volume_now >= avg_volume

        # 고점 돌파 여부
        prev_highs = [c["high_price"] for c in candles[-3:-1]]
        is_breakout = current_price > max(prev_highs)

        # 볼린저밴드 상단 돌파 여부
        upper_bb = calculate_bollinger_band(candles)[1]
        is_bollinger_break = current_price > upper_bb

        if is_bollinger_break and is_breakout and is_volume_ok:
            result["action"] = "hold"
            result["reason"] = "2차 목표가 도달 + 조건 충족 → 3차 목표가까지 유지"
        else:
            result["action"] = "sell"
            result["reason"] = "2차 목표가 도달 → 전량 익절"
        return result

    # 3차 도달 시
    if target_3 and current_price >= target_3:
        result["action"] = "sell"
        result["reason"] = "3차 목표 도달 → 전량 익절"
        return result
    else:
        touches = sum(1 for c in candles[:12] if c["high_price"] >= target_3)
        recent_high = max([c["high_price"] for c in candles[1:9]])  # 최근 2시간
        if touches >= 2 and recent_high < target_3:
            result["action"] = "sell"
            result["reason"] = "3차 목표 도달 실패 + 2시간 고점 갱신 실패"
            return result

    # ✅ 익절조건 2: 보조지표 기반
    A_trigger = (
        (is_obv_falling(candles) and is_shooting_star(candles)) or
        is_vwap_broken(candles, count=2)
    )
    B_conditions = sum([
        is_macd_dead_cross(candles),
        is_rsi_overbought_exit(candles),
        is_bb_center_broken(candles)
    ])

    if A_trigger or B_conditions >= 2:
        result["action"] = "sell"
        result["reason"] = "보조지표 조건 충족 → 전량 익절"
        return result

    # ✅ 익절조건 3: 지지선 이탈
    support = min([c["low_price"] for c in candles[1:5]])  # 최근 4봉 저가 중 최저
    if current["low_price"] < support and volume_now > candles[1]["candle_acc_trade_volume"]:
        result["action"] = "sell"
        result["reason"] = "지지선 이탈 + 거래량 증가 → 전량 익절"
        return result

    return result

if __name__ == "__main__":
    print("📤 매도 전략 1 테스트 시작")
    from utils.balance import balance
    print("보유 종목:", list(balance["holdings"].keys()))

    # 가짜 config 넣어도 무방
    sell_strategy1(config={})

    print("📤 매도 전략 1 테스트 완료")
    print("잔여 종목:", list(balance["holdings"].keys()))
