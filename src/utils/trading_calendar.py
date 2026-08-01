"""
A 股交易日历工具
基于 chinesecalendar 库判断中国法定假日和调休，对库未覆盖的年份做 fallback
"""

from datetime import date, timedelta
from typing import Optional

import chinese_calendar

from src.utils.logger import get_logger

logger = get_logger(__name__)


def is_trading_day(d: date) -> bool:
    """
    判断某日是否为 A 股交易日
    交易日 = 工作日（含调休补班）且非法定假日
    """
    try:
        return chinese_calendar.is_workday(d)
    except NotImplementedError:
        # 库未覆盖的年份：fallback 到周末判断
        logger.debug("chinese_calendar 未覆盖 %s，使用周末判断", d)
        return d.weekday() < 5


def is_holiday(d: date) -> bool:
    """判断某日是否为法定假日（不含普通周末）"""
    try:
        is_hol, name = chinese_calendar.get_holiday_detail(d)
        return is_hol and name is not None
    except NotImplementedError:
        return False


def get_holiday_name(d: date) -> Optional[str]:
    """
    获取法定假日名称（如 'National Day'、'New Year\\'s Day'）
    普通周末返回 None，非假日返回 None
    """
    try:
        is_hol, name = chinese_calendar.get_holiday_detail(d)
        if is_hol and name is not None:
            return name
        return None
    except NotImplementedError:
        return None


def get_non_trading_reason(d: date) -> Optional[str]:
    """
    获取非交易日原因描述
    返回 None 表示是交易日
    """
    if is_trading_day(d):
        return None

    hol_name = get_holiday_name(d)
    if hol_name:
        return f"休市（{hol_name}）"

    if d.weekday() >= 5:
        return "周末休市"

    return "非交易日"


def get_trading_days(start: date, end: date) -> list[date]:
    """获取 [start, end] 范围内的所有交易日"""
    result = []
    current = start
    while current <= end:
        if is_trading_day(current):
            result.append(current)
        current += timedelta(days=1)
    return result


def count_trading_days(start: date, end: date) -> int:
    """统计 [start, end] 范围内的交易日数量"""
    return len(get_trading_days(start, end))


def get_recent_trading_day(d: date = None) -> date:
    """
    获取最近的交易日（含当天）
    如果今天是交易日就返回今天，否则往前找最近的交易日
    """
    if d is None:
        d = date.today()

    # 往前找，最多找 30 天
    for i in range(30):
        check = d - timedelta(days=i)
        if is_trading_day(check):
            return check

    logger.warning("最近30天无交易日，返回 %s", d)
    return d


def get_next_trading_day(d: date = None) -> date:
    """
    获取下一个交易日（不含当天）
    """
    if d is None:
        d = date.today()

    for i in range(1, 30):
        check = d + timedelta(days=i)
        if is_trading_day(check):
            return check

    logger.warning("未来30天无交易日，返回 %s", d + timedelta(days=1))
    return d + timedelta(days=1)


if __name__ == "__main__":
    # 自测
    today = date.today()
    print(f"今天: {today}")
    print(f"  是否交易日: {is_trading_day(today)}")
    print(f"  非交易日原因: {get_non_trading_reason(today)}")
    print(f"  最近交易日: {get_recent_trading_day(today)}")
    print(f"  下一交易日: {get_next_trading_day(today)}")
    print()

    # 测几个特殊日
    tests = [
        date(2025, 1, 1),   # 元旦
        date(2025, 2, 17),  # 春节
        date(2025, 5, 1),   # 劳动节
        date(2025, 10, 1),  # 国庆
        date(2025, 3, 17),  # 普通周一
        date(2025, 3, 16),  # 普通周日
    ]
    for d in tests:
        reason = get_non_trading_reason(d)
        status = "交易日" if reason is None else reason
        print(f"  {d} ({d.strftime('%a')}): {status}")
