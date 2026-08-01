import time
from datetime import datetime, timedelta

import efinance as ef
import pandas as pd
import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_a_share_daily_kline(
    symbol: str,
    start_date: str = "",
    end_date: str = "",
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    使用 efinance 获取 A 股日线数据
    symbol: 纯数字代码，如 "000001"
    start_date / end_date: "20250101" 格式
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("获取K线: symbol=%s, start=%s, end=%s, attempt=%d",
                         symbol, start_date, end_date, attempt)
            kwargs = dict(stock_codes=symbol)
            if start_date:
                kwargs["beg"] = start_date
            if end_date:
                kwargs["end"] = end_date

            df = ef.stock.get_quote_history(**kwargs)

            if df is None or df.empty:
                return pd.DataFrame()

            # efinance 返回中文列名，统一映射
            rename_map = {
                "日期": "time",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
            }
            df = df.rename(columns=rename_map)

            # 只保留必需列
            required_cols = ["time", "open", "high", "low", "close", "volume"]
            df = df[[c for c in required_cols if c in df.columns]]

            # 时间格式统一
            df["time"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")

            # 数值类型保证
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna(subset=["time", "close"])

            # 【关键修复】确保按时间升序排列（efinance 默认是降序，图表必须升序）
            df = df.sort_values("time").reset_index(drop=True)

            return df

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ) as e:
            if attempt < max_retries:
                wait = attempt * 2
                time.sleep(wait)
            else:
                raise ConnectionError(
                    f"efinance 获取 {symbol} 日线失败，已重试 {max_retries} 次。"
                    f"原始错误：{e}"
                ) from e
        except Exception as e:
            if attempt < max_retries:
                wait = attempt * 2
                time.sleep(wait)
            else:
                raise ConnectionError(
                    f"efinance 获取 {symbol} 日线失败。原始错误：{e}"
                ) from e


def default_date_range(days: int = 365):
    """返回最近 N 天的日期字符串，格式 20250101"""
    end = datetime.now()
    start = end - timedelta(days=days)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
