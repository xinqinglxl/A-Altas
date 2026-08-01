"""
假K线数据生成器 —— 当真实数据源不可用时使用
生成模拟的真实股票走势，标注为 [模拟数据]
"""

import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.utils.logger import get_logger
from src.utils.trading_calendar import is_trading_day

logger = get_logger(__name__)


def generate_fake_kline(
    symbol: str = "000001",
    start_date: str = "",
    end_date: str = "",
    days: int = 180,
    base_price: float = 15.0,
    volatility: float = 0.02,
) -> pd.DataFrame:
    """
    生成模拟K线数据，走势具有一定的连贯性（几何布朗运动）

    Args:
        symbol: 股票代码，用于决定基础价格
        start_date/end_date: 日期范围，格式 YYYYMMDD
        days: 默认天数（start_date 为空时使用）
        base_price: 基础价格
        volatility: 日波动率
    """
    # 确定日期范围
    if start_date and end_date:
        s = date(int(start_date[:4]), int(start_date[4:6]), int(start_date[6:]))
        e = date(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:]))
    else:
        e = date.today()
        s = e - timedelta(days=days)

    # 根据股票代码微调基础价格，让不同股票看起来不一样
    code_num = int(symbol) if symbol.isdigit() else hash(symbol) % 100000
    rng = np.random.RandomState(code_num % 1000)
    base_price = 3.0 + (code_num % 100) * 0.8  # 3 ~ 83 之间

    # 生成交易日列表（剔除周末和法定假日，含调休补班）
    date_list = []
    current = s
    while current <= e:
        if is_trading_day(current):
            date_list.append(current)
        current += timedelta(days=1)

    n = len(date_list)
    if n == 0:
        logger.warning("假K线生成: 无交易日, symbol=%s", symbol)
        return pd.DataFrame()

    # 几何布朗运动生成价格序列
    mu = 0.0003  # 日均收益率（略微偏正）
    daily_ret = rng.normal(mu, volatility, n)
    price_path = base_price * np.exp(np.cumsum(daily_ret))

    records = []
    for i, d in enumerate(date_list):
        open_price = round(float(price_path[i]), 2)

        # 日内波动
        intraday_range = open_price * rng.uniform(0.005, 0.035)
        high_price = round(open_price + intraday_range * rng.uniform(0.3, 1.0), 2)
        low_price = round(open_price - intraday_range * rng.uniform(0.3, 1.0), 2)

        # close 不能超出 high/low
        close_price = round(
            low_price + (high_price - low_price) * rng.uniform(0.2, 0.8), 2
        )

        # OHLC 排序确保一致性
        prices = sorted(
            [open_price, high_price, low_price, close_price],
            reverse=True,
        )
        high_price, prices = prices[0], prices[1:]
        low_price, prices = prices[-1], prices[:-1]

        # 成交量（对数正态分布）
        volume = int(10 ** rng.uniform(7.0, 8.5))

        records.append(
            {
                "time": d.strftime("%Y-%m-%d"),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        )

    df = pd.DataFrame(records)

    logger.info(
        "假K线生成: symbol=%s, %d 条, 价格范围 %.2f-%.2f",
        symbol,
        len(df),
        df["close"].min(),
        df["close"].max(),
    )

    return df
