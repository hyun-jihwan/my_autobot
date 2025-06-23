def get_top_gainer():
    # 🚀 실전에서는 업비트나 증권사 API에서 전일대비 상승률 기준으로 상위 1위 추출
    # 임시 예시
    return "KRW-TOP1"

#실전 시, 사용
#import requests

#def get_top_gainer():
#    url = "https://api.upbit.com/v1/market/all"
#    markets = requests.get(url).json()
#    krw_markets = [m["market"] for m in markets if m["market"].startswith("KRW-")]

    # 전일대비 상승률을 기준으로 상위 1위 종목 찾기
#    ticker_url = f"https://api.upbit.com/v1/ticker?markets={','.join(krw_markets)}"
#    data = requests.get(ticker_url).json()

#    sorted_data = sorted(data, key=lambda x: x["signed_change_rate"], reverse=True)
#    return sorted_data[0]["market"]
