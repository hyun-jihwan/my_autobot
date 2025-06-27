import sys
import os
import math
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")


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


def strategy1(config):
    print("📥 전략1 실행 시작")

    symbol = "KRW-B"  # 테스트용

    # ✅ 전략 전환 모드 감지 시 → 보유 종목만 업데이트 후 종료
    if config.get("strategy_switch_mode", False):
        print(f"🔁 전환 모드 감지됨 → strategy1 전략만 덮어쓰기 진행 중")

        holding = get_holding_info().get(symbol)
        if holding:
            holding["score"] = "strategy1"
            holding["expected_profit"] = 0.05
            holding["target_2"] = 110
            holding["target_3"] = 120
            holding["source"] = "strategy1"

            if "extra" not in holding:
                holding["extra"] = {}

            holding["extra"]["mode"] = "단타"
            holding["extra"]["entry_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            save_holdings_to_file()

            print(f"✅ 전략1로 전략 전환 완료 → {symbol}")
            return {
                "종목": symbol,
                "전략": "strategy1",
                "전환모드": True,
                "진입가": holding["entry_price"],
                "진입시간": holding["extra"]["entry_time"]
            }

        else:
            print("⚠️ 전략 전환 모드이나 기존 보유 정보 없음 → 신규 진입으로 전환")
            return None

    candles = get_candles(symbol, interval="15", count=30)
    if not candles or len(candles) < 1:
        print(f"❌ 캔들 데이터 부족: {symbol}")
        return None

    current_price = candles[-1]["trade_price"]
    entry_price = current_price
    fee_rate = 0.0005
    capital = config["operating_capital"]

    # 수수료까지 고려한 최대 구매 가능 금액
    max_spend = capital / (1 + fee_rate)
    quantity = math.floor((max_spend / entry_price) * 10000) / 10000
    used_krw = round(quantity * entry_price * (1 + fee_rate), 2)

    # ✅ 실제 잔고가 충분할 경우에만 진입
    if used_krw > capital:
        print(f"❌ 진입 실패: 총 사용액({used_krw:.2f}) > 운영자금({capital:.2f})")
        return None

    # ✅ 잔고 차감 먼저 → 실패 시 record_holding 실행 안됨
    try:
        update_balance_after_buy(used_krw)
    except Exception as e:
        print(f"❌ 매수 실패: {e}")
        return None

    # 보유 등록
    record_holding(
        symbol=symbol,
        entry_price=entry_price,
        quantity=quantity,
        expected_profit=0.05,
        target_2=110,
        target_3=120,
        source="strategy1",
        score="strategy1",
        extra={
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_price": entry_price,
        }
    )


    print(f"✅ 전략1 진입 성공: {symbol} / 진입가: {current_price} / 수량: {quantity}")
    return {
        "종목": symbol,
        "전략": "strategy1",
        "진입가": entry_price,
        "진입금액": used_krw,
        "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }



def run_strategy1_from_strategy3(config):
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
    result = strategy1(config)
    print("✅ 전략1 진입 결과:", result)


def handle_strategy2_positions(config):
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
        print(f"🔎 평가 시작 → 현재 holding:", holding) 
        print("🧪 source:", holding.get("source"))

        if holding.get("source") != "strategy2":
            print("❌ 소스가 strategy2 아님 → 제외됨")
            continue

        symbol = holding["symbol"]
        entry_price = holding["entry_price"]
        quantity = holding["quantity"]
        entry_time = holding.get("entry_time", "")

        print(f"📌 전략 2 잔여 종목 확인: {symbol} (진입 시간: {entry_time})")

        candles = get_candles(symbol, interval="15", count=30)
        if not candles or len(candles) < 12:
            print(f"⚠️ 캔들 부족 → {symbol} 스킵")
            continue

        hourly_candles = get_candles(symbol, interval="60", count=10)
        is_swing = judge_trade_type(hourly_candles)
        current_price = candles[-1]["trade_price"]

        # ✅ 전략2 유지 조건 평가
        result = evaluate_exit(symbol, quantity, source="strategy2")
        print(f"📊 evaluate_exit 결과 → {symbol}: {result}")

        if not result:
            print(f"⛔ 전략2 → 전략1 전환 조건 미충족 → 강제 청산: {symbol}")
            sell_market_order(symbol)
            update_balance_after_sell(symbol, current_price, quantity)
            remove_holding(symbol)
            blocked_symbols.append(symbol)
            continue

        # ✅ 조건 충족 시 전략1 전환 처리
        print("🔁 전략2 → 전략1 전환 조건 충족 → holdings 정보만 업데이트")

        # 👉 피보나치 목표가 계산
        interval = "60" if is_swing else "15"
        candles_for_fib = get_candles(symbol, interval=interval, count=50)
        expected_profit, target_2, target_3 = calculate_fibonacci_targets(candles_for_fib, "스윙" if is_swing else "단타")

        # 예외: 계산 실패 시 유지 중단
        if expected_profit is None:
            print(f"❌ {symbol} → 피보나치 목표가 계산 실패 → 강제 청산")
            sell_market_order(symbol)
            update_balance_after_sell(symbol, current_price, quantity)
            remove_holding(symbol)
            blocked_symbols.append(symbol)
            continue

        # 👉 holding 정보 업데이트
        holding["score"] = "strategy1"
        holding["expected_profit"] = expected_profit
        holding["target_2"] = target_2
        holding["target_3"] = target_3
        holding["source"] = "strategy1"

        # ✅ extra 없으면 새로 dict 생성
        if "extra" not in holding or not isinstance(holding["extra"], dict):
            holding["extra"] = {}

        holding["extra"]["mode"] = "스윙" if is_swing else "단타"
        holding["extra"]["entry_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"💾 전략 전환 완료 → {symbol} → strategy1, 수익률: {expected_profit}, 목표가2: {target_2}, 목표가3: {target_3}")

        save_holdings_to_file()
        print("💾 holdings.json 저장 완료")


    return blocked_symbols


def run_strategy1(config):
    if config.get("strategy_switch_mode", false):
        print("🔄 전략 전환 모드 감지 → 진입 자본 무시 예정")

        holding_info = get_holding_info().get("KRW-A")
        if holding_info:
            holding_info["source"] = "strategy1"
            holding_info["score"] = "strategy1"
            holding_info["expected_profit"] = 0.05
            holding_info["target_2"] = 110
            holding_info["target_3"] = 120
            save_holdings_to_file()

            print(f"✅ 전략1로 전환 성공 → {holding_info}")
            return {
                "종목": "KRW-A",
                "전략": "strategy1",
                "진입가": holding_info["entry_price"],
                "전환모드": True,
                "진입시간": holding_info["entry_time"]
            }

    # 리스트 갱신을 위한 전역 변수
    if "last_update" not in config:
        config["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 15분마다 리스트 갱신
    now = datetime.now()
    last_update = datetime.strptime(config["last_update"], "%Y-%m-%d %H:%M")

    if (now - last_update).seconds >= 900:
        print("🔄 15분 경과 → 리스트 갱신 시도")
        config["watchlist"] = get_top_rising_symbols(limit=35)
        config["last_update"] = now.strftime("%Y-%m-%d %H:%M")
        print("🔁 상승률 상위 35종목으로 리스트 갱신 완료!")

    watchlist = config.get("watchlist")

    # 만약 리스트가 비어있다면 즉시 새로 불러오기
    if not watchlist or len(watchlist) == 0:
        print("⚠️ 감시 종목 비어 있음 → 즉시 리스트 재요청")
        watchlist = get_top_rising_symbols(limit=35)
        config["watchlist"] = watchlist
        print("📥 감시 종목 부족 → 즉시 리스트 불러오기")

    print(f"[스캔대상] 현재 감시 종목 수: {len(watchlist)}개")
    print(f"[📊 오늘 상승률 상위 종목] {watchlist}")


   # ✅ [3] 전략 실행용 리스트
    selected = []

    # ✅ [4] 스캔 루프
    for symbol in get_all_krw_symbols():  # 전체 KRW 종목 기준으로 루프
        candles = get_candles(symbol, interval="15", count=30)

        if not candles or len(candles) < 5:
            continue

        # 리스트에 없는 종목인데 급등 감지된 경우 예외 진입 허용
        in_list = symbol in watchlist

        if not in_list:
            price_now = candles[0]["trade_price"]
            price_prev = candles[1]["trade_price"]
            price_change = (price_now - price_prev) / price_prev * 100

            volume_now = candles[0]["candle_acc_trade_volume"]
            volume_avg = sum([c["candle_acc_trade_volume"]
                             for c in candles[1:4]]) / 3

            if price_change >= 1.2 and volume_now >= volume_avg * 1.5:
                print(f"🚨 예외 급등 진입 허용: {symbol}")
            else:
                continue  # watchlist에도 없고 급등 조건도 없음 → 진입 차단

        # 💡 진입가 정의
        entry_price = candles[0]["trade_price"]


        # 💡 단타/스윙 모드 판별
        is_swing = judge_trade_type(candles)
        mode = "스윙" if is_swing else "단타"
        print(f"📌 전략 분기: {symbol} → 모드: {mode}")

        # 💡 피보나치 목표가 계산
        interval = "60" if mode == "스윙" else "15"
        candles_for_fib = get_candles(symbol, interval=interval, count=50)

        expected_profit, target_2, target_3 = calculate_fibonacci_targets(candles_for_fib, mode)

        # 💥 목표가 계산 실패한 경우 스킵
        if expected_profit is None:
            print(f"❌ {symbol} → 피보나치 목표가 계산 실패 → 스킵")
            continue

        print(f"🎯 목표가 계산 완료 → 예상수익률: {expected_profit:.2f}%, 2차: {target_2:.2f}, 3차: {target_3:.2f}")

        holding_symbols = get_holding_symbols()
        holding_count = get_holding_count()

        # ✅ 현재 이미 보유 중이면 진입 불가
        if symbol in holding_symbols:
            print(f"❌ {symbol} → 이미 보유 중 → 진입 불가")
            continue

        # ✅ 2종목 보유 중이면 원칙적으로 진입 제한
        if holding_count >= 2:
            print(f"❌ {symbol} → 2종목 보유 중 → 진입 제한")
            continue

        # 패턴 조건 중 하나라도 만족해야 함
        pattern_matched = (
            is_box_breakout(candles) or
            is_breakout_pullback(candles) or
            is_v_rebound(candles)
        )
        print(f"[패턴 체크] {symbol} → 패턴 결과: {pattern_matched}")

        if not pattern_matched:
            print(f"→ ❌패턴 불충족: {symbol}")
            continue

        # 보조지표 계산
        indicator_result = calculate_indicators(candles)
        satisfied = sum(1 for val in indicator_result.values() if val)

        # ✅ 디버깅 출력 추가
        print(f"[보조지표] {symbol} → 만족 수: {satisfied}/6, 결과: {indicator_result}")

        # 보조지표 필터: 6개 중 4개 이상
        if satisfied < 4:
            print(f"→ ❌ 조건 미충족: 6개 중 4개 이상 충족 실패")
            continue

        result = {
            "종목": symbol,
            "전략": "strategy1",
            "진입가": entry_price,
            "예상수익률": expected_profit,
            "예상손익비": rr,
            "스코어": score,
            "진입비중": assign_position_size(score),
            "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # ✅ 스코어 계산
        score = calculate_score_full(
    candles,
    pattern_matched,
    indicator_result,
    expected_profit,
     expected_loss)
        print(f"[스코어링] {symbol} → 총점: {score}점")

        if score < 50:
            print("→ ❌ 조건 미충족: 스코70점 미만")
            continue

        # ✅ 운영 자금 불러오기
        current_price = candles[-1]["trade_price"]
        capital = config["operating_capital"]
        # ✅ 진입 비중 계산 (예: 30%, 70%, 100%)
        position = assign_position_size(score, total_capital=capital)
        position_ratio = position / capital * 100
        print(f"[진입비중] {symbol} → {position_ratio:.0f}%")

        # 진입금액이 0이면 제외
        if position == 0:
            print(f"❌ 진입불가: 점수 낮음 → {symbol}")
            continue

        # 4. 진입 비중 결정
        if score >= 90:
            print(f"💡 진입전략: 100% 단일 진입")
        elif score >= 80:
            print(f"💡 진입전략: 1차 70% + 2차 30%")
        elif score >= 70:
            print(f"💡 진입전략: 1차 30% + 2차 70%")
        else:
            print(f"❌조건 미충족: 스코어 70점 미만 - 진입안함")
            continue

        balance = get_krw_balance()

        # 진입 자격 통과 후

        # ✅ 운영 자금 불러오기
        capital = config["operating_capital"]

        # ✅ 기본 진입 비중 (단일 종목이라면 100%)
        position = assign_position_size(score, total_capital=capital)
        position_ratio = position / capital * 100

        # ✅ 보유 종목이 있을 경우, 형식 검사 및 필터링
        holdings = get_holding_info()
        holdings = [h for h in holdings if isinstance(
            h, dict) and "score" in h and "expected_profit" in h]

        # ✅ 조건부 2종목 진입 시 → 자금 배분 조정
        if get_holding_count() == 1 and len(holdings) >= 1:
            prev = holdings[0]
            prev_score = prev["score"]
            prev_profit = prev["expected_profit"]

            # 자금 배분 로직 적용
            score_diff = abs(prev_score - score)

            # 스코어 기반 배분
            if score_diff >= 10:
                position = capital * 0.7 if score > prev_score else capital * 0.3
            elif score_diff >= 5:
                position = capital * 0.6 if score > prev_score else capital * 0.4
            else:
                position = capital * 0.5

            # 예외: 수익률 기대치 높은 종목 우선
            expected_gain = position * (expected_profit / 100)
            prev_gain = (capital - position) * (prev_profit / 100)

            if expected_gain > prev_gain * 1.2:
                position = capital * 0.6
            else:
                position = capital * 0.5

            position_ratio = position / capital * 100
            print(f"[자금조정] 배분 적용 → 최종 비중: {position_ratio:.0f}%")

        # 💡 진입가 정의
        entry_price = candles[0]["trade_price"]

        # 💡 진입 수량 계산
        quantity = math.floor((position / current_price) * 10000) / 10000
        total_cost = quantity * current_price * 1.0005  # 수수료 포함

        if total_cost > capital:
            print(f"❌ 진입 실패: 총 사용액({total_cost:.2f}) > 운영자금({capital:.2f})")
            continue

        if get_krw_balance() < total_cost:
            print(f"❌ 잔고 부족 → 현재: {get_krw_balance()}, 필요: {total_cost}")
            continue

        # ✅ 잔고 차감

        update_balance_after_buy(total_cost)

        # 💡 먼저 보유 기록 등록 (이제 quantity 정의됨)
        record_holding(
            symbol=symbol,
            entry_price=current_price,
            quantity=quantity,
            score=score,
            expected_profit=expected_profit,
            target_2=target2,
            target_3=target3,
            extra={
                "max_price": current_price,
                "prev_cci": indicators.get("cci", None),  # 혹은 None
                "mode": mode,
                "entry_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            source="strategy1"
        )

        print(f"✅ 전략1 진입 성공! {symbol}, 진입가: {current_price}, 수량: {quantity}")

        # 예측 수익률 통과 후
        # 보조지표 값에서 RSI, OBV, MACD 추출
        rsi_value = indicator_result.get("RSI_VALUE", 65)
        macd_hist = indicator_result.get("MACD_HIST", 0)
        obv_slope = indicator_result.get("OBV_SLOPE", True)

        # 단타/스윙 자동 분류
        mode = classify_trade_mode(candles[0], rsi_value, obv_slope, macd_hist)
        print(f"[전개방식] {symbol} → 판단 결과: {mode}")

        # 목표 수익률 계산
        if mode == "단타":
            target_profit = max(2.0, expected_profit)
        elif mode == "스윙":
            target_profit = expected_profit + 9.0  # 또는 +5.0 정도 더해도 OK
        else:
            target_profit = expected_profit

        if balance < position:
            print(f"❌ 잔고 부족: {symbol} → 보유 KRW {balance}, 필요 {position}")
            continue

        update_balance_after_buy(position)

        result = {
            "종목": symbol,
            "전략": "strategy1",
            "진입가": current_price,
            "예상수익률": expected_profit,
            "예상손익비": rr,
            "스코어": score,
            "진입비중": position_ratio,
            "진입금액": position,        # 원 단위
            "전개방식": mode,
            "목표가1": round(target_1, 2),
            "목표가2": round(target_2, 2),
            "목표가3": round(target_3, 2),
            "최고가": current_price,  # 진입가로 초기화
            "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        selected.append(result)

        if selected:
            return selected[0]

        return None


#테스트
if __name__ == "__main__":
    print("🚀 [전략1 진입 조건 평가 테스트 실행]")

    try:
        # config.json 파일 로드
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        config["strategy_switch_mode"] = True

        # holdings.json 상태 출력 (기존 포지션 확인용)
        from utils.balance import load_holdings_from_file
        holdings = load_holdings_from_file()
        print("📦 현재 holdings 상태:", json.dumps(holdings, indent=2, ensure_ascii=False))

        # 전략1 진입 조건 평가 실행
        from strategies.strategy1 import strategy1
        result = strategy1(config)

        # 결과 출력
        print("✅ 전략1 진입 결과:", result)

    except Exception as e:
        import traceback
        print("❌ 전략1 진입 테스트 중 오류 발생:")
        traceback.print_exc()

