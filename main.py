import json
import time
import os
from datetime import datetime
from multiprocessing import Process, Manager

from strategies.strategy1 import run_strategy1
from strategies.strategy2 import run_strategy2
from strategies.strategy3 import run_strategy3

from utils.balance import (
    load_holdings_from_file,
    update_balance_from_upbit,
    get_holding_symbols
    get_krw_balance
)
from utils.telegram import (
    notify_buy, notify_bot_start,
    notify_bot_stop, notify_transition,
    notify_switch
)
from utils.candle import get_candles
from scanners.scanner2 import detect_strategy2_signals
from scanners.scanner3 import detect_fast_rising_symbols
from utils.error_handler import handle_error
from utils.google_sheet_logger import log_trade_to_sheet


# ✅ API Key 불러오기
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

# ✅ 설정 불러오기
with open("config.json") as f:
    config = json.load(f)

# ✅ 보유 종목 복구
load_holdings_from_file()

# ✅ 업비트 잔고 동기화
update_balance_from_upbit(access_key, secret_key)

# ✅ 메인 루프
def strategy_worker(strategy_func, strategy_num, config, shared_data):
    fast_mode = False
    fast_mode_trigger_time = None

    while True:
        try:
            holding_symbols = get_holding_symbols()
            if holding_symbols:
                print(f"[전략 {strategy_num}] 보유 중: {holding_symbols} → 신규 진입 대기")
            else:
                result = strategy_func(config)
                if result:
                    if isinstance(result, list):
                        result = result[0]
                    if result.get("status") == "buy":
                        notify_buy(
                            symbol=result["종목"],
                            total_amount=int(result["진입금액"]),
                            balance=int(result["잔고"]),
                            strategy_num=strategy_num,
                            swing_or_scalp=result["전개방식"],
                            expected_profit_pct=round(result["예상수익률"], 2),
                            target_profit_pct=round(result["목표수익률"], 2),
                            config=config
                        )
                        log_trade_to_sheet({
                            "날짜": datetime.now().strftime("%Y-%m-%d"),
                            "시간": datetime.now().strftime("%H:%M:%S"),
                            "종목": result["종목"],
                            "구분": "매수",
                            "전략": result["전략"],
                            "매수금액": int(result["진입금액"]),
                            "매도금액": 0,
                            "수익률(%)": 0,
                            "수익금액": 0,
                            "누적수익": 0,
                            "실시간잔고": int(result["잔고"])
                        })
                        print(f"✅ [전략 {strategy_num}] 매수 완료 및 알림: {result['종목']}")

                    elif result.get("type") == "transition":
                        notify_transition(
                            symbol=result["symbol"],
                            from_strategy=result["from_strategy"],
                            to_strategy=result["to_strategy"],
                            success=result["success"],
                            config=config
                        )
                        status = "성공" if result["success"] else "실패"
                        print(f"🔄 전략 전환 {status}: {result['symbol']}")
                        log_trade_to_sheet({
                            "날짜": datetime.now().strftime("%Y-%m-%d"),
                            "시간": datetime.now().strftime("%H:%M:%S"),
                            "종목": result["symbol"],
                            "구분": "전환",
                            "전략": result["to_strategy"],
                            "매수금액": 0,
                            "매도금액": 0,
                            "수익률(%)": 0,
                            "수익금액": 0,
                            "누적수익": 0,
                            "실시간잔고": int(get_krw_balance())
                        })

                    elif result.get("type") == "switch":
                        notify_switch(
                            old_symbol=result["old_symbol"],
                            new_symbol=result.get("new_symbol"),
                            success=result["success"],
                            exit_type=result.get("exit_type", "익절"),
                            config=config
                        )
                        status = "완료" if result["success"] else "실패"
                        print(f"🔁 갈아타기 {status}: {result['old_symbol']} -> {result.get('new_symbol')}")
                        log_trade_to_sheet({
                            "날짜": datetime.now().strftime("%Y-%m-%d"),
                            "시간": datetime.now().strftime("%H:%M:%S"),
                            "종목": result["old_symbol"],
                            "구분": "갈아타기",
                            "전략": result.get("strategy", "Unknown"),
                            "매수금액": 0,
                            "매도금액": 0,
                            "수익률(%)": 0,
                            "수익금액": 0,
                            "누적수익": 0,
                            "실시간잔고": int(get_krw_balance())
                        })

            # Fast Mode 및 급등 종목 관리 (공유된 shared_data를 사용)
            now = datetime.now()
            if strategy_num == "1":
                try:
                    shared_data["watchlist"] = detect_strategy2_signals()
                    if shared_data["watchlist"]:
                        print(f"⚡ 전략2 급등 종목 감지: {shared_data['watchlist']}")
                except Exception as e:
                    handle_error(e, location="main.py - detect_strategy2_signals", config=config)

                try:
                    signals = detect_fast_rising_symbols()
                    if signals:
                        print(f"⚡ 전략3 급등 신호 감지: {signals}")
                        shared_data["strategy3_signals"] = signals
                        fast_mode = True
                        fast_mode_trigger_time = datetime.now()
                except Exception as e:
                    handle_error(e, location="main.py - detect_fast_rising_symbols", config=config)

                if fast_mode:
                    elapsed = (datetime.now() - fast_mode_trigger_time).seconds
                    if elapsed >= config.get("fast_mode_duration", 900):
                        print("⏱ fast mode 해제 → 일반 모드 복귀")
                        fast_mode = False

            scan_interval = config["fast_scan_interval"] if fast_mode else config["scan_interval"]
            time.sleep(scan_interval)

        except KeyboardInterrupt:
            notify_bot_stop(config, reason="사용자 수동 종료")
            print(f"[전략 {strategy_num}] 수동 종료")
            break
        except Exception as e:
            handle_error(e, location=f"main.py - strategy_worker({strategy_num})", config=config)
            time.sleep(10)

def run():
    notify_bot_start(config)
    print("✅ 병렬 처리 매수봇 시작")

    with Manager() as manager:
        shared_data = manager.dict()
        processes = [
            Process(target=strategy_worker, args=(run_strategy1, "1", config, shared_data)),
            Process(target=strategy_worker, args=(run_strategy2, "2", config, shared_data)),
            Process(target=strategy_worker, args=(run_strategy3, "3", config, shared_data))
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join()

if __name__ == "__main__":
    run()
