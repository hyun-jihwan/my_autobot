import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sell_strategies.sell_utils import get_indicators
from utils.balance import (
    update_balance_after_sell,
    update_holding_field, get_holding_symbols,
    get_holding_data, remove_holding
)
from utils.log_utils import log_sell
from utils.candle import get_candles
from utils.trade import sell_market_order
from utils.telegram import notify_sell
from utils.error_handler import handle_error


def sell_strategy2(candles_dict, balance, config=None):
    sell_results = []

    for symbol in get_holding_symbols():
        try:
            candles = candles_dict.get(symbol)
            if candles is None or len(candles) < 15:
                print(f"⚠️ 캔들 부족 → {symbol} / 받아온 수: {len(candles) if candles else 0}")
                continue

            indicators = get_indicators(symbol, candles)
            if not indicators:
                continue

            holding = get_holding_data(symbol)
            if not holding:
                continue

            entry_price = holding["entry_price"]
            quantity = holding["quantity"]
            prev_cci = holding.get("prev_cci")
            max_price = holding.get("max_price", entry_price)
            current_price = candles[-1]["trade_price"]

            if current_price > max_price:
                max_price = current_price
                update_holding_field(symbol, "max_price", max_price)

            loss_rate = (current_price - entry_price) / entry_price
            profit = round((current_price - entry_price) * quantity)
            current_balance = get_krw_balance()

            # 1️⃣ 손절 조건
            if loss_rate <= -0.02:
                try:
                    sell_market_order(symbol)
                    update_balance_after_sell(symbol, current_price, quantity)
                    remove_holding(symbol)
                    log_sell(symbol, current_price, "전략2 손절 (-2%)")

                    notify_sell(
                        symbol=symbol,
                        strategy="2",
                        buy_price=entry_price,
                        sell_price=current_price,
                        profit=profit,
                        balance=current_balance,
                        exit_type="손절",
                        config=config
                    )

                    print(f"✅ 전략2 손절 완료: {symbol} @ {current_price}")
                    sell_results.append({
                        "symbol": symbol,
                        "price": current_price,
                        "type": "손절"
                    })
                except Exception as e:
                    handle_error(e, location=f"sell_strategy2.py - 손절 - {symbol}", config=config)

                continue

            # 2️⃣ 트레일링 익절 조건
            trail_rate = (max_price - entry_price) / entry_price
            if trail_rate >= 0.02:
                condition_count = 0

                bb_upper = indicators.get("bb_upper")
                prev_high = candles[-2]["high_price"]
                cci = indicators.get("cci")

                if current_price < indicators["vwap"]:
                    condition_count += 1
                if bb_upper and prev_high > bb_upper and current_price < bb_upper:
                    condition_count += 1
                if prev_cci is not None and prev_cci > 100 and cci is not None and cci < 80:
                    condition_count += 1
                if indicators["obv_prev"] > indicators["obv"]:
                    condition_count += 1

                update_holding_field(symbol, "prev_cci", cci)

                if condition_count >= 2:
                    try:
                        sell_market_order(symbol)
                        update_balance_after_sell(symbol, current_price, quantity)
                        remove_holding(symbol)
                        log_sell(symbol, current_price, f"전략2 익절 (조건 {condition_count}개)")

                        notify_sell(
                            symbol=symbol,
                            strategy="2",
                            buy_price=entry_price,
                            sell_price=current_price,
                            profit=profit,
                            balance=current_balance,
                            exit_type="익절",
                            config=config
                        )

                        print(f"✅ 전략2 익절 완료: {symbol} @ {current_price}")
                        sell_results.append({
                            "symbol": symbol,
                            "price": current_price,
                            "type": "익절"
                        })
                    except Exception as e:
                        handle_error(e, location=f"sell_strategy2.py - 익절 - {symbol}", config=config)

        except Exception as e:
            handle_error(e, location=f"sell_strategy2.py - 루프 내부 - {symbol}", config=config)

    print(f"💼 청산 후 보유 종목: {get_holding_symbols()}")
    return sell_results
