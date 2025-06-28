import requests
from utils.send_telegram import send_telegram


def send_telegram(message, config):
    """
    텔레그램으로 메시지를 전송합니다.
    """
    try:
        token = config.get("tele_token")
        chat_id = config.get("tele_chat_id")
        if not token or not chat_id:
            print("텔레그램 설정이 없습니다.")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message
        }

        response = requests.post(url, data=data)
        if response.status_code != 200:
            print("텔레그램 전송 실패:", response.text)

    except Exception as e:
        print("텔레그램 전송 오류:", e)


def notify_buy(symbol, total_amount, balance, strategy_num, swing_or_scalp, expected_profit_pct, target_profit_pct, config):
    msg = (
        f"📥 [매수 체결]\n"
        f"종목: {symbol}\n"
        f"매수총액: {total_amount:,} KRW\n"
        f"잔고: {balance:,} KRW\n"
        f"전략: {strategy_num} ({swing_or_scalp})\n"
        f"예상수익률: {expected_profit_pct}%\n"
        f"목표수익률: {target_profit_pct}%"
    )
    send_telegram(msg, config)

def notify_transition(symbol, from_strategy, to_strategy, success=True, exit_type=None, config=None):
    if success:
        status = "성공"
    else:
        status = f"실패 ({exit_type})" if exit_type else "실패"
    message = f"🔄 {symbol} - 전략 {from_strategy} → {to_strategy} 전환 {status}"
    send_telegram(message, config)


def notify_switch(old_symbol, new_symbol=None, success=True, exit_type="익절", config=None):
    if success and new_symbol:
        message = f"🔁 {old_symbol} → {new_symbol} {exit_type} 후 갈아타기 완료"
    else:
        message = f"❌ {old_symbol} 갈아타기 실패, {exit_type} 후 청산"
    send_telegram(message, config)


def notify_sell(symbol, strategy, buy_price, sell_price, profit, balance, config=None):
    result_type = "익절" if profit >= 0 else "손절"
    profit_str = f"+{profit:,.0f}원" if profit >= 0 else f"{profit:,.0f}원"

    message = (
        f"💸 {symbol} (전략 {strategy}) 매도 완료\n"
        f"매수가: {buy_price:,.0f}\n"
        f"매도가: {sell_price:,.0f}\n"
        f"결과: {result_type}\n"
        f"총손익: {profit_str}\n"
        f"현재잔고: {balance:,.0f}원"
    )
    send_telegram(message, config)

def notify_error(location, error_message, config=None):
    message = f"❌ 오류 발생 ({location})\n{error_message[:3500]}"  # 텔레그램 메시지 길이 제한 대응
    send_telegram(message, config)

def notify_bot_start(config):
    message = "✅ [알림] 매매봇이 실행되었습니다."
    send_telegram(message, config)

def notify_bot_stop(config, reason="정상 종료"):
    message = f"🛑 [알림] 매매봇이 종료되었습니다.\n사유: {reason}"
    send_telegram(message, config)
