import sys
import os
import json
import time
import datetime
from datetime import datetime

# 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ✅ 유틸 함수 및 모듈
from sell_strategies.sell_utils import get_indicators
from sell_strategies.sell_strategy1 import check_sell_signal_strategy1
from transition.strategy3_exit import handle_strategy3_exit
from utils.candle import get_all_krw_symbols, get_candles
from utils.filter import get_top_rising_symbols
from utils.indicators import calculate_indicators
from utils.position import assign_position_size
from utils.risk import (
    judge_trade_type,
    calculate_scalping_target,
    calculate_swing_target_with_fibonacci,
)
from utils.score import calculate_score_full
from utils.signal import classify_trade_mode
from utils.trade import sell_market_order, calculate_targets
from utils.balance import (
    get_krw_balance,
    get_holdings,
    get_holding_info,
    get_holding_symbols,
    get_holding_count,
    update_balance_after_buy,
    update_balance_after_sell,
    record_holding,
    save_holdings_to_file,
)
from utils.transition_helper import evaluate_exit


def has_active_strategy3_position():
    for h in get_holdings():
        if h.get("source") == "strategy3":
            print(f"⛔ 전략3 포지션 유지 중 → 전략1 진입 차단: {h['symbol']}")
            return True
    return False


def strategy1(config):
    print("📥 전략1 실행 시작")

    total_krw_balance = get_krw_balance()
    print(f"💰 현재 총 보유 KRW 잔고: {total_krw_balance:,.0f}원")

    capital = 10000  # 테스트용 운영 자본
    print(f"⚙️ 전략에 사용할 운영자금: {capital:,.0f}원")

    if capital > total_krw_balance:
        print("❌ 보유 잔고보다 많은 금액을 설정했습니다.")
        return None
    if capital < 1000:
        print("❌ 자본 부족으로 진입 불가")
        return None

    # ✅ 테스트용 강제 진입 심볼
    symbol = "KRW-TEST"
    candles = get_candles(symbol, interval="15", count=30)
    if not candles or len(candles) < 1:
        print(f"❌ 캔들 데이터 부족: {symbol}")
        return None

    entry_price = candles[0]["trade_price"]
    position = capital
    quantity = round(position / entry_price, 3)

    update_balance_after_buy(position)

    record_holding(
        symbol=symbol,
        entry_price=entry_price,
        quantity=quantity,
        score=80,
        expected_profit=5.0,
        target_2=110,
        target_3=120,
        source="strategy1",
        extra={
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_price": entry_price,
            "mode": "스윙"
        }
    )

    print(f"✅ 전략1 진입 성공: {symbol} / 진입가: {entry_price} / 수량: {quantity}")
    return {
        "종목": symbol,
        "진입가": entry_price,
        "진입금액": position,
        "진입시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def handle_strategy2_positions():
    now = datetime.now()
    if now.strftime("%H:%M") < "09:15":
        return []

    print("🔁 전략 2 → 전략 1 전환 처리 시작")
    holdings = get_holdings()
    blocked_symbols = []

    for h in holdings:
        if h.get("source") != "strategy2":
            continue

        symbol = h["symbol"]
        quantity = h["quantity"]
        print(f"📌 전략 2 잔여 종목 확인: {symbol}")

        candles = get_candles(symbol, interval="15", count=30)
        if not candles or len(candles) < 12:
            continue

        result = evaluate_exit(symbol, quantity, source="strategy2")
        if not result:
            blocked_symbols.append(symbol)

    return blocked_symbols


def run_strategy1(config):
    if handle_strategy3_exit(config) is None:
        print("⏸ 전략3 평가 중 → 전략1 대기")
        return

    if has_active_strategy3_position():
        return

    # 자본 및 리스트 확인
    capital = config.get("operating_capital", 0)
    if capital < 5000:
        print("❌ 운영 자금 부족 → 전략1 중단")
        return

    if "blocked_symbols" not in config:
        config["blocked_symbols"] = []

    # 전략2 포지션 평가
    config["blocked_symbols"].extend(handle_strategy2_positions() or [])

    watchlist = config.get("watchlist", [])
    if not watchlist:
        print("⚠️ 감시 종목 없음 → 리스트 갱신 필요")
        watchlist = get_top_rising_symbols(limit=35)
        config["watchlist"] = watchlist

    holdings = get_holding_info()
    selected = []

    for symbol in watchlist:
        if symbol in config["blocked_symbols"]:
            prior = next((h for h in holdings if h["symbol"] == symbol), None)
            if not prior:
                continue
            if prior.get("score", 0) < 80:
                continue

        candles = get_candles(symbol, interval="15", count=30)
        if not candles or len(candles) < 5:
            continue

        entry_price = candles[0]["trade_price"]
        is_swing = judge_trade_type(candles)

        if is_swing:
            candles_1h = get_candles(symbol, interval="60", count=30)
            _, _, _, fib_0618, fib_1000, fib_1618, market_mode = calculate_swing_target_with_fibonacci(candles_1h)
            expected_target = fib_0618 if market_mode == "보수장" else (fib_1000 if market_mode == "중립장" else fib_1618)
            expected_profit = (expected_target - entry_price) / entry_price * 100
        else:
            expected_profit, _, _ = calculate_scalping_target(candles)

        indicator_result = calculate_indicators(candles)
        satisfied = sum(1 for v in indicator_result.values() if v)

        if satisfied < 4:
            continue

        score = calculate_score_full(
            candles, True, indicator_result, expected_profit, 2.0
        )

        if score < 70:
            continue

        # 진입 비중 계산
        position = assign_position_size(score, total_capital=capital)
        if position == 0:
            continue

        if get_holding_count() >= 2:
            continue

        quantity = round(position / entry_price, 3)
        update_balance_after_buy(position)

        mode = "스윙" if is_swing else "단타"

        record_holding(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            score=score,
            expected_profit=expected_profit,
            target_2=0,
            target_3=0,
            source="strategy1",
            extra={
                "max_price": entry_price,
                "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode
            }
        )

        print(f"✅ 전략1 진입 성공! {symbol}, 진입가: {entry_price}, 수량: {quantity}")
        selected.append(symbol)

        break  # 한 종목만 진입

    return selected[0] if selected else None


if __name__ == "__main__":
    with open("config.json", "r") as f:
        config = json.load(f)
    result = strategy1(config)
    print(result)
