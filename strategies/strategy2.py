# strategies/strategy2.py
import sys
import os
import json
import math
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")


import datetime
from utils.candle import get_candles
from utils.balance import (
    get_krw_balance, update_balance_after_buy,
    get_holding_symbols, record_holding, has_switched,
    get_holdings, save_holdings_to_file, get_max_buyable_amount
)
from holding_manager import handle_existing_holdings
from switch_logic import try_switch, should_switch_to_other, execute_switch_to_new
from switch_manager import has_switched_today, set_switch_today


def is_within_strategy_time():
    return True  # 테스트 용

    now = datetime.datetime.now()
    start = datetime.datetime(now.year, now.month, now.day, 9, 0)
    end = datetime.datetime(now.year, now.month, now.day, 9, 15, 59)
    return start <= now <= end


def recent_high_breakout(candles, current_price):
    highs = [c["high_price"] for c in candles[:-1]]  # 최근 15분 기준
    return current_price > max(highs)


def analyze_candle_structure(candle):
    o, h, l, c = candle["opening_price"], candle["high_price"], candle["low_price"], candle["trade_price"]
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    range_ = h - l if h != l else 1  # 0으로 나누지 않게 처리

    body_ratio = body / range_
    upper_ratio = upper_wick / body if body != 0 else 1
    lower_ratio = lower_wick / body if body != 0 else 1

    if body_ratio >= 0.6 and upper_ratio <= 0.3:
        return "공격진입"
    elif body_ratio >= 0.4 and upper_ratio <= 0.4:
        return "보수진입"
    else:
        return "진입금지"


def run_strategy2(config):
    # ✅ 전환 시 자본 체크 우회용 플래그 설정
    config["strategy_switch_mode"] = True  # ← 이 줄 추가

    if not is_within_strategy_time():
        print("⛔ 전략2 실행 시간 아님 (09:00~09:15 한정)")
        return None

    # ✅ 전략 1 → 전략 2 전환 판단 블록을 맨 앞에 넣는다
    holdings = get_holdings()
    if holdings and not has_switched_today():
        h = list(holdings.values())[0]
        sym = h["symbol"]
        ep = h["entry_price"]
        qt = h["quantity"]
        et = h["entry_time"]

        if should_switch_to_other(sym, ep, et):
            from external_api import get_top_gainer
            new_symbol = get_top_gainer()
            now_price = get_candles(sym, interval="1", count=1)[0]["trade_price"]
            execute_switch_to_new(sym, now_price, qt, new_symbol, config)


    # ✅ 갈아타기 판단 (하루 1회 제한)
    switched_symbol, switch_status = try_switch()

    if switch_status == "mode_change_only":
        print(f"🔄 보유 종목 전략만 변경 → {switched_symbol}")

    # 현재 holdings.json 상태 불러오기
    holdings = get_holdings()
    if switched_symbol in holdings:
        holdings[switched_symbol]["source"] = "strategy2"
        holdings[switched_symbol]["score"] = None
        holdings[switched_symbol]["expected_profit"] = None
        holdings[switched_symbol]["target_2"] = 0
        holdings[switched_symbol]["target_3"] = 0
        save_holdings_to_file()
        print(f"✅ 전략 전환 완료 → {switched_symbol} → strategy2")
    else:
        print(f"⚠️ 전략 전환 대상 보유 종목 없음 → {switched_symbol} 누락")

    if switch_status == "switched":
        print(f"✅ 갈아타기 완료 → 기존 종목: {switched_symbol}")
    elif switch_status == "mode_change_only":
        # 전략만 바뀐 경우, 추가 메시지 생략
        pass
    else:
        print("❌ 갈아타기 조건 불충족 or 이미 오늘 갈아탐")

    watchlist = config.get("watchlist", [])
    selected = []


    for symbol in watchlist:
        if has_switched():
            print("🚫 이미 갈아타기 진행됨 → 추가 진입 차단")
            return None

        if symbol == switched_symbol:
            print(f"현재 루프: {symbol}")
            continue  # 방금 청산한 종목이면 재진입 금지


        candles = get_candles(symbol, interval="1", count=16)  # 15개 + 현재 캔들

        if len(candles) < 16:
            print(len(candles), candles)
            continue

        prev = candles[-2]
        current = candles[-1]

        o, h, l, c = current["opening_price"], current["high_price"], current["low_price"], current["trade_price"]
        v_prev = prev["candle_acc_trade_volume"]
        v_now = current["candle_acc_trade_volume"]

        print(f"🔥 거래량 확인 → {symbol} / 이전: {v_prev} / 현재: {v_now}")

        if v_now < v_prev * 1.3:
            print(f"⛔ 거래량 조건 미달 → {symbol} / 현재: {v_now}, 필요 최소: {v_prev * 1.3:.0f}")
            continue  # 거래량 부족
        else:
            print(f"✅ 거래량 조건 충족 → {symbol} / 현재: {v_now}, 기준: {v_prev * 1.3:.0f}")

        if not recent_high_breakout(candles, c):
            print(f"❌ 고점 돌파 실패 → {symbol} / 현재가: {c}")
            continue  # 고점 돌파 실패
        else:
            print(f"✅ 고점 돌파 성공 → {symbol}")


        entry_type = analyze_candle_structure(current)
        print(f"🔥 진입유형 판단 → {symbol} / 유형: {entry_type}")

        if entry_type == "진입금지":
            print(f"❌ 캔들 구조상 진입금지 → {symbol}")
            continue

        if symbol in get_holding_symbols():
            print(f"❌ 이미 보유 중 → {symbol}")
            continue

        # ✅ 진입 실행
        current_price = candles[0]["trade_price"]
        capital = get_max_buyable_amount()

        if capital < 5000:
            print("❌ 운영 자금 부족 (최소 5000원 필요)")
            continue

        quantity = math.floor((capital / current_price) * 10000) / 10000
        used_krw = round(quantity * current_price, 2)

        if used_krw > get_krw_balance():
            print(f"❌ 매수 잔고 차감 실패: 잔고 부족: KRW={get_krw_balance()} < 사용액={used_krw}")
            return None

        update_balance_after_buy(used_krw)

        record_holding(
            symbol=symbol,
            entry_price=current_price,
            quantity=quantity,
            score=None,
            expected_profit=None,
            target_2=0,
            target_3=0,
            extra={
                "entry_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "max_price": current_price
            },
            source="strategy2"
        )

        result = {
            "종목": symbol,
            "전략": "strategy2",
            "진입가": c,
            "진입시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "진입유형": entry_type
        }

        selected.append(result)
        print(f"✅ 전략2 {entry_type} 완료 → {symbol} / 진입가: {c} / 수량: {quantity:.2f}")
        break  # 1종목만 진입



    return selected if selected else None

#테스트 시작
if __name__ == "__main__":
    print("🧪 [전략2 전환 테스트 실행]")


    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ config.json 로드 실패: {e}")
        config = {"operating_capital": 10000, "watchlist": ["KRW-A"]}

    result = run_strategy2(config)
    print(result)
#테스트 끝
