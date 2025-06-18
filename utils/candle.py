import requests
import datetime

#def get_candles(symbol, interval="15", count=30):
def get_candles(symbol, interval="1", count=16):
    """
    업비트 캔들 데이터 조회
    interval:
      - "1", "3", "5", "15", "30", "60", "240" → 분봉
      - "day" → 일봉
      - "week" → 주봉
      - "month" → 월봉
    """
    #테스트 시작
    if symbol == "KRW-TEST":
        return [
            {"opening_price": 100, "high_price": 105, "low_price": 98, "trade_price": 104, "candle_acc_trade_volume": 3000},
            {"opening_price": 104, "high_price": 106, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 2800},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 2500},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 2600},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 2700},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 2800},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 2900},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3000},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3100},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3200},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3300},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3400},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3500},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3600},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3700},
            {"opening_price": 104, "high_price": 105, "low_price": 103, "trade_price": 104, "candle_acc_trade_volume": 3800},
            {"opening_price": 104, "high_price": 104, "low_price": 100, "trade_price": 101, "candle_acc_trade_volume": 3900}  
        ]
    print(f"❌ {symbol} → 캔들 응답 실패 / 상태코드: 404")
    return []
    #테스트 끝

    if interval == "day":
        url = "https://api.upbit.com/v1/candles/days"
    elif interval == "week":
        url = "https://api.upbit.com/v1/candles/weeks"
    elif interval == "month":
        url = "https://api.upbit.com/v1/candles/months"
    else:
        url = f"https://api.upbit.com/v1/candles/minutes/{interval}"

    params = {"market": symbol, "count": count}
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ {symbol} → 캔들 응답 실패 / 상태코드: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ {symbol} → 요청 중 예외 발생: {e}")
        return []

def is_box_breakout(candles):
    """
    박스권 상단 재돌파 패턴 판별
    - 최근 5~10봉 동안 가격 변동폭이 ±1% 이내
    - 이후 양봉 돌파 + 거래량 1.5배 이상
    """
    if len(candles) < 12:
        return False

    recent = candles[2:12]  # 박스 분석용 구간
    prices = [c["trade_price"] for c in recent]
    max_price = max(prices)
    min_price = min(prices)

    box_range = (max_price - min_price) / min_price
    if box_range > 0.01:  # 박스폭 ±1% 이상이면 박스 아님
        return False

    current = candles[0]
    prev = candles[1]

    # 양봉 돌파 + 거래량 1.5배 이상
    if current["trade_price"] > max_price and current["opening_price"] < current["trade_price"]:
        if current["candle_acc_trade_volume"] > prev["candle_acc_trade_volume"] * 1.5:
            return True

    return False

def is_breakout_pullback(candles):
    """
    돌파 후 눌림 패턴 감지
    - 고점 돌파 후 눌림
    - 최근 봉 양봉
    - 거래량 전봉보다 1.2배 이상
    """
    if len(candles) < 6:
        return False

    prev_5 = candles[1:6]
    high = max(c["high_price"] for c in prev_5)
    low = min(c["low_price"] for c in prev_5)

    # 현재봉 조건
    current = candles[0]
    prev = candles[1]

    # 눌림 후 양봉 + 거래량 증가
    if current["trade_price"] > low and current["opening_price"] < current["trade_price"]:
        if current["candle_acc_trade_volume"] > prev["candle_acc_trade_volume"] * 1.2:
            return True
    return False

def is_v_rebound(candles):
    """
    V자 반등 패턴 감지
    - 큰 음봉 → 큰 양봉 (반전)
    - 양봉 거래량이 음봉보다 1.2배 이상
    """
    if len(candles) < 3:
        return False

    down = candles[2]
    up = candles[1]
    now = candles[0]

    # down = 긴 음봉, up = 긴 양봉
    down_range = down["opening_price"] - down["trade_price"]
    up_range = up["trade_price"] - up["opening_price"]

    if down_range <= 0 or up_range <= 0:
        return False

    if up_range < down_range * 0.8:
        return False  # 양봉이 충분히 크지 않음

    # 거래량 조건
    if up["candle_acc_trade_volume"] < down["candle_acc_trade_volume"] * 1.2:
        return False

    # 현재봉이 양봉 유지 중이면 V자 반등 확정
    if now["trade_price"] > now["opening_price"]:
        return True

    return False

def get_all_krw_symbols():
    url = "https://api.upbit.com/v1/market/all"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return [item['market'] for item in data if item['market'].startswith("KRW-")]
        else:
            print("❌ 심볼 목록 가져오기 실패")
            return []
    except Exception as e:
        print(f"❌ 심볼 요청 중 오류: {e}")
        return []

