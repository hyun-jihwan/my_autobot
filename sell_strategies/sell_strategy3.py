import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from utils.candle import get_candles
from utils.trade import sell_market_order
from utils.balance import update_balance_after_sell, update_holding_field, remove_holding, get_krw_balance
from utils.log_utils import log_sell
from sell_strategies.sell_utils import get_indicators
from utils.telegram import notify_sell, handle_error
from utils.google_sheet_logger import log_trade_to_sheet


def check_sell_signal_strategy3(holding, candles_dict):
    symbol = holding["symbol"]
    entry_price = holding["entry_price"]
    quantity = holding["quantity"]
    max_price = holding.get("max_price", entry_price)

    # ✅ 1분봉 30개 받아오기 (최근 30분)
    candles = candles_dict.get[symbol]
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


def evaluate_exit_strategy3(holding, candles_dict, config=None):
    try:
        symbol = holding["symbol"]
        entry_price = holding["entry_price"]
        quantity = holding["quantity"]
        signal = check_sell_signal_strategy3(holding, candles_dict)

        if signal:
            last_price = candles_dict[symbol][-1]["trade_price"]

            print(f"🚨 전략3 매도 시그널 발생: {symbol} / 사유: {signal}")

            # ✅ 시장가 매도
            sell_market_order(symbol)
            update_balance_after_sell(symbol, last_price, quantity)
            remove_holding(symbol)
            log_sell(symbol, last_price, f"전략3 매도: {signal}")

            profit = round((last_price - entry_price) * quantity)
            balance = get_krw_balance()

            # ✅ 매도 알림 발송
            notify_sell(
                symbol=symbol,
                strategy="3",
                buy_price=entry_price,
                sell_price=last_price,
                profit=profit,
                balance=balance,
                config=config
            )

            # ✅ 구글 시트 기록 (Raw_Data 구조)
            log_trade_to_sheet({
                "날짜": datetime.now().strftime("%Y-%m-%d"),
                "시간": datetime.now().strftime("%H:%M:%S"),
                "종목": symbol,
                "구분": "매도",
                "전략": "strategy3",
                "매수금액": round(entry_price * quantity, 2),
                "매도금액": round(last_price * quantity, 2),
                "수익률(%)": profit_rate,
                "수익금액": profit,
                "누적수익": 0,
                "실시간잔고": int(balance)
            })

            update_summary_sheets()

            print(f"✅ 전략3 매도 완료 및 알림 발송: {symbol} / 수익: {profit}원")
            return True

    except Exception as e:
        print(f"❌ 전략3 매도 처리 중 오류: {e}")
        if config:
            handle_error(e, location="sell_strategy3", config=config)

    return False

