import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sell_strategies.sell_utils import get_indicators
from utils.balance import update_balance_after_sell, clear_holdings, remove_holding
from utils.log_utils import log_sell
from db.holdings import get_holding_symbols, get_holding_data
from utils.candle import get_candles


def sell_strategy2(candles_dict, balance):
    sell_results = []

    for symbol in get_holding_symbols():
        candles = candles_dict.get(symbol)
        if candles is None or len(candles) < 15:
            continue

        indicators = get_indicators(symbol, candles)
        if not indicators:
            continue

        holding = get_holding_data(symbol)
        entry_price = holding["entry_price"]
        quantity = holding["quantity"]
        prev_cci = holding.get("prev_cci")
        max_price = holding.get("max_price", entry_price)
        current_price = candles[-1]["trade_price"]

        # 최고가 갱신
        if current_price > max_price:
            max_price = current_price
            holding["max_price"] = max_price  # 상태 업데이트 필요

        # 1. 손절 조건: -2%
        loss_rate = (current_price - entry_price) / entry_price
        if loss_rate <= -0.02:
            update_balance_after_sell(symbol, current_price, quantity)
            remove_holding(symbol)
            log_sell(symbol, current_price, "전략2 손절 (-2%)")
            sell_results.append({
                "symbol": symbol,
                "price": current_price,
                "type": "손절"
            })
            continue

        # 2. 트레일링 익절 조건: 최고가 기준 수익률 ≥ 2%
        trail_rate = (max_price - entry_price) / entry_price
        if trail_rate >= 0.02:
            condition_count = 0

            # 🧪 로그: 기본 정보 출력
            print(f"🧪 진입가: {entry_price} / 최고가: {max_price} / 현재가: {current_price}")
            print(f"🧪 trail_rate: {trail_rate:.4f}")


            # 조건 1: VWAP 이탈
            if current_price < indicators["vwap"]:
                condition_count += 1
                print("✅ 조건 1 통과: 현재가 < VWAP")
            else:
                print("❌ 조건 1 불충족: 현재가 >= VWAP")

            # 조건 2: 볼린저 상단 돌파 후 복귀
            bb_upper = indicators.get("bb_upper")
            prev_high = candles[-2]["high_price"]
            if bb_upper and prev_high > bb_upper and current_price < bb_upper:
                condition_count += 1
                print("✅ 조건 2 통과: 볼밴 상단 복귀")
            else:
                print("❌ 조건 2 불충족")


            # 조건 3: CCI 급락
            cci = indicators.get("cci")
            if prev_cci is not None and prev_cci > 100 and cci is not None and cci < 80:
                condition_count += 1
                print("✅ 조건 3 통과: CCI 급락")
            else:
                print("❌ 조건 3 불충족")

            holding["prev_cci"] = cci  # 상태 업데이트 필요

            # 조건 4: OBV 하락 반전
            if indicators["obv_prev"] > indicators["obv"]:
                condition_count += 1
                print("✅ 조건 4 통과: OBV 하락")
            else:
                print("❌ 조건 4 불충족")


            print(f"🧮 통과된 조건 수: {condition_count}")

            # 조건 2개 이상 만족 → 익절
            if condition_count >= 2:
                update_balance_after_sell(symbol, current_price, quantity)
                remove_holding(symbol)
                log_sell(symbol, current_price, f"전략2 익절 (지표 {condition_count}개 충족)")
                sell_results.append({
                    "symbol": symbol,
                    "price": current_price,
                    "type": "익절"
                })

    return sell_results

#테스트 시작
if __name__ == "__main__":
    import json

    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ config.json 로드 실패: {e}")
        config = {"operating_capital": 10000}

    # 테스트용 전체 보유 종목 캔들 수집
    candles_dict = {}
    for symbol in get_holding_symbols():
        candles = get_candles(symbol, interval="1", count=30)
        candles_dict[symbol] = candles

    # 임시 잔고 예시 (필요시 수정)
    balance = config.get("operating_capital", 10000)

    result = sell_strategy2(candles_dict, balance)
    print("📦 전략2 청산 결과:", result)

#테스트 끝
