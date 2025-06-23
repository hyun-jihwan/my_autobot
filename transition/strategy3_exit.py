import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import utils.balance as balance_util
from utils.price import get_current_price
from utils.candle import get_candles
from utils.risk import judge_trade_type
from datetime import datetime
from utils.transition_helper import evaluate_exit
from utils.trade import sell_market_order  # ← 실제 매도 실행
from utils.fibonacci_target import calculate_fibonacci_targets
from sell_strategies.sell_strategy3 import evaluate_exit_strategy3



def transition_strategy3_to_1(config):
    print("🔁 전략3 종료 조건 평가 시작")

    holdings_dict = balance_util.get_holdings()
    print("📦 현재 보유 목록:", holdings_dict)
    released = []

    # 전략3 포지션이 없다면 → 전략1 자동 전환 시작
    if not holdings_dict:
        print("📭 전략3 보유 없음 → 전략1 전환 허용")
        config["ready_for_strategy1"] = True
        return []

    for symbol, h in list(holdings_dict.items()):
        if h.get("source") != "strategy3":
            continue  # 전략3 포지션만 처리

        quantity = h["quantity"]
        entry_price = h["entry_price"]
        entry_time = h.get("entry_time", "N/A")
        current_price = get_current_price(symbol)

        print(f"📌 전략3 잔여 종목 확인: {symbol} / 진입 시간: {entry_time}")

        # ✅ 손절 조건 체크
        risk_cut = 0.015 if current_price < entry_price else 0.02
        if current_price <= entry_price * (1 - risk_cut):
            print(f"❌ [{symbol}] 손절 → 현재가 {current_price:.2f} < {entry_price * (1 - risk_cut):.2f}")
            sell_market_order(symbol)
            balance_util.update_balance_after_sell(symbol, current_price, quantity)
            balance_util.remove_holding(symbol)
            released.append(symbol)
            continue

        # ✅ 매도 조건 체크
        result = evaluate_exit_strategy3(h)
        if result:
            print(f"✅ [{symbol}] 매도 조건 충족 → 청산 완료")
            released.append(symbol)
            continue

        # ✅ 피보나치 목표가 계산
        candles_1h = get_candles(symbol, interval="60", count=10)
        is_swing = judge_trade_type(candles_1h)
        interval = "60" if is_swing else "15"
        candles_for_fib = get_candles(symbol, interval=interval, count=50)

        expected_profit, target_2, target_3 = calculate_fibonacci_targets(candles_for_fib, "스윙" if is_swing else "단타")


        if expected_profit is None:
            print(f"❌ {symbol} → 목표가 계산 실패 → 강제 청산")
            sell_market_order(symbol)
            balance_util.update_balance_after_sell(symbol, current_price, quantity)
            balance_util.remove_holding(symbol)
            released.append(symbol)
            continue


        # ✅ 강한 캔들 여부 체크
        candles_15m = get_candles(symbol, interval="15", count=20)
        if not candles_15m or len(candles_15m) < 1:
            print(f"❌ {symbol} → 15분봉 데이터 부족 → 강제 청산")
            sell_market_order(symbol)
            balance_util.update_balance_after_sell(symbol, current_price, quantity)
            balance_util.remove_holding(symbol)
            released.append(symbol)
            continue 


        last = candles_15m[0]
        body = abs(last["trade_price"] - last["opening_price"])
        high = last["high_price"]
        low = last["low_price"]
        body_ratio = body / (high - low) if (high - low) > 0 else 0



        # ✅ 전환 조건 만족
        if is_swing or body_ratio > 0.5:
            print(f"🔁 전략3 → 전략1 전환 처리 중 → {symbol}")
            balance_util.update_holding_field(symbol, "source", "strategy1")
            balance_util.update_holding_field(symbol, "mode", "스윙" if is_swing else "단타")
            balance_util.update_holding_field(symbol, "expected_profit", expected_profit)
            balance_util.update_holding_field(symbol, "target_2", target_2)
            balance_util.update_holding_field(symbol, "target_3", target_3)
            balance_util.update_holding_field(symbol, "score", 80)
        else:
            # ✅ 전환 조건 미충족 → 강제 청산
            print(f"⛔ {symbol} → 전환 조건 미충족 → 강제 청산")
            sell_market_order(symbol)
            balance_util.update_balance_after_sell(symbol, current_price, quantity)
            balance_util.remove_holding(symbol)
            released.append(symbol)


    # ✅ 전략3 전부 청산된 경우 → 전략1 허용
    if len(released) > 0 and len(balance_util.get_holdings()) == 0:
        print("📭 전략3 포지션 전부 청산 완료 → 전략1 진입 허용")
        config["ready_for_strategy1"] = True

    balance_util.save_holdings_to_file()
    print("📂 최종 holdings 상태:", json.dumps(balance_util.get_holdings(), indent=2, ensure_ascii=False))

    return released


def handle_strategy3_positions():
    """
    전략3 포지션 평가 후 → 전략1 전환 처리
    """
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ config.json 로드 실패: {e}")
        config = {"operating_capital": 100000, "ready_for_strategy1": False}

    return transition_strategy3_to_1(config)


if __name__ == "__main__":
    print("🧪 전략3 → 전략1 테스트 실행 중...")
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ config.json 로드 실패: {e}")
        config = {"operating_capital": 100000, "ready_for_strategy1": False}

    result = transition_strategy3_to_1(config)
    print(f"📤 청산 또는 전환된 종목: {result}")
