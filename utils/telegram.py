import requests

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
