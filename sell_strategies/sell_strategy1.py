# 전략 1 단타 매도 조건 - 완성 버전
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

import json
from sell_strategies.sell_utils import get_indicators, check_sell_signal_strategy1
from utils.balance import balance, save_holdings_to_file, remove_holding
from utils.candle import get_candles

def load_holdings_from_file():
    with open("data/holdings.json", "r") as f:
        return json.load(f)


def sell_strategy1(config):
    print("📤 매도 전략1 실행됨")

    balance = load_holdings_from_file()
    holdings = balance.get("holdings", {})
    if not holdings:
        print("⚠️ 현재 보유 중인 종목이 없습니다.")
        return

    to_delete = []

    for symbol, data in holdings.items():
        print(f"📤 매도 체크: {symbol}")
        # 여기에 간단히 조건: 무조건 매도
        entry_price = data["entry_price"]
        quantity = data["quantity"]

        # ✅ 캔들과 보조지표 불러오기
        candles = get_candles(symbol, interval="1", count=10)
        if not candles or len(candles) < 5:
            print(f"⚠️ 캔들 부족: {symbol}")
            continue

        indicators = get_indicators(candles)

        # ✅ 매도 조건 판단
        signal = check_sell_signal_strategy1(data, candles, indicators)

        if signal:
            print(f"✅ 매도 조건 충족: {symbol} / 이유: {signal}")
            to_delete.append(symbol)
        else:
            print(f"⏳ 매도 조건 미충족: {symbol}")

    for symbol in to_delete:
        remove_holding(symbol)

    save_holdings_to_file()
    print("📤 매도 전략 1 완료 — holdings.json 저장됨")


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
    print("🧪 [전략1 매도 조건 평가 트리거] 시작")
    config = {
        "operating_capital": 100000,
        "ready_for_strategy1": False
    }
    sell_strategy1(config)
