"""
真实K线数据获取模块 —— 多数据源自动回退

优先级: Baostock > 新浪 > 腾讯 > 假数据
"""

from datetime import date, timedelta

import pandas as pd

from src.data.kline_fake import generate_fake_kline
from src.data.sources import get_real_kline
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_kline(
    symbol: str = "000001",
    start_date: str = "",
    end_date: str = "",
    days: int = 180,
) -> tuple[pd.DataFrame, str]:
    """
    获取K线数据（真实优先，自动回退到假数据）

    Args:
        symbol: 6位股票代码
        start_date/end_date: YYYYMMDD
        days: 默认天数

    Returns:
        (DataFrame, source_label) — source_label:
          'baostock' / 'sina' / 'tencent' / 'fake'
    """
    # 尝试获取真实数据
    df, source = get_real_kline(symbol, start_date, end_date, days)

    if not df.empty:
        label = f"真实数据 ({source})"
        logger.info("K线获取成功: %s, %d 条, 来源: %s", symbol, len(df), source)
        return df, label

    # 全部失败，使用假数据
    logger.warning("所有真实数据源失败，使用假数据: %s", symbol)
    df = generate_fake_kline(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )
    return df, "模拟数据 (真实接口全部失败)"
