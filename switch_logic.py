# switch_logic.py
import datetime
from utils.balance import (
    get_holdings, update_balance_after_sell,
    clear_holdings, save_holdings_to_file,
    update_balance_after_buy, record_holding
)
from utils.candle import get_candles
from switch_manager import has_switched_today, set_switch_today
from external_api import get_top_gainer

def try_switch():
    holdings = get_holdings()
    if not holdings:
        return None, None  # 보유 없음

    if has_switched_today():
        print("❌ 이미 갈아타기 1회 완료 (금일 제한)")
        return None, None

    current = list(holdings.values())[0]
    symbol = current["symbol"]
    entry_price = current["entry_price"]
    quantity = current["quantity"]

    # 📊 현재가 + 거래량 불러오기
    candles = get_candles(symbol, interval="1", count=2)

    # 안전 검사
    if len(candles) < 2:
        print(f"❌ 캔들 부족 → {symbol} / count=2")
        return None, None

    previous_candle = candles[-2]  # 직전 캔들
    current_candle = candles[-1]   # 현재 캔들

    now_price = current_candle["trade_price"]
    now_volume = current_candle["candle_acc_trade_volume"]
    prev_volume = previous_candle["candle_acc_trade_volume"]

    # 오차 여유값 설정
    PRICE_BUFFER = 0.001  # 0.1% 정도 여유
    VOLUME_BUFFER = 0.1   # 10% 여유

    # 수익률 계산
    price_change = (now_price - entry_price) / entry_price
    volume_ratio = now_volume / prev_volume if prev_volume > 0 else 1

    # 정체 흐름 체크 (최근 5분간 고점 못 넘김)
    recent_highs = [c["high_price"] for c in candles]
    is_stagnant = max(recent_highs) <= entry_price * (1 + 0.005)

    if price_change <= (-0.01 + PRICE_BUFFER) or is_stagnant:
        print(f"⚠️ {symbol} → 수익률 {price_change:.2%}, 정체: {is_stagnant} → 갈아타기 실행")
        update_balance_after_sell(symbol, now_price, quantity)
        clear_holdings()
        save_holdings_to_file()
        set_switch_today()
        print(f"✅ {symbol} 청산 완료. 갈아타기 가능")
        return symbol, "switched"  # 방금 청산한 종목명 반환

    elif price_change >= (0.013 - PRICE_BUFFER) and volume_ratio >= (1.5 - VOLUME_BUFFER):
        print(f"✅ {symbol} 급등 흐름 → 전략만 'strategy2'로 전환")
        # 보유 종목은 그대로, 전략 전환만 허용
        save_holdings_to_file()
        return symbol, "mode_change_only"

    else:
        print(f"⚠️ {symbol} 청산 조건 → 수익률: {price_change:.2%}, 거래량 증가율: {volume_ratio:.2f}")
        update_balance_after_sell(symbol, now_price, quantity)
        clear_holdings()
        save_holdings_to_file()
        set_switch_today()
        print(f"✅ {symbol} 청산 완료. 전략2 진입 가능 상태 전환")
        return symbol, "switched"

def should_switch_to_other(symbol, entry_price, entry_time):
    now = datetime.datetime.now()
    entry_dt = datetime.datetime.strptime(entry_time, "%Y-%m-%d %H:%M:%S")
    diff = (now - entry_dt).seconds

    if diff < 180 or diff > 360:  # 3~6분 사이만 감시
        return False

    candles = get_candles(symbol, interval="1", count=5)
    if len(candles) < 5:
        return False

    current_price = candles[-1]["trade_price"]
    recent_highs = [c["high_price"] for c in candles[:-1]]
    recent_volumes = [c["candle_acc_trade_volume"] for c in candles]

    price_change = (current_price - entry_price) / entry_price
    max_high = max(recent_highs)
    avg_volume = sum(recent_volumes[:-1]) / 4
    curr_volume = recent_volumes[-1]

    if price_change < 0.01 and max_high < current_price * 1.003 and curr_volume < avg_volume * 1.2:
        print(f"📉 {symbol} → 흐름 약함 (수익률 {price_change:.2%}, 거래량↓, 고점 미돌파)")
        return True
    return False


def execute_switch_to_new(symbol, current_price, quantity, new_symbol, config):
    print(f"🚨 {symbol} → 갈아타기 실행 → {new_symbol}")

    # ✅ 전략 전환이므로 자본 무시하도록 설정
    config["strategy_switch_mode"] = True  # ← 이 줄 추가

    update_balance_after_sell(symbol, current_price, quantity)
    clear_holdings()

    candles = get_candles(new_symbol, interval="1", count=1)
    if not candles:
        print(f"❌ {new_symbol} 캔들 조회 실패")
        return

    entry_price = candles[-1]["trade_price"]
    quantity = config["operating_capital"] / entry_price
    update_balance_after_buy(config["operating_capital"])

    record_holding(
        symbol=new_symbol,
        entry_price=entry_price,
        quantity=quantity,
        score=None,
        expected_profit=None,
        target_2=0,
        target_3=0,
        extra={
            "entry_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_price": entry_price,
        },
        source="strategy2"
    )

    save_holdings_to_file()
    set_switch_today()
    print(f"✅ 갈아타기 완료 → {new_symbol} 진입 성공")
