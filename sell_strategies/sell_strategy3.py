import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from utils.candle import get_candles
from utils.trade import sell_market_order
from utils.balance import update_balance_after_sell
from sell_strategies.sell_utils import get_indicators

def check_sell_signal_strategy3(holding):
    symbol = holding["symbol"]
    entry_price = holding["entry_price"]
    quantity = holding["quantity"]
    max_price = holding.get("max_price", entry_price)

    # ✅ 1분봉 30개 받아오기 (최근 30분)
    candles = get_candles(symbol, interval="1", count=30)
    if not candles or len(candles) < 5:
        print(f"⚠️ {symbol} → 1분봉 캔들 부족")
        return None

    indicators = get_indicators(candles)
    last_candle = candles[0]
    last_close = last_candle["trade_price"]
    vwap = indicators.get("vwap")
    obv_reversal = indicators.get("obv_reversal")

    # ✅ 손절 조건 (실시간 손절 감지)
    stop_loss_rate = 0.98  # 기본 -2%
    if holding.get("market_mode") == "약세장":
        stop_loss_rate = 0.985  # 약세장 -1.5%

    if last_close <= entry_price * stop_loss_rate:
        return "❌ 손절 조건 도달 → 강제 종료"

    # ✅ 트레일링 익절 조건
    if (
        last_close < vwap and        # VWAP 아래 이탈
        obv_reversal and            # OBV 하락 전환
        last_close < max_price * 0.995  # 최고가 대비 하락 (안전판)
    ):
        return "✅ 트레일링 익절 조건 충족 → 청산"

    return None


def evaluate_exit_strategy3(holding):
    signal = check_sell_signal_strategy3(holding)
    if signal:
        print(f"🚨 전략3 매도 시그널: {signal}")
        symbol = holding["symbol"]
        quantity = holding["quantity"]
        last_price = get_candles(symbol, interval="1", count=1)[0]["trade_price"]

        # ✅ 시장가 매도 실행
        sell_market_order(symbol)
        update_balance_after_sell(last_price * quantity)
        return True
    return False
