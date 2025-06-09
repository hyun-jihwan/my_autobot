from datetime import datetime
from utils.candle import get_all_krw_symbols, get_candles

def detect_strategy2_signals():
    now = datetime.now()
    if not ("09:00" <= now.strftime("%H:%M") < "09:15"):
        return []

    detected = []
    for symbol in get_all_krw_symbols():
        candles = get_candles(symbol, interval="1", count=4)
        if len(candles) < 4:
            continue

        price_now = candles[0]["trade_price"]
        price_prev = candles[1]["trade_price"]
        price_diff = (price_now - price_prev) / price_prev * 100

        volume_now = candles[0]["candle_acc_trade_volume"]
        volume_avg = sum([c["candle_acc_trade_volume"] for c in candles[1:4]]) / 3

        if price_diff >= 1.5 and volume_now > volume_avg * 2:
            detected.append(symbol)

    return detected
