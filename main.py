import json
import time
import os
from datetime import datetime
from strategies.strategy1 import run_strategy1
from strategies.strategy2 import run_strategy2
from strategies.strategy3 import run_strategy3
from utils.balance import (
    load_holdings_from_file,
    update_balance_from_upbit,
    get_holding_symbols
)
from utils.telegram import notify_buy, notify_bot_start, notify_bot_stop
from utils.candle import get_candles
from scanners.scanner2 import detect_strategy2_signals
from scanners.scanner3 import detect_fast_rising_symbols
from sell_strategies.sell_strategy1 import sell_strategy1
from sell_strategies.sell_strategy2 import sell_strategy2
from utils.error_handler import handle_error


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
def run():
    notify_bot_start(config)

    fast_mode = False
    fast_mode_trigger_time = None

    while True:
        now = datetime.now()
        print(f"\n[{now}] 24H 자동 매매봇 감지 중...")

        try:
            # ✅ 보유 종목 확인
            holding_symbols = get_holding_symbols()
            if holding_symbols:
                print(f"⚠️ 현재 보유 중: {holding_symbols} → 신규 진입 차단")
            else:
                # ✅ 전략 1 → 2 → 3 순으로 실행
                for strategy_func, strategy_num in [
                    (run_strategy1, "1"),
                    (run_strategy2, "2"),
                    (run_strategy3, "3")
                ]:
                    try:
                        result = strategy_func(config)
                        if result:
                            # 전략 2, 3은 리스트 반환 고려
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
                                print(f"✅ 전략 {strategy_num} 매수 완료 및 알림 발송: {result['종목']}")
                                break  # 매수 시 다른 전략 실행 중단

                            # ✅ 전환 알림 처리
                            elif result.get("type") == "transition":
                                notify_transition(
                                    symbol=result["symbol"],
                                    from_strategy=result["from_strategy"],
                                    to_strategy=result["to_strategy"],
                                    success=result["success"],
                                    config=config
                                )
                                status = "성공" if result["success"] else "실패"
                                print(f"🔄 전략 전환 {status} 알림 발송 완료")

                            # ✅ 갈아타기 알림 처리
                            elif result.get("type") == "switch":
                                notify_switch(
                                    old_symbol=result["old_symbol"],
                                    new_symbol=result.get("new_symbol"),
                                    success=result["success"],
                                    exit_type=result.get("exit_type", "익절"),
                                    config=config
                                )
                                status = "완료" if result["success"] else "실패"
                                print(f"🔁 갈아타기 {status} 알림 발송 완료")
                    except Exception as e:
                        handle_error(e, location=f"main.py - run_strategy{strategy_num}", config=config)


            # ✅ 매도 전략 1 실행
            try:
                print("📤 전략 1 매도 감지 실행")
                sell_strategy1(config)

            except Exception as e:
                handle_error(e, location="main.py - sell_strategy1", config=config)

            # ✅ 매도 전략 2 실행
            try:
                print("📤 전략 2 매도 감지 실행")
                candles_dict = {}
                for symbol in get_holding_symbols():
                    candles = get_candles(symbol, interval="1", count=50)
                    if candles:
                        candles_dict[symbol] = candles

                sell_results = sell_strategy2(candles_dict)
                for res in sell_results:
                    print(f"💸 전략2 매도 완료: {res['symbol']} / 가격: {res['price']} / 유형: {res['type']}")
            except Exception as e:
                handle_error(e, location="main.py - sell_strategy2", config=config)

            # ✅ 전략 2 급등 종목 감지
            try:
                config["watchlist"] = detect_strategy2_signals()
                if config["watchlist"]:
                    print(f"⚡ 전략2 급등 종목 감지: {config['watchlist']}")
            except Exception as e:
                handle_error(e, location="main.py - detect_strategy2_signals", config=config)

            # ✅ 전략 3 급등 신호 감지 및 fast mode 전환
            try:
                strategy3_signals = detect_fast_rising_symbols()
                if strategy3_signals:
                    print(f"⚡ 전략3 급등 신호 감지: {strategy3_signals}")
                    config["strategy3_signals"] = strategy3_signals
                    fast_mode = True
                    fast_mode_trigger_time = datetime.now()
            except Exception as e:
                handle_error(e, location="main.py - detect_fast_rising_symbols", config=config)

            # ✅ fast mode 유지 시간 관리
            if fast_mode:
                elapsed = (datetime.now() - fast_mode_trigger_time).seconds
                if elapsed >= config.get("fast_mode_duration", 900):
                    print("⏱ fast mode 해제 → 일반 모드로 복귀")
                    fast_mode = False

            # ✅ 스캔 주기 설정
            scan_interval = config["fast_scan_interval"] if fast_mode else config["scan_interval"]
            print(f"⏳ 다음 스캔까지 대기: {scan_interval}초\n")
            time.sleep(scan_interval)

        except KeyboardInterrupt:
            notify_bot_stop(config, reason="사용자 수동 종료")
            print("🛑 수동 종료됨")
            break
        except Exception as e:
            handle_error(e, location="main.py - main loop", config=config)
            notify_bot_stop(config, reason=f"예외 종료: {str(e)}")
            time.sleep(10)

# ✅ 실행
if __name__ == "__main__":
    run()
