import pandas as pd


def resample_kline(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """
    将日线合成为 N 日K线
    period: 几根日K合成一根新K线
    """
    if df.empty:
        return df

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])

    ohlc_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    # 每 period 根日K合成一根
    df["group"] = range(len(df))
    df["group"] = df["group"] // period

    # 聚合
    df_custom = df.groupby("group").agg(ohlc_dict)

    # 取每组最后一根日K的时间
    time_map = df.groupby("group")["time"].last()
    df_custom["time"] = df_custom.index.map(time_map)

    df_custom = df_custom[["time", "open", "high", "low", "close", "volume"]]
    df_custom = df_custom.dropna(subset=["time"])

    df_custom["time"] = df_custom["time"].dt.strftime("%Y-%m-%d")

    return df_custom
