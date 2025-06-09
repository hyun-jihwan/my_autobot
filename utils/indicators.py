import pandas as pd

def calculate_indicators(candles):
    df = pd.DataFrame(candles)
    df = df.rename(columns={
        "trade_price": "close",
        "opening_price": "open",
        "high_price": "high",
        "low_price": "low",
        "candle_acc_trade_volume": "volume"
    })
    df = df[::-1].reset_index(drop=True)  # 오름차순 정렬

    signals = {}

    # 1. RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    signals["RSI"] = rsi.iloc[-1] > 50 and rsi.iloc[-1] > rsi.iloc[-2]

    # 2. MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    signals["MACD"] = hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2]

    # 3. MA(7/200)
    ma7 = df["close"].rolling(window=7).mean()
    ma200 = df["close"].rolling(window=200).mean()
    signals["MA"] = ma7.iloc[-1] > ma200.iloc[-1]

    # 4. CCI
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    ma = typical_price.rolling(20).mean()
    md = typical_price.rolling(20).apply(lambda x: abs(x - x.mean()).mean())
    cci = (typical_price - ma) / (0.015 * md)
    signals["CCI"] = cci.iloc[-1] >= 80  # 확정 기준

    # 5. OBV
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i - 1]:
            obv.append(obv[-1] + df["volume"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i - 1]:
            obv.append(obv[-1] - df["volume"].iloc[i])
        else:
            obv.append(obv[-1])
    signals["OBV"] = obv[-1] > obv[-2]

    # 6. Bollinger Band
    mbb = df["close"].rolling(20).mean()
    signals["BOLL"] = df["close"].iloc[-1] > mbb.iloc[-1]

    return signals
