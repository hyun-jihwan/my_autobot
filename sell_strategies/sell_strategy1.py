# 전략 1 매도 조건 완성 버전 (단타 / 스윙 분기 포함)
import sys
import os
import json
import time
import traceback
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from sell_strategies.sell_utils import (
    get_indicators, check_sell_signal_strategy1,
    check_sell_signal_strategy_swing
)
from utils.balance import (
    load_holdings_from_file, save_holdings_to_file,
    remove_holding,update_balance_after_sell
)
from utils.candle import get_candles
from utils.trade import sell_market_order
from utils.log_utils import log_sell



def get_latest_price(symbol):
    """1분봉을 사용한 체결가 보정"""
    candles = get_candles(symbol, interval="1", count=1)
    if candles and len(candles) > 0:
        return candles[0]["trade_price"]
    return None



def sell_strategy1(config):
    print("📤 매도 전략1 실행됨")

    balance = load_holdings_from_file()
    holdings = balance.get("holdings", {})

    if not holdings:
        print("⚠️ 현재 보유 중인 종목이 없습니다.")
        return

    for symbol, data in holdings.copy().items():
        print(f"📤 매도 체크: {symbol}")

        entry_price = data["entry_price"]
        quantity = data["quantity"]
        mode = data.get("extra", {}).get("mode", "단타")  # 기본 단타

        # ✅ 캔들 간격 선택: 단타 → 15분 / 스윙 → 60분
        interval = "15" if mode == "단타" else "60"
        candles = get_candles(symbol, interval=interval, count=30)

        if not candles or len(candles) < 10:
            print(f"⚠️ 캔들 부족: {symbol}")
            continue

        # ✅ 목표가 정보
        expected_profit = data.get("expected_profit", 0.05)
        target_1 = round(entry_price * (1 + expected_profit), 2)
        target_2 = data.get("target_2")
        target_3 = data.get("target_3")

        print(f"🎯 목표가1: {target_1}, 목표가2: {target_2}, 목표가3: {target_3}")

        # ✅ 매도 조건 평가
        indicators = get_indicators(symbol, candles)
        signal = None

        # ✅ 매도 조건 평가
        if mode == "스윙":
            signal = check_sell_signal_strategy_swing(data, candles, indicators)
        else:
            signal = check_sell_signal_strategy1(data, candles, indicators)

        if signal:
            print(f"✅ 스윙 매도 조건 충족: {symbol} / 이유:{signal}")

            # ✅ 체결가 조회 및 시장가 매도
            try:
                price = get_latest_price(symbol)
                if not price:
                    raise ValueError("체결가 조회 실패")


                # 💰 매도 시도 (최대 2회 재시도)
                for attempt in range(2):
                    try:
                        sell_market_order(symbol)
                        update_balance_after_sell(symbol, price, quantity)
                        remove_holding(symbol)
                        log_sell(symbol, price, f"전략1 매도 ({mode}) - 이유: {signal}")
                        print(f"💸 매도 완료: {symbol} @ {price}")
                        break
                    except Exception as e:
                        print(f"⚠️ 매도 실패 [{attempt+1}/2]: {e}")
                        time.sleep(2)
                else:
                    print(f"❌ 매도 완전 실패: {symbol} → 로그만 남기고 보유 유지")

            except Exception as e:
                print(f"❌ 매도 처리 중 오류 발생: {symbol} / {e}")

        else:
            print(f"⏳ 매도 조건 미충족: {symbol} ({mode})")


    save_holdings_to_file()
    print("📤 매도 전략 1 완료 — holdings.json 저장됨")



if __name__ == "__main__":
    print("🧪 [전략1 매도 조건 평가 테스트용 실행] 시작")

    from utils.balance import get_holdings

    try:
        holdings = get_holdings()
        has_strategy1 = any(h.get("source") == "strategy1" for h in holdings.values())

        if has_strategy1:
            print("✅ strategy1 포지션 확인됨 → 매도 조건 평가 시작")
            config = {
                "operating_capital": 100000,
                "ready_for_strategy1": True
            }
            sell_strategy1(config)
        else:
            print("⏸ strategy1 포지션이 없어 테스트 생략됨")

    except Exception as e:
        import traceback
        print("❌ 전략1 테스트용 실행 중 예외 발생:")
        traceback.print_exc()
