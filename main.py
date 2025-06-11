import json
import time
from strategies.strategy1 import run_strategy1
from strategies.strategy2 import run_strategy2
from strategies.strategy3 import run_strategy3
from utils.balance import load_holdings_from_file
from utils.telegram import send_telegram
from utils.sheet import record_to_sheet
from datetime import datetime, timedelta
from utils.candle import get_all_krw_symbols, get_candles
from scanners.scanner2 import detect_strategy2_signals
from transition.strategy3_exit import handle_strategy3_exit
from scanners.scanner3 import detect_fast_rising_symbols
from utils.balance import balance


# 봇 실행 전 → 보유 종목 자동 복구
load_holdings_from_file()

# 설정 불러오기
with open("config.json") as f:
    config = json.load(f)

balance["holdings"].clear()
print("✅ 보유 종목 초기화 완료")


# 전략 매핑
strategy_map = {
    "strategy1": run_strategy1,
    "strategy2": run_strategy2,
    "strategy3": run_strategy3
}

# 메인 루프
def run():
    fast_mode = False
    fast_mode_trigger_time = None

    while True:
        now = datetime.now()
        print(f"\n[{now}] 감지 실행 중...")

        # 전략2 급등 감지
        config["watchlist"] = detect_strategy2_signals()
        if config["watchlist"]:
            print(f"⚡ 전략2 급등 종목: {config['watchlist']}")

        # ✅ 전략 실행 순서대로 실행 (strategy1 → strategy3 순서 보장)
        for strategy_name in config["strategies"]:
            print(f"🚀 전략 실행 중: {strategy_name}")
            strategy_func = strategy_map.get(strategy_name)
            if strategy_func:
                try:
                    result = strategy_func(config)
                    if result:
                        print(f"✅ {strategy_name} 실행 결과: {result}")
                except Exception as e:
                    print(f"❌ {strategy_name} 실행 중 오류: {e}")

        # 전략3 급등 감지 (fast mode 트리거용)
        strategy3_signals = detect_fast_rising_symbols()
        if strategy3_signals:
            print(f"⚡ 전략3 급등 감지됨: {strategy3_signals}")
            config["strategy3_signals"] = strategy3_signals
            fast_mode = True
            fast_mode_trigger_time = datetime.now()

        # 📡 급등 모드 유지 시간 제어
        if fast_mode:
            elapsed = (datetime.now() - fast_mode_trigger_time).seconds
            if elapsed >= config.get("fast_mode_duration", 900):
                print("⏱ 급등 모드 해제 → 기본 간격 복귀")
                fast_mode = False

        # ⏳ 스캔 간격 설정
        scan_interval = config["fast_scan_interval"] if fast_mode else config["scan_interval"]
        print(f"⏳ 다음 스캔까지 대기: {scan_interval}초\n")
        time.sleep(scan_interval)


if __name__ == "__main__":
    run()
