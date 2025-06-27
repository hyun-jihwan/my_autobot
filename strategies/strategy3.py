import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import time
import datetime
from utils.candle import get_candles, get_all_krw_symbols
from utils.balance import (
    get_holding_symbols, get_holdings,
    record_holding, update_balance_after_buy,
    update_balance_after_sell, remove_holding,
    get_krw_balance
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


# ✅ 새로 추가된 전략3 진입 조건 확인 함수
def check_strategy3_entry_condition(candles):
    if len(candles) < 4:
        return False

    latest = candles[-1]  # ✅ 가장 최근 캔들
    prev_candles = candles[-4:-1]  # ✅ 이전 3개 캔들

    prev_high = max(c['high_price'] for c in prev_candles)
    if latest['high_price'] <= prev_high:
        return False

    price_change = (latest['trade_price'] - candles[-2]['trade_price']) / candles[-2]['trade_price']
    if price_change < 0.013:
        return False

    avg_volume = sum(c['candle_acc_trade_volume'] for c in prev_candles) / 3
    if latest['candle_acc_trade_volume'] < avg_volume * 2:
        return False

    # 슬리피지 제한
    if latest['trade_price'] > candles[-2]['trade_price'] * 1.03:
        return False

    # 좋은 캔들 조건
    o, h, l, c = latest['opening_price'], latest['high_price'], latest['low_price'], latest['trade_price']
    body = abs(c - o)
    candle_range = h - l if h != l else 1
    upper_wick = h - max(o, c)
    upper_ratio = upper_wick / body if body != 0 else 1
    body_ratio = body / candle_range

    if body_ratio < 0.4 or upper_ratio > 0.5:
        return False

    # 기대 수익률 3% 이상
    expected_profit = ((c * 1.04) - c) / c
    if expected_profit < 0.03:
        return False


    return True


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
            print(f"[DEBUG] 건너뜀: 이미 보유 중인 종목 → {symbol}")
            continue  # 중복 진입 방지

        candles = get_candles(symbol, interval="1", count=4)
        if len(candles) < 4:
            print(f"[DEBUG] 건너뜀: 캔들 부족 → {symbol}")
            continue

        c1 = candles[-2]
        c0 = candles[-1]

        price_change = ((c0["trade_price"] - c1["trade_price"]) / c1["trade_price"]) * 100
        volume_now = c0["candle_acc_trade_volume"]
        volume_avg = sum(c["candle_acc_trade_volume"] for c in candles[-4:-1]) / 3
        volume_ratio = volume_now / volume_avg if volume_avg != 0 else 0

        if price_change < 1.3 or volume_ratio < 2:
            print(f"[DEBUG] 건너뜀: 상승률 {price_change:.2f}% 또는 거래량비 {volume_ratio:.2f} 불충족")
            continue

        if not recent_high_breakout(candles, c0["trade_price"]):
            print(f"[DEBUG] 건너뜀: 고점 돌파 실패 → 현재가 {c0['trade_price']} vs 이전고점 {max([c['high_price'] for c in candles[:-1]])}")
            continue

        score = calculate_score(price_change, volume_ratio)

        # ✅ 시간대 별 조건 강화
        now = datetime.datetime.now().time()
        if now < datetime.time(18, 0) or now > datetime.time(1, 0):
            if score < 80:
                print(f"[DEBUG] 건너뜀: 점수 {score} < 80 (낮 시간대)")
                continue
        else:
            if score < 60:
                print(f"[DEBUG] 건너뜀: 점수 {score} < 60 (야간)")
                continue

        if not is_good_candle(c0):
            print(f"[DEBUG] 건너뜀: 좋은 캔들 조건 미충족 → {symbol}")
            continue

        # ✅ 슬리피지 제한 (이전 종가 대비 3% 이내만 진입 허용)
        previous_close = c1["trade_price"]
        current_price = c0["trade_price"]

        print(f"[DEBUG] 이전 종가: {previous_close}, 현재가: {current_price}")

        if current_price > previous_close * 1.03:
            print(f"❌ 슬리피지 초과: {current_price} > {previous_close * 1.03}")
            continue

        # ✅ 기대 수익률 3% 이상이어야 진입
        expected_target = current_price * 1.04  # 예시 목표가
        expected_profit = (expected_target - current_price) / current_price
        print(f"[DEBUG] 기대 수익률: {expected_profit:.2%}")

        if expected_profit < 0.03:
            print(f"❌ 기대 수익률 부족: {expected_profit:.2%}")
            continue

        print(f"[DEBUG] 최종 통과: {symbol} (점수: {score})")

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
            h = list(holdings.values())[0]
            if check_strategy1_exit_conditions(h):
                print(f"❌ 전략1 → 수익성 하락 / 박스권 → 청산 후 전략3 진입")
                symbol = h["symbol"]
                sell_price = get_current_price(symbol)
                quantity = h["quantity"]
                update_balance_after_sell(symbol, sell_price, quantity)
                remove_holding(symbol)
            else:
                print(f"⏸ 전략1 → 유지 조건 → 전략3 진입 차단")
                return None

        # ✅ 진입
        capital = config.get("operating_capital", 100000)
        if capital < 5000:
            print("❌ 운영 자금 부족")
            return None

        # 💰 현재 잔고 확인
        current_balance = get_krw_balance()
        if current_balance < 5000:
            print(f"❌ 진입 실패: 현재 잔고 {current_balance:.2f}원이너무 적음")
            return None


        # ✅ 지정가 체결 시도 (5초 기다렸다가 시장가 진입)
        print(f"⏳ 5초 대기 후 지정가 진입 시도 → {symbol} @ {price}")
        time.sleep(5)


        quantity = round(capital / current_price, 4)
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

#테스트 시작

if __name__ == "__main__":
    print("🚀 [전략3 실행 시작]")

    test_mode = True  # ✅ 테스트모드 설정 (True = 테스트, False = 실전)

    # ✅ 공통 설정
    config = {
        "operating_capital": 100000,
        "strategy_switch_mode": False,
    }

    if test_mode:
        print("🧪 [테스트모드] 전략3 전환 조건 수동 평가 중")
        symbols = ["KRW-A", "KRW-B"]

        for symbol in symbols:
            print(f"\n🧪 {symbol}에 대해 전략3 진입 조건 평가 시도")

            candles = get_candles(symbol, interval="1", count=4)
            if not candles or len(candles) < 4:
                print(f"❌ [테스트모드] 캔들 부족 → {symbol}")
                continue

            is_entry = check_strategy3_entry_condition(candles)

            if is_entry:
                print(f"✅ [테스트모드] 전략3 진입 조건 충족 → {symbol}")

                # ✅ 전략1 보유 시 청산 판단
                holdings = get_holdings()
                if holdings:
                    h = list(holdings.values())[0]
                    if check_strategy1_exit_conditions(h):
                        print("🔁 [테스트모드] 전략1 청산 조건 만족 → 청산 후 전략3 진입 실행")
                        sell_price = get_current_price(h["symbol"])
                        quantity = h["quantity"]
                        update_balance_after_sell(h["symbol"], sell_price, quantity)
                        remove_holding(h["symbol"])
                    else:
                        print("⏸ [테스트모드] 전략1 유지 조건 → 전략3 진입 보류")
                        continue  # 전략1 유지 시 신규 진입하지 않음

                        # 전략3 진입 실행
                entry_price = candles[-1]["trade_price"]
                qty = round(config["operating_capital"] / entry_price, 4)
                update_balance_after_buy(config["operating_capital"])
                record_holding(symbol, entry_price, qty, score=999, source="strategy3")
                print(f"✅ [테스트모드] 전략3 진입 실행 완료 → {symbol}")

            else:
                print(f"❌ [테스트모드] 조건 미충족 → {symbol}")

    else:
        # ✅ 실전 실행
        result = run_strategy3(config)
        print(f"✅ 전략3 실행 결과: {result}")

#테스트 종료
