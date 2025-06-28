# 전략 1 매도 조건 완성 버전 (단타 / 스윙 분기 포함)
import sys
import os
import json
import time
import traceback
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from sell_strategies.sell_utils import (
    get_indicators, check_sell_signal_strategy1,
    check_sell_signal_strategy_swing
)
from utils.balance import (
    load_holdings_from_file, save_holdings_to_file,
    remove_holding,update_balance_after_sell
)
from utils.candle import get_candles
from utils.trade import sell_market_order
from utils.log_utils import log_sell
from utils.telegram import notify_sell
from utils.error_handler import handle_error
from utils.price import get_current_price


def get_latest_price(symbol):
    """1분봉을 사용한 체결가 보정"""
    candles = get_candles(symbol, interval="1", count=1)
    if candles and len(candles) > 0:
        return candles[0]["trade_price"]
    return None



def sell_strategy1(config):
    print("📤 매도 전략1 실행됨")

    try:
        balance = load_holdings_from_file()
        holdings = balance.get("holdings", {})

        if not holdings:
            print("⚠️ 현재 보유 중인 종목이 없습니다.")
            return

        for symbol, data in holdings.copy().items():
            try:
                print(f"📤 매도 체크: {symbol}")

                entry_price = data["entry_price"]
                quantity = data["quantity"]
                mode = data.get("extra", {}).get("mode", "단타")  # 기본 단타

                interval = "15" if mode == "단타" else "60"
                candles = get_candles(symbol, interval=interval, count=30)

                if not candles or len(candles) < 10:
                    print(f"⚠️ 캔들 부족: {symbol}")
                    continue

                # 목표가 설정
                expected_profit = data.get("expected_profit", 0.05)
                target_1 = round(entry_price * (1 + expected_profit), 2)
                target_2 = data.get("target_2")
                target_3 = data.get("target_3")

                print(f"🎯 목표가1: {target_1}, 목표가2: {target_2}, 목표가3: {target_3}")

                indicators = get_indicators(symbol, candles)

                # 매도 조건 판별
                if mode == "스윙":
                    signal = check_sell_signal_strategy_swing(data, candles, indicators)
                else:
                    signal = check_sell_signal_strategy1(data, candles, indicators)

                if signal:
                    print(f"✅ 매도 조건 충족: {symbol} - 이유: {signal}")

                    price = get_latest_price(symbol) or get_current_price(symbol)
                    if not price:
                        raise ValueError("체결가 조회 실패")

                    exit_type = "익절" if price >= entry_price else "손절"

                    for attempt in range(2):
                        try:
                            sell_market_order(symbol)
                            update_balance_after_sell(symbol, price, quantity)
                            remove_holding(symbol)
                            log_sell(symbol, price, f"전략1 매도 ({mode}) - {signal}")

                            profit = round((price - entry_price) * quantity)
                            balance_now = get_krw_balance()

                            notify_sell(
                                symbol=symbol,
                                strategy="1",
                                buy_price=entry_price,
                                sell_price=price,
                                profit=profit,
                                balance=balance_now,
                                exit_type=exit_type,
                                config=config
                            )

                            print(f"💸 매도 완료: {symbol} @ {price} ({exit_type}) / 수익: {profit}원")
                            break
                        except Exception as e:
                            print(f"⚠️ 매도 실패 [{attempt+1}/2]: {e}")
                            time.sleep(2)
                    else:
                        print(f"❌ 매도 완전 실패: {symbol} → 보유 유지")
                else:
                    print(f"⏳ 매도 조건 미충족: {symbol} ({mode})")

            except Exception as e:
                handle_error(e, location=f"sell_strategy1.py - {symbol}", config=config)

        save_holdings_to_file()
        print("📤 매도 전략1 완료 — holdings.json 저장됨")

    except Exception as e:
        handle_error(e, location="sell_strategy1.py - 전체", config=config)



