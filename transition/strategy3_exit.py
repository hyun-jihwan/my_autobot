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




def handle_strategy3_exit(config):
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

        # ✅ 손절 조건 체크
        risk_cut = 0.015 if current_price < entry_price else 0.02
        print(f"[DEBUG] 현재가: {current_price}, 진입가: {entry_price}, 손절 기준가: {entry_price * (1 - risk_cut):.2f}")

        if current_price <= entry_price * (1 - risk_cut):
            print(f"❌ [{symbol}] 손절 조건 충족 → 현재가 {current_price:.2f} < 진입가 {entry_price:.2f} -{risk_cut*100:.1f}%")
            sell_market_order(symbol)
            balance_util.update_balance_after_sell(symbol, current_price, quantity)
            balance_util.remove_holding(symbol)
            released.append(symbol)

            config["ready_for_strategy1"] = True  # ✅ 전략1 전환 허용
            continue

        print(f"📌 전략3 잔여 종목 확인: {symbol} / 진입 시간: {entry_time}")

        # 1시간봉 기준 스윙 판단
        hourly_candles = get_candles(symbol, interval="60", count=10)

        if not hourly_candles or len(hourly_candles) < 5:
            print(f"❌ {symbol} → 1시간봉 캔들 부족 → 건너뜀")
            continue

        is_swing = judge_trade_type(hourly_candles)
        candles_15 = get_candles(symbol, interval="15", count=20)
        if not candles_15 or len(candles_15) < 1:
            print(f"❌ {symbol} → 15분봉 캔들 데이터 부족 → 건너뜀")
            continue

        last = candles_15[0]
        body = abs(last["trade_price"] - last["opening_price"])
        high = last["high_price"]
        low = last["low_price"]
        body_ratio = body / (high - low) if (high - low) > 0 else 0
        print(f"📈 body_ratio: {body_ratio:.3f}")

        if is_swing:
            print(f"🔁 전략3 → 전략1 전환 처리 (스윙): {symbol}")
            print(f"⚙️ update_holding_field 실행 직전 (스윙)")
            balance_util.update_holding_field(symbol, "source", "strategy1")
            balance_util.update_holding_field(symbol, "mode", "스윙")
            continue

        elif body_ratio > 0.5:
            print(f"✅ 단타 조건 충족 (강한 캔들) → 유지 결정: {symbol}")
            print(f"🔁 전략3 → 전략1 전환 처리 (단타): {symbol}")
            balance_util.update_holding_field(symbol, "source", "strategy1")
            balance_util.update_holding_field(symbol, "mode", "단타")
            continue

        # ✅ 전략3 종료 판단 (익절 조건 등)
        result = evaluate_exit(symbol, quantity, source="strategy3")
        if result is False:  # 매도 조건 충족
            released.append(symbol)
        else:
            print(f"✅ 전략3 유지 결정: {symbol}")

    # ✅ 전략3 전부 청산된 경우 → 전략1 허용
    if len(released) > 0 and len(balance_util.get_holdings()) == 0:
        print("📭 전략3 포지션 전부 청산 완료 → 전략1 진입 허용")
        config["ready_for_strategy1"] = True

    balance_util.save_holdings_to_file()

    print("📂 최종 holdings 상태:", json.dumps(balance_util.get_holdings(), indent=2, ensure_ascii=False))

    return released

if __name__ == "__main__":
    print("🧪 전략3 청산 테스트 실행 중...")
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ config.json 로드 실패: {e}")
        config = {"operating_capital": 100000, "ready_for_strategy1": False}

    result = handle_strategy3_exit(config)
    print(f"📤 청산된 종목: {result}")
