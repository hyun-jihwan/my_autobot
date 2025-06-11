from utils.sell_utils import get_indicators
from utils.order_utils import update_balance_after_sell, clear_holdings
from utils.log_utils import log_sell
from db.holdings import get_holding_symbols, get_holding_data

def sell_strategy2(candles_dict, balance):
    sell_results = []

    for symbol in get_holding_symbols():
        candles = candles_dict.get(symbol)
        if candles is None or len(candles) < 15:
            continue

        indicators = get_indicators(candles)
        if not indicators:
            continue

        holding = get_holding_data(symbol)
        entry_price = holding["entry_price"]
        quantity = holding["quantity"]
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
            clear_holdings(symbol)
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

            # 조건 1: VWAP 이탈
            if current_price < indicators["vwap"]:
                condition_count += 1

            # 조건 2: 볼린저 상단 돌파 후 복귀
            bb_upper = indicators.get("bb_upper")
            prev_high = candles[-2]["high_price"]
            if bb_upper and prev_high > bb_upper and current_price < bb_upper:
                condition_count += 1

            # 조건 3: CCI 급락
            cci = indicators.get("cci")
            prev_cci = holding.get("prev_cci")
            if prev_cci is not None and prev_cci > 100 and cci < 80:
                condition_count += 1
            holding["prev_cci"] = cci  # 상태 업데이트 필요

            # 조건 4: OBV 하락 반전
            if indicators["obv_prev"] > indicators["obv"]:
                condition_count += 1

            # 조건 2개 이상 만족 → 익절
            if condition_count >= 2:
                update_balance_after_sell(symbol, current_price, quantity)
                clear_holdings(symbol)
                log_sell(symbol, current_price, f"전략2 익절 (지표 {condition_count}개 충족)")
                sell_results.append({
                    "symbol": symbol,
                    "price": current_price,
                    "type": "익절"
                })

    return sell_results
