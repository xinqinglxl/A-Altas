"""
行情扫描引擎 —— 批量获取K线 + 技术条件筛选

支持条件:
  - N连阳: 最近N天连续收盘>开盘
  - N连阴: 最近N天连续收盘<开盘
  - 单日涨幅>X%: 最近一日涨幅超过阈值
  - 单日跌幅>X%: 最近一日跌幅超过阈值
  - 均线多头排列: MA5 > MA10 > MA20 > MA30
  - MA金叉: 短期均线上穿长期均线
  - 放量上涨: 当日成交量 > N日均量的M倍 且 涨幅>0
  - N日新高: 收盘价为最近N日最高
  - 涨跌幅排名: 按涨幅排序取TOP
"""

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

import pandas as pd

from src.data.db import StockBasic
from src.data.sources import get_real_kline
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── 条件注册表 ──

@dataclass
class ScanCondition:
    """扫描条件定义"""
    id: str                        # 唯一标识
    name: str                      # 中文名称
    description: str               # 简短说明
    params: dict = field(default_factory=dict)  # 参数定义 {param_name: (type, default, label)}
    check: Callable = lambda df, **kw: True  # 检查函数


def _cond_n_yang(df: pd.DataFrame, n: int = 2) -> bool:
    """N连阳：最近N天收盘>开盘"""
    if len(df) < n:
        return False
    recent = df.tail(n)
    return all(recent["close"].values > recent["open"].values)


def _cond_n_yin(df: pd.DataFrame, n: int = 2) -> bool:
    """N连阴：最近N天收盘<开盘"""
    if len(df) < n:
        return False
    recent = df.tail(n)
    return all(recent["close"].values < recent["open"].values)


def _cond_daily_gain(df: pd.DataFrame, x: float = 3.0) -> bool:
    """单日涨幅>X%"""
    if len(df) < 2:
        return False
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    if yesterday["close"] == 0:
        return False
    pct = (today["close"] - yesterday["close"]) / yesterday["close"] * 100
    return pct > x


def _cond_daily_drop(df: pd.DataFrame, x: float = 3.0) -> bool:
    """单日跌幅>X%"""
    if len(df) < 2:
        return False
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    if yesterday["close"] == 0:
        return False
    pct = (today["close"] - yesterday["close"]) / yesterday["close"] * 100
    return pct < -x


def _calc_ma(df: pd.DataFrame, n: int) -> pd.Series:
    """计算MA"""
    return df["close"].rolling(window=n).mean()


def _cond_ma_bullish(df: pd.DataFrame, short: int = 5, mid: int = 10, long: int = 30) -> bool:
    """均线多头排列 MA(short) > MA(mid) > MA(long)"""
    if len(df) < long:
        return False
    ma_s = _calc_ma(df, short)
    ma_m = _calc_ma(df, mid)
    ma_l = _calc_ma(df, long)
    latest = len(df) - 1
    if pd.isna(ma_s.iloc[latest]) or pd.isna(ma_m.iloc[latest]) or pd.isna(ma_l.iloc[latest]):
        return False
    return ma_s.iloc[latest] > ma_m.iloc[latest] > ma_l.iloc[latest]


def _cond_ma_golden_cross(df: pd.DataFrame, short: int = 5, long: int = 15) -> bool:
    """MA金叉：短期均线在今日/昨日上穿长期均线"""
    if len(df) < long + 1:
        return False
    ma_s = _calc_ma(df, short)
    ma_l = _calc_ma(df, long)
    idx = len(df) - 1
    if pd.isna(ma_s.iloc[idx]) or pd.isna(ma_l.iloc[idx]):
        return False
    if pd.isna(ma_s.iloc[idx - 1]) or pd.isna(ma_l.iloc[idx - 1]):
        return False
    # 昨天短期 <= 长期，今天短期 > 长期 = 金叉
    return (ma_s.iloc[idx - 1] <= ma_l.iloc[idx - 1] and
            ma_s.iloc[idx] > ma_l.iloc[idx])


def _cond_volume_breakout(df: pd.DataFrame, vol_days: int = 20, multiple: float = 1.5) -> bool:
    """放量：今日成交量 > 过去N日均量的M倍"""
    if len(df) < vol_days + 1:
        return False
    today_vol = df.iloc[-1]["volume"]
    avg_vol = df["volume"].iloc[-(vol_days + 1):-1].mean()
    if avg_vol == 0:
        return False
    # 同时要求放量上涨
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        if yesterday["close"] > 0:
            pct = (df.iloc[-1]["close"] - yesterday["close"]) / yesterday["close"] * 100
            return today_vol > avg_vol * multiple and pct > 0
    return today_vol > avg_vol * multiple


def _cond_n_day_high(df: pd.DataFrame, n: int = 20) -> bool:
    """N日新高：收盘价为最近N日最高"""
    if len(df) < n:
        return False
    recent = df.tail(n)
    return df.iloc[-1]["close"] >= recent["close"].max()


def _cond_turnover_active(df: pd.DataFrame, min_turn: float = 3.0) -> bool:
    """换手率活跃（需要turn数据，Baostock日K提供此字段）"""
    # Baostock 日K数据有 turn 字段（换手率）
    if "turn" not in df.columns:
        return True  # 无数据则不过滤
    if len(df) < 1:
        return False
    return df.iloc[-1]["turn"] > min_turn


# ── 注册所有条件 ──

ALL_CONDITIONS: list[ScanCondition] = [
    ScanCondition(
        id="n_yang", name="N连阳", description="最近N天连续收阳线",
        params={"n": (int, 2, "连续阳线天数")},
        check=_cond_n_yang,
    ),
    ScanCondition(
        id="n_yin", name="N连阴", description="最近N天连续收阴线",
        params={"n": (int, 2, "连续阴线天数")},
        check=_cond_n_yin,
    ),
    ScanCondition(
        id="daily_gain", name="单日涨幅>X%", description="最新日涨幅超过阈值",
        params={"x": (float, 3.0, "涨幅阈值(%)")},
        check=_cond_daily_gain,
    ),
    ScanCondition(
        id="daily_drop", name="单日跌幅>X%", description="最新日跌幅超过阈值",
        params={"x": (float, 3.0, "跌幅阈值(%)")},
        check=_cond_daily_drop,
    ),
    ScanCondition(
        id="ma_bullish", name="均线多头排列", description="MA5 > MA10 > MA30",
        params={
            "short": (int, 5, "短期均线"),
            "mid": (int, 10, "中期均线"),
            "long": (int, 30, "长期均线"),
        },
        check=_cond_ma_bullish,
    ),
    ScanCondition(
        id="ma_golden_cross", name="均线金叉", description="短期均线上穿长期均线",
        params={
            "short": (int, 5, "短期均线"),
            "long": (int, 15, "长期均线"),
        },
        check=_cond_ma_golden_cross,
    ),
    ScanCondition(
        id="volume_breakout", name="放量上涨", description="成交量放大 + 当日上涨",
        params={
            "vol_days": (int, 20, "均量周期"),
            "multiple": (float, 1.5, "放量倍数"),
        },
        check=_cond_volume_breakout,
    ),
    ScanCondition(
        id="n_day_high", name="N日新高", description="收盘价为最近N日最高",
        params={"n": (int, 20, "新高天数")},
        check=_cond_n_day_high,
    ),
]

# 条件名称 → 对象映射
CONDITION_MAP = {c.id: c for c in ALL_CONDITIONS}


def _enrich_with_stock_info(result: dict) -> dict:
    """从数据库填充股票基础信息"""
    try:
        stock = StockBasic.get_or_none(StockBasic.code == result["code"])
        if stock:
            result["name"] = stock.name
            result["sector"] = stock.sector or ""
            result["wuxing"] = stock.wuxing or ""
    except Exception:
        result["name"] = result["code"]
        result["sector"] = ""
        result["wuxing"] = ""
    return result


# ── 批量扫描 ──

def scan_market(
    codes: list[str],
    conditions: list[str],
    cond_params: Optional[dict] = None,
    lookback_days: int = 90,
) -> list[dict]:
    """
    批量扫描市场，按条件筛选股票。

    Args:
        codes: 股票代码列表
        conditions: 条件ID列表，如 ['n_yang', 'daily_gain']
        cond_params: 条件参数覆盖，如 {'n_yang': {'n': 3}, 'daily_gain': {'x': 5.0}}
        lookback_days: K线回溯天数

    Returns:
        匹配的股票列表，每项包含:
        {code, name, sector, wuxing, price, change_pct, volume,
         matched_conditions, ma_values, source}
    """
    if cond_params is None:
        cond_params = {}

    results = []
    total = len(codes)

    for i, code in enumerate(codes):
        # 获取K线
        df, source = get_real_kline(code, days=lookback_days)
        if df.empty:
            continue

        # 确保数据按时间排序
        if "time" in df.columns:
            df = df.sort_values("time").reset_index(drop=True)

        # 检查所有条件
        matched = []
        for cond_id in conditions:
            cond = CONDITION_MAP.get(cond_id)
            if cond is None:
                continue

            # 合并参数：默认值 + 用户覆盖
            params = {}
            for pname, (ptype, pdefault, _plabel) in cond.params.items():
                val = pdefault
                if cond_id in cond_params and pname in cond_params[cond_id]:
                    val = cond_params[cond_id][pname]
                params[pname] = val

            try:
                if cond.check(df, **params):
                    matched.append(cond.name)
            except Exception as e:
                logger.warning("条件检查异常: %s %s: %s", code, cond_id, e)

        if not matched:
            continue

        # 提取关键指标
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        price = last.get("close", 0)
        prev_close = prev.get("close", 0)
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        # 计算常用MA
        ma_values = {}
        for period in [5, 10, 15, 20, 30]:
            if len(df) >= period:
                ma_values[f"MA{period}"] = round(
                    float(df["close"].tail(period).mean()), 2
                )

        result = {
            "code": code,
            "name": code,
            "price": round(float(price), 2),
            "change_pct": round(float(change_pct), 2),
            "volume": int(last.get("volume", 0)),
            "matched_conditions": matched,
            "ma_values": ma_values,
            "source": source,
        }
        result = _enrich_with_stock_info(result)
        results.append(result)

        # 进度日志
        if (i + 1) % 10 == 0:
            logger.info("扫描进度: %d/%d, 匹配 %d", i + 1, total, len(results))

        # 请求间隔
        if i < total - 1:
            time.sleep(0.3)

    # 按涨跌幅排序
    results.sort(key=lambda x: -x["change_pct"])
    logger.info("扫描完成: %d 只股票, 匹配 %d 只", total, len(results))
    return results
