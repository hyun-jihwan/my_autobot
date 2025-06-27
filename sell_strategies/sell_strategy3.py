import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from utils.candle import get_candles
from utils.trade import sell_market_order
from utils.balance import update_balance_after_sell, update_holding_field, remove_holding
from utils.log_utils import log_sell
from sell_strategies.sell_utils import get_indicators

def check_sell_signal_strategy3(holding, candles_dict):
    symbol = holding["symbol"]
    entry_price = holding["entry_price"]
    quantity = holding["quantity"]
    max_price = holding.get("max_price", entry_price)

    # ✅ 1분봉 30개 받아오기 (최근 30분)
    candles = candles_dict[symbol]
    if not candles or len(candles) < 5:
        print(f"⚠️ {symbol} → 1분봉 캔들 부족")
        return None

    indicators = get_indicators(symbol, candles)

    last_candle = candles[-1]
    last_close = last_candle["trade_price"]
    vwap = indicators.get("vwap")
    obv_reversal = indicators.get("obv_reversal")

    # ✅ 최고가 실시간 갱신
    if last_close > max_price:
        max_price = last_close
        holding["max_price"] = max_price
        update_holding_field(symbol, "max_price", max_price)
        print(f"📈 최고가 갱신됨: {symbol} → {max_price}")

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
    signal = check_sell_signal_strategy3(holding, candles_dict)
    if signal:
        symbol = holding["symbol"]
        quantity = holding["quantity"]
        last_price = candles_dict[symbol][-1]["trade_price"]

        print(f"🚨 전략3 매도 시그널 발생: {symbol} / 사유: {signal}")

        # ✅ 시장가 매도 실행
        sell_market_order(symbol)
        update_balance_after_sell(symbol, last_price, quantity)
        remove_holding(symbol)
        log_sell(symbol, last_price, f"전략3 매도: {signal}")
        return True
    return False


#테스트 시작
if __name__ == "__main__":
    print("🚀 [전략3 익절/손절 테스트 시작 - 테스트 전용 심볼: KRW-B]")

    from utils.balance import get_holdings
    from utils.candle import get_candles

    symbol = "KRW-B"
    holdings = get_holdings()

    if symbol not in holdings:
        print(f"⚠️ {symbol} → holdings.json에 보유 중이지 않음")
        exit()

    holding = holdings[symbol]
    if holding.get("source") != "strategy3":
        print(f"⏩ {symbol} → 전략3 포지션 아님, 테스트 종료")
        exit()

    print(f"\n🔍 {symbol} → 전략3 익절/손절 조건 평가 시작")

    candles = get_candles(symbol, interval="1", count=30)

    if not candles or len(candles) < 5:
        print(f"❌ 캔들 부족 → {symbol}")
        exit()

    candles_dict = {
        symbol: candles
    }

    result = evaluate_exit_strategy3(holding)

    if result:
        print(f"✅ 매도 처리 완료 → {symbol}")
    else:
        print(f"❌ 매도 조건 미충족 → {symbol}")

#테스트 종료
