import pandas as pd

def calculate_indicators(candles):
    if len(candles) < 200:
        return {}  # ⚠️ 지표 계산 불가 → 빈 결과 반환


    df = pd.DataFrame(candles)

    # ✅ 표준 컬럼으로 변환
    df = df.rename(columns={
        "trade_price": "close",
        "opening_price": "open",
        "high_price": "high",
        "low_price": "low",
        "candle_acc_trade_volume": "volume"
    })

    # ✅ 혹시라도 누락된 컬럼 보정
    for col in ["close", "open", "high", "low", "volume"]:
        if col not in df.columns:
            df[col] = 0  # 또는 df["close"], df["volume"] 같은 fallback 가능


    # ✅ 정렬 (과거 → 현재 순서)
    df = df[::-1].reset_index(drop=True)

    signals = {}


    # ✅ 1. RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs))
    signals["RSI"] = rsi.iloc[-1] > 50 and rsi.iloc[-1] > rsi.iloc[-2]
    signals["RSI_VALUE"] = round(rsi.iloc[-1], 2) if not rsi.isna().iloc[-1] else None


    # ✅ 2. MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    signals["MACD"] = hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2]
    signals["MACD_HIST"] = hist.iloc[-1] if not hist.isna().iloc[-1] else None

    # ✅ 3. MA (7/200)
    ma7 = df["close"].rolling(window=7).mean()
    ma200 = df["close"].rolling(window=200).mean()
    signals["MA"] = ma7.iloc[-1] > ma200.iloc[-1] if not ma200.isna().iloc[-1] else False

    # ✅ 4. CCI
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    ma = typical_price.rolling(20).mean()
    md = typical_price.rolling(20).apply(lambda x: abs(x - x.mean()).mean())
    cci = (typical_price - ma) / (0.015 * md.replace(0, 0.001))
    signals["CCI"] = cci.iloc[-1] >= 80 if not cci.isna().iloc[-1] else False

    # ✅ 5. OBV
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i - 1]:
            obv.append(obv[-1] + df["volume"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
            obv.append(obv[-1] - df["volume"].iloc[i])
        else:
            obv.append(obv[-1])
    df["obv"] = obv
    signals["OBV"] = obv[-1] > obv[-2]
    signals["OBV_SLOPE"] = df["obv"].diff().mean() > 0

    # ✅ 6. Bollinger Band
    mbb = df["close"].rolling(20).mean()
    signals["BOLL"] = df["close"].iloc[-1] > mbb.iloc[-1] if not mbb.isna().iloc[-1] else False

    return signals

