# scanners/scanner3.py

import datetime
from utils.candle import get_all_krw_symbols, get_candles

def detect_fast_rising_symbols():
    print("📡 급등 감지 함수 실행 중")

    candidates = []
    now = datetime.datetime.now()
    hour = now.hour

    for symbol in get_all_krw_symbols():
        candles = get_candles(symbol, interval="1", count=16)
        if len(candles) < 16:
            continue

        c0 = candles[-1]
        c1 = candles[-2]
        volume_avg = sum([c["candle_acc_trade_volume"] for c in candles[1:4]]) / 3
        volume_now = c0["candle_acc_trade_volume"]

        price_now = c0["trade_price"]
        price_prev = c1["trade_price"]
        price_change = (price_now - price_prev) / price_prev * 100

        if price_change >= 1.2 and volume_now > volume_avg * 1.8:
            score = price_change * (volume_now / volume_avg) * 10
            candidates.append({
                "symbol": symbol,
                "score": round(score, 2),
                "price_change": round(price_change, 2),
                "volume_ratio": round(volume_now / volume_avg, 2)
            })

    if candidates:
        print(f"⚡ 급등 후보 감지: {len(candidates)}개")
        for c in sorted(candidates, key=lambda x: x["score"], reverse=True):
            print(f"📈 {c['symbol']} | 점수: {c['score']} | 상승률: {c['price_change']}% | 거래량 배수: {c['volume_ratio']}배")
    else:
        print("📭 급등 후보 없음")

    return candidates
