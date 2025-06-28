import sys
import os
import math
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import json

from sell_strategies.sell_utils import get_indicators, check_sell_signal_strategy1, check_sell_signal_strategy_swing
from sell_strategies.sell_strategy1 import sell_strategy1
from transition.strategy3_exit import transition_strategy3_to_1
from utils.trade import calculate_targets, sell_market_order
from utils.filter import get_top_rising_symbols
from utils.risk import judge_trade_type
from utils.risk import calculate_swing_target_with_fibonacci, calculate_scalping_target
from utils.balance import get_holdings, update_balance_after_sell
from utils.balance import get_holding_symbols, get_holding_count, get_holding_info, remove_holding, get_max_buyable_amount
from utils.balance import get_krw_balance, update_balance_after_buy, record_holding, save_holdings_to_file
from utils.position import assign_position_size
from utils.signal import classify_trade_mode
from utils.candle import get_all_krw_symbols, get_candles, is_box_breakout, is_breakout_pullback, is_v_rebound
from utils.score import calculate_score_full
from utils.risk import calculate_expected_risk
from utils.indicators import calculate_indicators
from utils.transition_helper import evaluate_exit
from datetime import datetime
from utils.fibonacci_target import calculate_fibonacci_targets
from utils.error_handler import handle_error
from utils.telegram import notify_buy, notify_transition


def run_strategy1_from_strategy3(config):
    try:
        # ✅ 전략 3 포지션 → 전략 1로 전환 평가
        released = transition_strategy3_to_1(config)

        # ✅ 아직 전환 중이면 전략 1은 대기
        if not config.get("ready_for_strategy1", False):
            print("⏸ 전략3 평가 중 → 전략1 대기")
            return

        # ✅ 전략3 포지션이 여전히 남아있으면 신규 진입 제한
        holdings = get_holdings()
        for h in holdings:
            if h.get("source") == "strategy3":
                print(f"⛔ 전략3 포지션 유지 중 → 전략1 신규 진입 차단: {h['symbol']}")
                return

        # ✅ 전략 1 진입 실행
        result = run_strategy1(config)
        print("✅ 전략1 진입 결과:", result)

    except Exception as e:
        handle_error(e, location="strategy1.py - run_strategy1_from_strategy3", config=config)

def handle_strategy2_positions(config):
    try:
        config["strategy_switch_mode"] = True  # 🔧 전환 플래그 설정
        from utils.balance import load_holdings_from_file

        load_holdings_from_file()

        now = datetime.now()
        if now.strftime("%H:%M") < "09:15":
            return  # 아직 전략 2 시간 → 아무 것도 안 함

        print("🔁 전략 2 → 전략 1 전환 처리 시작")


        with open("data/holdings.json", "r") as f:
            raw = json.load(f)
            print("📦 현재 보유 종목(raw):", json.dumps(raw, indent=2))

        holdings_dict = get_holding_info()
        print("🔍 get_holding_info() 결과:", json.dumps(holdings_dict, indent=2, ensure_ascii=False))

        holdings = list(holdings_dict.values())
        blocked_symbols = []

        for holding in holdings:
            try:
                print(f"🔎 평가 시작 → 현재 holding:", holding) 
                print("🧪 source:", holding.get("source"))

                if holding.get("source") != "strategy2":
                print("❌ 소스가 strategy2 아님 → 제외됨")
                    continue

                symbol = holding["symbol"]
                entry_price = holding["entry_price"]
                quantity = holding["quantity"]

                candles = get_candles(symbol, interval="15", count=30)
                if not candles or len(candles) < 12:
                    print(f"⚠️ 캔들 부족 → {symbol} 스킵")
                    continue

                hourly_candles = get_candles(symbol, interval="60", count=10)
                is_swing = judge_trade_type(hourly_candles)
                current_price = candles[-1]["trade_price"]

                # ✅ 전략2 유지 조건 평가
                result = evaluate_exit(symbol, quantity, source="strategy2")
                if not result:
                    print(f"⛔ 전략2 → 전략1 전환 조건 미충족 → 강제 청산: {symbol}")
                    sell_market_order(symbol)
                    update_balance_after_sell(symbol, current_price, quantity)
                    remove_holding(symbol)
                    blocked_symbols.append(symbol)

                    notify_transition(
                        symbol=symbol,
                        from_strategy="2",
                        to_strategy="1",
                        success=False,
                        exit_type="손절" if current_price < entry_price else "익절",
                        config=config
                    )
                    continue

                interval = "60" if is_swing else "15"
                candles_for_fib = get_candles(symbol, interval=interval, count=50)
                expected_profit, target_2, target_3 = calculate_fibonacci_targets(candles_for_fib, "스윙" if is_swing else "단타")

                if expected_profit is None:
                    print(f"❌ {symbol} → 피보나치 목표가 계산 실패 → 강제 청산")
                    sell_market_order(symbol)
                    update_balance_after_sell(symbol, current_price, quantity)
                    remove_holding(symbol)
                    blocked_symbols.append(symbol)

                    notify_transition(
                        symbol=symbol,
                        from_strategy="2",
                        to_strategy="1",
                        success=False,
                        exit_type="손절" if current_price < entry_price else "익절",
                        config=config
                    )
                    continue

                holding["score"] = "strategy1"
                holding["expected_profit"] = expected_profit
                holding["target_2"] = target_2
                holding["target_3"] = target_3
                holding["source"] = "strategy1"
                holding.setdefault("extra", {})["mode"] = "스윙" if is_swing else "단타"
                holding["extra"]["entry_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                save_holdings_to_file()

                notify_transition(
                    symbol=symbol,
                    from_strategy="2",
                    to_strategy="1",
                    success=True,
                    config=config
                )
                print(f"💾 전략 전환 완료: {symbol} → strategy1")

            except Exception as e:
                handle_error(e, location=f"strategy1.py - handle_strategy2_positions ({holding.get('symbol', 'N/A')})", config=config)

        return blocked_symbols

    except Exception as e:
        handle_error(e, location="strategy1.py - handle_strategy2_positions", config=config)



def run_strategy1(config):
    try:
        # ✅ 감시 리스트 15분마다 갱신
        now = datetime.now()
        if "last_update" not in config:
            config["last_update"] = now.strftime("%Y-%m-%d %H:%M")

        last_update = datetime.strptime(config["last_update"], "%Y-%m-%d %H:%M")
        if (now - last_update).seconds >= 900:
            config["watchlist"] = get_top_rising_symbols(limit=35)
            config["last_update"] = now.strftime("%Y-%m-%d %H:%M")
            print(f"🔄 감시 리스트 갱신 완료: {len(config['watchlist'])}개")

        watchlist = config.get("watchlist", [])

        selected = []

        for symbol in get_all_krw_symbols():
            # ✅ 현재 보유 종목이 2개 이상이면 진입 중단
            if get_holding_count() >= 2:
                print("❌ 현재 보유 종목 2개 초과 → 신규 진입 금지")
                return None

            if symbol in get_holding_symbols():
                continue  # 이미 보유 중인 종목 스킵

            candles = get_candles(symbol, interval="15", count=30)
            if not candles or len(candles) < 5:
                continue

            # 급등 감지 예외 진입 허용
            in_list = symbol in watchlist
            if not in_list:
                price_now = candles[0]["trade_price"]
                price_prev = candles[1]["trade_price"]
                price_change = (price_now - price_prev) / price_prev * 100
                volume_now = candles[0]["candle_acc_trade_volume"]
                volume_avg = sum(c["candle_acc_trade_volume"] for c in candles[1:4]) / 3

                if not (price_change >= 1.2 and volume_now >= volume_avg * 1.5):
                    continue  # 급등 조건 불충족 시 스킵

            # 모드 판별
            is_swing = judge_trade_type(candles)
            mode = "스윙" if is_swing else "단타"
            interval = "60" if mode == "스윙" else "15"
            candles_for_fib = get_candles(symbol, interval=interval, count=50)

            # 피보나치 목표가 및 예상 수익률 계산
            expected_profit_percent, target_2, target_3 = calculate_fibonacci_targets(candles_for_fib, mode)
            if expected_profit_percent is None:
                continue

            entry_price = candles[0]["trade_price"]
            target_1 = round(entry_price * (1 + expected_profit_percent / 100), 2)

            # 패턴 필터
            if not (is_box_breakout(candles) or is_breakout_pullback(candles) or is_v_rebound(candles)):
                continue

            # 보조지표 필터
            indicators = calculate_indicators(candles)
            satisfied = sum(1 for v in indicators.values() if v)
            if satisfied < 4:
                continue

            # 스코어 계산
            score = calculate_score_full(
                candles=candles,
                pattern_matched=True,
                indicator_result=indicators,
                expected_profit=expected_profit_percent,
                expected_loss=2.0  # 손실 예상 비율 (%), 필요시 조정 가능
            )
            if score < 70:
                continue

            # 자금 및 수량 계산
            capital = config.get("operating_capital", 1000000)
            position = assign_position_size(score, total_capital=capital)
            if position == 0:
                continue

            current_price = candles[-1]["trade_price"]
            quantity = math.floor((position / current_price) * 10000) / 10000
            total_cost = quantity * current_price * 1.0005  # 수수료 포함

            if get_krw_balance() < total_cost:
                print(f"❌ 잔고 부족: {symbol} 필요={total_cost:.2f}, 보유={get_krw_balance():.2f}")
                continue

            # 잔고 차감
            update_balance_after_buy(total_cost)

            # 보유 기록
            record_holding(
                symbol=symbol,
                entry_price=current_price,
                quantity=quantity,
                score=score,
                expected_profit=expected_profit_percent,
                target_2=target_2,
                target_3=target_3,
                extra={
                    "max_price": current_price,
                    "prev_cci": indicators.get("cci"),
                    "mode": mode,
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "target_1": target_1
                },
                source="strategy1"
            )


            # ✅ 거래 후 실시간 업비트 잔고 동기화
            update_balance_from_upbit()

            result = {
                "종목": symbol,
                "전략": "strategy1",
                "진입가": current_price,
                "예상수익률": expected_profit_percent,
                "스코어": score,
                "진입비중": round(position / capital * 100, 2),
                "진입금액": position,
                "전개방식": mode,
                "목표수익률": expected_profit_percent,
                "목표가1": target_1,
                "목표가2": target_2,
                "목표가3": target_3,
                "최고가": current_price,
                "잔고": int(get_krw_balance()),
                "status": "buy",
                "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            selected.append(result)
            print(f"✅ 전략1 진입 완료 → {result}")

            # 한 번 진입 후 루프 종료
            break

        if selected:
            return selected[0]
        return None

    except Exception as e:
        handle_error(e, location="strategy1.py - run_strategy1", config=config)
        return None
