"""
汇率数据采集模块
支持多数据源：国家外汇管理局(currency_boc_safe)、新浪(currency_boc_sina)
"""

import random
from datetime import date, datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_usd_cny_from_safe() -> pd.DataFrame:
    """
    从国家外汇管理局获取美元/人民币中间价历史数据
    数据来源: ak.currency_boc_safe()
    返回的美元列为100美元兑人民币中间价（如678.94），需除以100

    Returns:
        DataFrame with columns: date(datetime), usd_cny(float)
    """
    try:
        logger.info("从国家外汇管理局获取USD/CNY汇率历史")
        df = ak.currency_boc_safe()

        if df.empty:
            return pd.DataFrame()

        # 列名: 日期, 美元, 欧元, ...
        date_col = "日期"
        usd_col = "美元"

        if date_col not in df.columns or usd_col not in df.columns:
            logger.warning("currency_boc_safe 列名不匹配: %s", list(df.columns))
            return pd.DataFrame()

        result = df[[date_col, usd_col]].copy()
        result.columns = ["date", "usd_cny"]
        result["date"] = pd.to_datetime(result["date"])
        result["usd_cny"] = pd.to_numeric(result["usd_cny"], errors="coerce")
        # 外汇管理局返回的是100美元兑人民币(如678.94)，需除以100
        result["usd_cny"] = result["usd_cny"] / 100.0
        result = result.dropna()
        result = result.sort_values("date").reset_index(drop=True)

        logger.info("从外汇管理局获取到 %d 条汇率记录, 最新日期: %s",
                     len(result), result["date"].iloc[-1] if len(result) > 0 else "N/A")
        return result

    except Exception:
        logger.warning("从外汇管理局获取汇率失败", exc_info=True)
        return pd.DataFrame()


def get_usd_cny_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    获取美元/人民币历史汇率（优先使用外汇管理局数据，回退到新浪）

    使用 akshare 的 currency_boc_safe 接口（国家外汇管理局）
    回退到 currency_boc_sina 接口（新浪）
    """
    # 优先使用外汇管理局数据（更权威、更新）
    df = get_usd_cny_from_safe()

    if df.empty or len(df) < 100:
        logger.info("外汇管理局数据不足，尝试新浪数据源")
        try:
            # 使用新浪外汇数据
            df = ak.currency_boc_sina(symbol="美元")

            if df.empty:
                return pd.DataFrame()

            # 日期列可能是 '日期' 或 'date'
            date_col = None
            for col in ["日期", "date", "Date"]:
                if col in df.columns:
                    date_col = col
                    break

            if date_col is None:
                return pd.DataFrame()

            df[date_col] = pd.to_datetime(df[date_col])

            # 取中间价
            rate_col = None
            for col in ["中行折算价", "中间价", "折算价"]:
                if col in df.columns:
                    rate_col = col
                    break

            if rate_col is None and len(df.columns) >= 2:
                rate_col = df.columns[1]

            if rate_col is None:
                return pd.DataFrame()

            result = df[[date_col, rate_col]].copy()
            result[rate_col] = pd.to_numeric(result[rate_col], errors="coerce")
            result.columns = ["date", "usd_cny"]
            result = result.dropna()

            # akshare 返回的汇率是 x100 的（如 717.71 = 7.1771），需要除以100
            if result["usd_cny"].mean() > 100:
                result["usd_cny"] = result["usd_cny"] / 100.0

            logger.info("从新浪获取到 %d 条汇率记录", len(result))
            df = result
        except Exception:
            logger.warning("获取USD/CNY汇率失败", exc_info=True)
            return pd.DataFrame()

    # 过滤日期范围
    if start_date:
        df = df[df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["date"] <= pd.to_datetime(end_date)]

    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_usd_cny_latest() -> Optional[float]:
    """获取最新美元汇率"""
    df = get_usd_cny_history()
    if df.empty:
        return None
    return float(df["usd_cny"].iloc[-1])


def convert_to_usd(cny_value: float, rate: float) -> float:
    """人民币转美元"""
    return round(cny_value / rate, 4) if rate > 0 else 0


def generate_fake_exchange_rates(
    start_date: str = "2024-01-01",
    days: int = 400,
) -> list[dict]:
    """
    生成假的汇率数据（当真实数据源不可用时）
    以 7.2 为基准，模拟正常波动
    """
    logger.info("生成假汇率数据: start=%s, days=%d", start_date, days)

    random.seed(42)
    results = []
    base = date.fromisoformat(start_date)
    rate = 7.20

    for i in range(days):
        d = base + timedelta(days=i)
        # 随机游走
        rate += random.uniform(-0.02, 0.02)
        rate = max(6.8, min(7.5, rate))
        results.append({"date": d, "usd_cny": round(rate, 4)})

    return results


if __name__ == "__main__":
    df = get_usd_cny_history()
    print(f"获取到 {len(df)} 条汇率记录")
    if not df.empty:
        print(df.tail())
