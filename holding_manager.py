# holding_manager.py

from utils.balance import (
    get_holding_info, remove_holding,
    update_balance_after_sell, get_current_price
)
from utils.candle import get_candles


def handle_existing_holdings(config):
    capital = config.get("operating_capital", 0)
    if capital <= 0:
        print("❌ 운영 자금이 설정되지 않았습니다.")
        return

    holdings = get_holding_info()
    if not holdings:
        return

    print(f"🧾 장시작 전 보유 종목 확인: {len(holdings)}개")

    for symbol, h in list(holdings.items()):
        candles = get_candles(symbol, interval="1", count=3)
        if not candles or len(candles) < 3:
            print(f"⚠️ 캔들 부족: {symbol}")
            continue

        c1, c2, c3 = candles[2], candles[1], candles[0]
        bullish_candles = sum(c["trade_price"] > c["opening_price"] for c in [c1, c2, c3])
        up = bullish_candles >= 2
        vol_up = c3["candle_acc_trade_volume"] > c2["candle_acc_trade_volume"] * 1.3

        if up and vol_up:
            print(f"✅ 유지 결정 → {symbol}")
            continue

        print(f"⚠️ 청산 결정 → {symbol}")
        current_price = get_current_price(symbol)
        quantity = h["quantity"]
        estimated_value = current_price * quantity
        update_balance_after_sell(symbol, current_price, quantity)
        remove_holding(symbol)
        config["switch_allowed"] = 2  # 전략 내 갈아타기 최대 2회 허용 등록
