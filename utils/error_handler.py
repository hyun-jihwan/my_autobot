from utils.telegram import notify_error
import traceback

def handle_error(e, location="알 수 없는 위치", config=None):
    """
    e: Exception 객체
    location: 어디서 발생했는지 (main.py 매수, sell_monitor.py 매도 등)
    config: 텔레그램 config 전달
    """
    error_message = f"{str(e)}\n\n{traceback.format_exc()}"
    notify_error(location, error_message, config)
    print(f"[ERROR] ({location}) {error_message}")
