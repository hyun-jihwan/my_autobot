from utils.candle import get_all_krw_symbols, get_candles

def get_top_rising_symbols(limit=35, min_volume=100000000):
    candidates = []

    for symbol in get_all_krw_symbols():
        candles = get_candles(symbol, interval="day", count=2)
        if not candles or len(candles) < 2:
            continue

        today = candles[0]
        yesterday = candles[1]

        # 전일 종가 기준 상승률 계산
        prev_close = yesterday["trade_price"]
        curr_close = today["trade_price"]

        if prev_close == 0:
            continue

        change_rate = (curr_close - prev_close) / prev_close * 100

        if change_rate <= 0:
            continue  # 📌 상승 종목만 포함

        volume = today["candle_acc_trade_price"]
        if volume < min_volume:
            continue

        candidates.append({
            "symbol": symbol,
            "change": change_rate,
            "volume": volume
        })

    if len(candidates) < 10:
        print(f"⚠️ 상승 종목 부족: {len(candidates)}개만 감지됨")

    top = sorted(candidates, key=lambda x: x["change"], reverse=True)[:limit]
    return [x["symbol"] for x in top]
