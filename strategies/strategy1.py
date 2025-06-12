import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from datetime import datetime
from utils.candle import get_candles, is_box_breakout, is_breakout_pullback, is_v_rebound
from utils.indicators import calculate_indicators
from utils.risk import calculate_expected_risk
from utils.score import calculate_score_full
from utils.candle import get_all_krw_symbols, get_candles
from utils.signal import classify_trade_mode
from utils.position import assign_position_size
from utils.balance import get_krw_balance, update_balance_after_buy, record_holding
from utils.balance import get_holding_symbols, get_holding_count, get_holding_info
from utils.balance import get_holdings, update_balance_after_sell
from utils.risk import calculate_swing_target_with_fibonacci, calculate_scalping_target
from utils.risk import judge_trade_type
from utils.filter import get_top_rising_symbols
from utils.trade import sell_market_order
from utils.trade import calculate_targets
from transition.strategy3_exit import handle_strategy3_exit
from sell_strategies.sell_strategy1 import check_sell_signal_strategy1, evaluate_swing_exit
from sell_strategies.sell_strategy1 import sell_strategy1
from sell_strategies.sell_utils import get_indicators


def run_strategy1(config):
    # ✅ 전략 3 종료 판단 먼저
    released = handle_strategy3_exit(config)

    if not config.get("ready_for_strategy1", False):
        print("⏸ 전략3 평가 중 → 전략1 대기")
        return

    # ✅ watchlist 및 자금 확인
    watchlist = config.get("watchlist", [])
    capital = config.get("operating_capital", 0)
    if capital < 5000:
        print("❌ 운영 자금 부족 → 전략1 중단")
        return

    # ✅ 중복 진입 제한용 blocked_symbols 초기화
    if "blocked_symbols" not in config:
        config["blocked_symbols"] = []

    # ✅ 전략2 포지션 평가 → 청산된 종목 리스트 반환
    blocked = handle_strategy2_positions() or []
    config["blocked_symbols"].extend(blocked)

    holdings = get_holding_info()  # 보유했던 종목들에서 score/expected_profit 불러오기

    # ✅ 전략1 진입 시작
    for symbol in watchlist:
        if symbol in config.get("blocked_symbols", []):
            # 이전 기록에서 score, expected_profit 찾아오기
            prior = next((h for h in holdings if h["symbol"] == symbol), None)

            if prior:
                score = prior.get("score", 0)
                expected_profit = prior.get("expected_profit", 0)

            # 예외 조건 충족 시 재진입 허용
                if (
                    score >= 80 and               # 전략 스코어 (예시)
                    expected_profit >= 0.03 and   # 기대 수익률 3% 이상
                    is_rising(symbol)            # 상승 캔들 2개 이상 or 직전 거래량 급등
                ):
                    print(f"✅ 예외 조건 충족: {symbol} → 전략 1 재진입 허용")
                    config["blocked_symbols"].remove(symbol)
                else:
                    print(f"🚫 차단된 종목 → {symbol} → 전략 1 재진입 금지")
                    continue

            else:
                print(f"⚠️ score/expected_profit 기록 없음 → {symbol} 차단 유지")
                continue

def handle_strategy2_positions():
    now = datetime.now()
    if now.strftime("%H:%M") < "09:15":
        return  # 아직 전략 2 시간 → 아무 것도 안 함

    print("🔁 전략 2 → 전략 1 전환 처리 시작")

    holdings = get_holdings()
    blocked_symbols = []

    for h in holdings:
        if h.get("source") == "strategy2":
            symbol = h["symbol"]
            entry_price = h["entry_price"]
            quantity = h["quantity"]
            entry_time = h.get("entry_time", "")

            print(f"📌 전략 2 잔여 종목 확인: {symbol} (진입 시간: {entry_time})")

            candles = get_candles(symbol, interval="15", count=30)
            if not candles or len(candles) < 12:
                continue

            hourly_candles = get_candles(symbol, interval="60", count=10)
            is_swing = judge_trade_type(hourly_candles)
            current_price = candles[0]["trade_price"]


            # ✅ 간단한 판단 로직 (보완된 조건)
            body = abs(candles[0]["opening_price"] - candles[0]["trade_price"])
            high = candles[0]["high_price"]
            low = candles[0]["low_price"]
            range_ratio = (high - low) / current_price * 100

            if is_swing:
                print(f"✅ {symbol} → 스윙 조건 충족 → 유지")
                continue
            elif range_ratio < 1.5 or body < (high - low) * 0.3:
                # 박스권 또는 정체로 판단
                print(f"❌ {symbol} → 정체 or 박스권 판단 → 전량 청산")
                sell_market_order(symbol)
                update_balance_after_sell(current_price * quantity)
                blocked_symbols.append(symbol)
            else:
                print(f"✅ {symbol} → 단타 조건 충족 → 유지")

    return blocked_symbols

def run_strategy1(config):
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

    # ✅ 전략 1 보유 종목 매도 조건 검사 (5분마다 실행)
    if "last_sell_check" not in config:
        config["last_sell_check"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    last_check = datetime.strptime(config["last_sell_check"], "%Y-%m-%d %H:%M")
    if (datetime.now() - last_check).seconds >= 300:  # 5분마다 검사
        config["last_sell_check"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        holdings = get_holdings()
        for h in holdings:
            if h.get("source") != "strategy1":
                continue

            symbol = h["symbol"]
            quantity = h["quantity"]
            candles = get_candles(symbol, interval="5", count=30)
            if not candles or len(candles) < 5:
                continue

            indicators = get_indicators(candles)
            signal = check_sell_signal_strategy1(h, candles, indicators)

            if signal:
                print(f"🚨 [전략1 매도] 조건 충족 → {symbol} / 사유: {signal}")
                price = candles[0]["trade_price"]

                sell_market_order(symbol)
                update_balance_after_sell(price * quantity)

                # 보유 종목 제거
                holdings.remove(h)


    # ✅ [3] 전략 실행용 리스트
    selected = []

    # ✅ [4] 스캔 루프
    for symbol in get_all_krw_symbols():  # 전체 KRW 종목 기준으로 루프
        candles = get_candles(symbol, interval="1", count=16)

        # 캔들 강제 수정 (전략1 테스트용)
        if len(candles) >= 16:
            for i in range(15):
                candles[i]["high_price"] = 100
                candles[i]["trade_price"] = 95
                candles[i]["candle_acc_trade_volume"] = 10000

            candles[-1] = {
                "trade_price": 110,
                "opening_price": 90,
                "high_price": 111,
                "low_price": 89,
                "candle_acc_trade_volume": 20000  # 이전보다 2배
            }

        if not candles or len(candles) < 12:
            continue


        # 리스트에 없는 종목인데 급등 감지된 경우 예외 진입 허용
        in_list = symbol in watchlist

        if not in_list:
            price_now = candles[0]["trade_price"]
            price_prev = candles[1]["trade_price"]
            price_change = (price_now - price_prev) / price_prev * 100

            volume_now = candles[0]["candle_acc_trade_volume"]
            volume_avg = sum([c["candle_acc_trade_volume"] for c in candles[1:4]]) / 3

            if price_change >= 1.2 and volume_now >= volume_avg * 1.5:
                print(f"🚨 예외 급등 진입 허용: {symbol}")
            else:
                continue  # watchlist에도 없고 급등 조건도 없음 → 진입 차단


        # ✅ 여기 아래에 이 코드 추가!

        entry_price = candles[0]["trade_price"]
        is_swing = judge_trade_type(candles)

        # ✅ 목표가 계산 (스윙일 때만)
        target_2, target_3 = 0, 0
        if is_swing:
            target_2, target_3 = calculate_targets(symbol)
            if target_2 is None or target_3 is None:
                print(f"⚠️ {symbol} → 목표가 계산 실패 → 스킵")
                continue  # 목표가 계산 실패 시 스킵

        if is_swing:
            candles_1h = get_candles(symbol, interval="60", count=30)
            expected_profit, expected_loss, rr, fib_0618, fib_1000, fib_1618, market_mode = calculate_swing_target_with_fibonacci(candles_1h)

            # 시장 상황에 따라 목표가 설정
            expected_target = fib_0618 if market_mode == "보수장" else (
                fib_1000 if market_mode == "중립장" else fib_1618
            )
            expected_profit = ((expected_target - entry_price) / entry_price) * 100

            print(f"[전략 분기] → 스윙 / 시장상태: {market_mode}")
            print(f"[목표가 설정] → {expected_target:.2f}원 / 수익률: {expected_profit:.2f}% / RR: {rr:.2f}")

        else:
            expected_profit, expected_loss, rr = calculate_scalping_target(candles)
            print(f"[전략 분기] → 단타 / 예상 수익률: {expected_profit:.2f}% / RR: {rr:.2f}")

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
            "진입가": candles[0]["trade_price"],
            "예상수익률": 5.0,
            "예상손익비": 2.0,
            "스코어": 85,
            "진입비중": assign_position_size(85),
            "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # ✅ 스코어 계산
        score = calculate_score_full(candles, pattern_matched, indicator_result, expected_profit, expected_loss)
        print(f"[스코어링] {symbol} → 총점: {score}점")

        if score < 50:
            print("→ ❌ 조건 미충족: 스코70점 미만")
            continue

        # ✅ 운영 자금 불러오기
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
            position = "100%"
        elif score >= 80:
            position = "1차 70% + 2차 30%"
        elif score >= 70: #테스트
            position = "1차 30% + 2차 70%"
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
        holdings = [h for h in holdings if isinstance(h, dict) and "score" in h and "expected_profit" in h]

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
        quantity = position / entry_price
        quantity = round(quantity, 3)

        # ✅ 잔고 차감
        update_balance_after_buy(position)

        # 💡 먼저 보유 기록 등록 (이제 quantity 정의됨)
        record_holding(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            score=score,
            expected_profit=expected,
            target_2=target2,
            target_3=target3,
            extra={
                "max_price":entry_price,
                "prev_cci": indicators.get("cci", None),  # 혹은 None
            'entry_time' : datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )

        print(f"✅ 전략1 진입 성공! {symbol}, 진입가: {entry_price}, 수량: {quantity}")

    print("📤 진입 루프 종료 → 매도 전략 실행")
    sell_strategy1(config)

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
        "진입가": candles[0]["trade_price"],
        "예상수익률": expected_profit,
        "예상손익비": rr,
        "스코어": score,
        "진입비중": position_ratio,
        "진입금액": position,        # 원 단위
        "전개방식": mode,
        "최고가": candles[0]["trade_price"],  # 진입가로 초기화
        "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    selected.append(result)

    if selected:
        return selected[0]


    return None

if __name__ == "__main__":
    import datetime
    from utils.balance import record_holding

    print("📥 테스트 진입 시작")

    record_holding(
        symbol="KRW-TEST",
        entry_price=100.0,
        quantity=5,
        score=80,
        expected_profit=0.3,
        entry_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    print("✅ 테스트 진입 완료 — holdings.json 저장을 확인해보세요")
