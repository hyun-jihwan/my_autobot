# 전략 1 매도 조건 완성 버전 (단타 / 스윙 분기 포함)
import sys
import os
import json
import schedule
import time
import traceback
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from sell_strategies.sell_utils import get_indicators, check_sell_signal_strategy1, check_sell_signal_strategy_swing
from utils.balance import load_holdings_from_file, save_holdings_to_file, remove_holding,update_balance_after_sell
from utils.candle import get_candles
from utils.trade import sell_market_order




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
        print(f"🎯 1차 목표가: {target_1}")
        target_2 = data.get("target_2")
        target_3 = data.get("target_3")
        print(f"🎯 목표가2: {target_2}, 목표가3: {target_3}")


        # ✅ 매도 조건 평가
        indicators = get_indicators(symbol, candles)

        # ✅ 매도 조건 평가
        if mode == "스윙":
            result = check_sell_signal_strategy_swing(data, candles, indicators)

            if result:
                print(f"✅ 스윙 매도 조건 충족: {symbol} / 이유: {result}")

                # 💰 매도 처리
                price = get_latest_price(symbol)
                if price:
                    sell_market_order(symbol)
                    update_balance_after_sell(symbol, price, quantity)
                    remove_holding(symbol)

                else:
                    print(f"❌ 체결가 조회 실패 → {symbol}")

            else:
                print(f"⏳ 스윙 매도 조건 미충족: {symbol}")


        else:  # 단타
            signal = check_sell_signal_strategy1(data, candles, indicators)

            if signal:
                print(f"✅ 단타 매도 조건 충족: {symbol} / 이유: {signal}")

                # 💰 매도 처리
                price = get_latest_price(symbol)
                if price:
                    sell_market_order(symbol)
                    update_balance_after_sell(symbol, price, quantity)
                    remove_holding(symbol)
                else:
                    print(f"❌ 체결가 조회 실패 → {symbol}")

            else:
                print(f"⏳ 단타 매도 조건 미충족: {symbol}")


    save_holdings_to_file()
    print("📤 매도 전략 1 완료 — holdings.json 저장됨")


# ✅ 5분마다 실행 스케줄러 설정
def run_scheduler(config):
    schedule.every(5).minutes.do(lambda: sell_strategy1(config))
    print("🕒 [전략1 매도] 5분마다 자동 실행 스케줄러 시작됨")

    try:
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"❌ 스케줄 실행 중 오류 발생: {e}")
                traceback.print_exc()

            time.sleep(1)

    except KeyboardInterrupt:
        print("🛑 사용자 종료 요청으로 스케줄러 종료됨")

if __name__ == "__main__":
    print("🧪 [전략1 매도 조건 평가 트리거] 시작")
    config = {
        "operating_capital": 100000,
        "ready_for_strategy1": False
    }
    sell_strategy1(config)
