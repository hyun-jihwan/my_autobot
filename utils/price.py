# utils/price.py

import requests

def get_current_price(symbol):

    url = f"https://api.upbit.com/v1/ticker?markets={symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        return data[0]["trade_price"]
    except Exception as e:
        print(f"❌ 실시간 가격 조회 실패: {symbol} → {e}")
        return 0
