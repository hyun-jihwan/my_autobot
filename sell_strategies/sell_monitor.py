# sell_monitor.py : 전략1(5분) + 전략2/3(1분) 통합 감지 루프

import time
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 전략 로직 불러오기
from sell_strategies.sell_strategy1 import sell_strategy1
from sell_strategies.sell_strategy2 import sell_strategy2
from sell_strategies.sell_strategy3 import evaluate_exit_strategy3

# 공통 유틸
from utils.balance import (
    get_holding_symbols,
    get_holding_data,
    load_holdings_from_file,
)
from utils.candle import get_candles


# ✅ 전략2,3용 캔들 수집 함수
def get_candles_dict(symbols):
    candles_dict = {}
    for symbol in symbols:
        candles = get_candles(symbol, interval="1", count=30)
        if candles:
            candles_dict[symbol] = candles
    return candles_dict


# ✅ 통합 매도 감지 루프
def run_sell_monitor():
    print("📡 [통합 매도 감지 루프 시작됨]")

    last_run_strategy1 = None  # 전략 1: 5분마다 실행
    last_run_strategy2_3 = None  # 전략 2, 3: 1분마다 실행

    config = {"operating_capital": 100000}

    while True:
        now = datetime.now()

        # ✅ 전략 1: 5분 간격 실행
        if last_run_strategy1 is None or (now - last_run_strategy1).seconds >= 300:
            print(f"\n🚀 [전략1] 매도 감지 시작: {now.strftime('%H:%M:%S')}")
            try:
                sell_strategy1(config)
            except Exception as e:
                print(f"❌ 전략1 오류: {e}")
            last_run_strategy1 = now

        # ✅ 전략 2, 3: 1분 간격 실행
        if last_run_strategy2_3 is None or (now - last_run_strategy2_3).seconds >= 60:
            print(f"\n🔄 [전략2/3] 매도 감지 시작: {now.strftime('%H:%M:%S')}")

            try:
                symbols = get_holding_symbols()
                candles_dict = get_candles_dict(symbols)

                # ✅ 전략 2 실행
                try:
                    balance = load_holdings_from_file()
                    sell_strategy2(candles_dict, balance)
                except Exception as e:
                    print(f"❌ 전략2 오류: {e}")

                # ✅ 전략 3 실행
                for symbol in symbols:
                    holding = get_holding_data(symbol)
                    if not holding or holding.get("source") != "strategy3":
                        continue

                    try:
                        evaluate_exit_strategy3(holding, candles_dict)
                    except Exception as e:
                        print(f"❌ 전략3 오류 - {symbol}: {e}")

            except Exception as e:
                print(f"❌ 전략2/3 루프 오류: {e}")

            last_run_strategy2_3 = now

        time.sleep(1)


if __name__ == "__main__":
    run_sell_monitor()
