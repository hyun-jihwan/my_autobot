# switch_logic.py
from utils.balance import get_holdings, update_balance_after_sell, clear_holdings
from utils.candle import get_candles
from switch_manager import has_switched_today, set_switch_today

def try_switch():
    holdings = get_holdings()
    if not holdings:
        return None, None  # 보유 없음

    if has_switched_today():
        print("❌ 이미 갈아타기 1회 완료 (금일 제한)")
        return None, None

    current = holdings[0]
    symbol = current["symbol"]
    entry_price = current["entry_price"]
    quantity = current["quantity"]
    now_price = get_candles(symbol, interval="1", count=1)[0]["trade_price"]

    # 수익률 계산
    price_change = (now_price - entry_price) / entry_price

    # 정체 흐름 체크 (최근 5분간 고점 못 넘김)
    candles = get_candles(symbol, interval="1", count=5)
    recent_highs = [c["high_price"] for c in candles]
    is_stagnant = max(recent_highs) <= entry_price * 1.005

    if price_change <= -0.01 or is_stagnant:
        print(f"⚠️ {symbol} → 수익률 {price_change:.2%}, 정체: {is_stagnant} → 갈아타기 실행")
        update_balance_after_sell(now_price * quantity)
        clear_holdings()
        set_switch_today()
        print(f"✅ {symbol} 청산 완료. 갈아타기 가능")
        return symbol, "switched"  # 방금 청산한 종목명 반환
    else:
        print(f"⏸ {symbol} 유지. 수익률 {price_change:.2%} / 정체: {is_stagnant}")
        return None, None
