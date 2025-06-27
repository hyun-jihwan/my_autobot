import time
import requests
import datetime

#def get_candles(symbol, interval="15", count=30, max_retries=3, retry_delay=1.0):
def get_candles(symbol, interval="1", count=30): #테스트용
    print(f"📊 get_candles 호출됨 → symbol: {symbol}, interval: {interval}, count: {count}")
    """
    업비트 캔들 데이터 조회
    interval:
      - "1", "3", "5", "15", "30", "60", "240" → 분봉
      - "day" → 일봉
      - "week" → 주봉
      - "month" → 월봉
    """
    #테스트 시작
    # ✅ 전략1 손절 테스트용 15분봉 캔들
    # ✅ 전략1 진입 테스트용 15분봉 (박스 돌파 상승 흐름)
    if symbol == "KRW-B" and interval == "15" and count == 30:
        return [
            *[
                {
                    "opening_price": 1030 + i,
                    "high_price": 1030 + i + 1,
                    "low_price": 1030 + i - 1,
                    "trade_price": 1030 + i,
                    "candle_acc_trade_volume": 1000 + (i * 10),
                    "timestamp": 300000 + i
                }
                for i in range(28)
            ],
            {
                "opening_price": 1085,  # 고점 찍고 시작
                "high_price": 1088,     # 트레일링 최고가
                "low_price": 1075,
                "trade_price": 1079,    # 트레일링 기준 0.8% 하락 → 익절 조건
                "candle_acc_trade_volume": 3500,
                "timestamp": 300028
            },
            {
                "opening_price": 1079,
                "high_price": 1080,
                "low_price": 1068,
                "trade_price": 1070,    # 트레일링 기준 1% 하락 → 전량 익절 트리거
                "candle_acc_trade_volume": 3800,
                "timestamp": 300029
            }
        ]

        return candles

    if symbol == "KRW-B" and interval == "1" and count == 1:
        return [
            {
                "opening_price": 1072,
                "high_price": 1075,
                "low_price": 1068,
                "trade_price": 1070,  # 💰 실제 익절 체결가 (trailing high = 1080, 0.7% 하락)
                "candle_acc_trade_volume": 1200,
                "timestamp": 400000
            }
        ]

        return candles

    print(f"❌ 캔들 응답 실패 → {symbol} / interval: {interval}")
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

    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=3)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ {symbol} → 캔들 응답 실패 / 상태코드: {response.status_code}")
        except Exception as e:
            print(f"⚠️ API 요청 실패: {e} / 재시도: {attempt+1}")
        attempt += 1
        time.sleep(retry_delay)

    print(f"❌ {symbol} → 모든 재시도 실패. 빈 리스트 반환")
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

#테스트 시작
# ✅ candle.py 맨 아래쪽에 테스트용 캔들 저장 함수 추가

def save_test_candles(symbol, candles, filepath="data/test_candles.json"):
    import json
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    all_data = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except:
                all_data = {}

    all_data[symbol] = candles
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"🕯 테스트 캔들 저장 완료 → {symbol}")
#테스트 끝
