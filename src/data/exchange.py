"""
汇率数据采集模块
"""

from datetime import date, datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd


def get_usd_cny_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    获取美元/人民币历史汇率

    使用 akshare 的 currency_boc_sina 接口
    """
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

        # 过滤日期范围
        if start_date:
            result = result[result["date"] >= pd.to_datetime(start_date)]
        if end_date:
            result = result[result["date"] <= pd.to_datetime(end_date)]

        result = result.sort_values("date").reset_index(drop=True)
        return result

    except Exception:
        return pd.DataFrame()


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
    import random

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
