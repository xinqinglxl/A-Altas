"""
天干地支择时模块
日柱计算、黄历信号、节气轮动
"""

from datetime import date, timedelta
from typing import Optional

from lunar_python import Lunar, Solar

from src.utils.logger import get_logger

from .bazi import GAN_WUXING, get_day_gan_zhi
from .wuxing import (
    WUXING_KE,
    WUXING_LIST,
    WUXING_SHENG,
    get_wuxing_compatible_sectors,
    get_wuxing_avoid_sectors,
)

logger = get_logger(__name__)


def get_daily_signal(target_date: Optional[date] = None) -> dict:
    """
    获取指定日期的玄学择时信号

    Returns:
        dict with keys:
            date, day_gan, day_zhi, day_wuxing,
            yi, ji, caishen, jieqi,
            trade_signal, recommended_wuxing, avoid_wuxing
    """
    if target_date is None:
        target_date = date.today()

    solar = Solar.fromYmd(target_date.year, target_date.month, target_date.day)
    lunar = Lunar.fromSolar(solar)
    eight_char = lunar.getEightChar()

    day_gan = str(eight_char.getDayGan())
    day_zhi = str(eight_char.getDayZhi())
    day_wuxing = GAN_WUXING.get(day_gan, "未知")

    yi = lunar.getDayYi()
    ji = lunar.getDayJi()
    caishen = lunar.getDayPositionCai()
    jieqi = lunar.getJieQi() or None

    # 择时信号判定
    trade_signal = _judge_trade_signal(day_wuxing, yi, ji)

    # 推荐/回避的五行
    recommended_wx = _recommend_wuxing(day_wuxing)
    avoid_wx = _avoid_wuxing(day_wuxing)

    result = {
        "date": target_date.isoformat(),
        "day_gan": day_gan,
        "day_zhi": day_zhi,
        "day_wuxing": day_wuxing,
        "yi": yi,
        "ji": ji,
        "caishen": caishen,
        "jieqi": jieqi,
        "trade_signal": trade_signal,
        "recommended_wuxing": recommended_wx,
        "avoid_wuxing": avoid_wx,
    }

    logger.info(
        "每日信号: %s | %s%s日 (%s) | 信号=%s | 宜=%s",
        target_date.isoformat(), day_gan, day_zhi, day_wuxing,
        trade_signal, recommended_wx,
    )
    return result


def _judge_trade_signal(day_wuxing: str, yi: list[str], ji: list[str]) -> str:
    """判断当日交易信号"""
    yi_text = " ".join(yi) if yi else ""
    ji_text = " ".join(ji) if ji else ""

    # 黄历宜忌关键词
    good_keywords = ["交易", "开市", "立券", "纳财"]
    bad_keywords = ["破土", "安葬", "行丧"]

    has_good = any(k in yi_text for k in good_keywords)
    has_bad = any(k in ji_text for k in bad_keywords)

    if has_good and not has_bad:
        return "宜买入"
    elif has_bad and not has_good:
        return "忌交易"
    else:
        return "宜观望"


def _recommend_wuxing(day_wuxing: str) -> list[str]:
    """根据日干五行推荐板块五行"""
    sheng = WUXING_SHENG.get(day_wuxing)  # 日干生的五行
    bei_sheng = None
    for k, v in WUXING_SHENG.items():
        if v == day_wuxing:
            bei_sheng = k
            break

    result = [day_wuxing]  # 比和
    if bei_sheng:
        result.append(bei_sheng)  # 生我的
    return result


def _avoid_wuxing(day_wuxing: str) -> list[str]:
    """根据日干五行回避板块五行"""
    avoid = WUXING_KE.get(day_wuxing)  # 我克的 → 泄力
    bei_ke = None
    for k, v in WUXING_KE.items():
        if v == day_wuxing:
            bei_ke = k
            break

    result = []
    if bei_ke:
        result.append(bei_ke)  # 克我的
    if avoid and avoid != day_wuxing:
        result.append(avoid)
    return result


def get_ganzhi_timing_score(
    day_wuxing: str,
    sector_wuxing: str,
    user_xi_shen: Optional[list[str]] = None,
) -> float:
    """
    天干地支择时打分 (0-100)

    综合日柱五行 + 用户喜用神
    """
    score = 50.0

    # 日干五行与板块五行关系
    if day_wuxing == sector_wuxing:
        score += 15  # 比和
    elif WUXING_SHENG.get(day_wuxing) == sector_wuxing:
        score += 10  # 日干生板块
    elif WUXING_SHENG.get(sector_wuxing) == day_wuxing:
        score += 20  # 板块生日干

    # 克的关系
    if WUXING_KE.get(day_wuxing) == sector_wuxing:
        score -= 10
    elif WUXING_KE.get(sector_wuxing) == day_wuxing:
        score -= 20

    # 用户喜用神加成
    if user_xi_shen and sector_wuxing in user_xi_shen:
        score += 15

    return max(0, min(100, score))


def get_jieqi_rotation(target_date: Optional[date] = None) -> Optional[dict]:
    """
    节气轮动信号
    检查当天是否是节气日，返回节气轮动建议
    """
    if target_date is None:
        target_date = date.today()

    solar = Solar.fromYmd(target_date.year, target_date.month, target_date.day)
    lunar = Lunar.fromSolar(solar)
    jieqi = lunar.getJieQi()

    if not jieqi:
        return None

    logger.info("节气轮动: %s → 推荐五行=%s", jieqi, [])

    # 节气板块轮动映射
    jieqi_sector_map = {
        "立春": ["木", "火"],
        "雨水": ["水", "木"],
        "惊蛰": ["火", "木"],
        "春分": ["木", "火"],
        "清明": ["木"],
        "谷雨": ["土", "木"],
        "立夏": ["火"],
        "小满": ["火", "土"],
        "芒种": ["火", "土"],
        "夏至": ["火"],
        "小暑": ["土", "火"],
        "大暑": ["土"],
        "立秋": ["金"],
        "处暑": ["金", "土"],
        "白露": ["金", "水"],
        "秋分": ["金"],
        "寒露": ["金", "土"],
        "霜降": ["土", "金"],
        "立冬": ["水"],
        "小雪": ["水", "木"],
        "大雪": ["水", "金"],
        "冬至": ["水"],
        "小寒": ["土", "水"],
        "大寒": ["土"],
    }

    recommended_wx = jieqi_sector_map.get(jieqi, [])
    sectors = []
    for wx in recommended_wx:
        sectors.extend(get_wuxing_compatible_sectors([wx]))

    return {
        "jieqi": jieqi,
        "date": target_date.isoformat(),
        "recommended_wuxing": recommended_wx,
        "sectors": sectors[:10],  # 最多10个
    }


def generate_daily_signals(
    start_date: date, days: int = 30
) -> list[dict]:
    """批量生成每日信号（用于日历热力图）"""
    logger.info("批量生成每日信号: start=%s, days=%d", start_date.isoformat(), days)
    signals = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        try:
            signal = get_daily_signal(d)
            signals.append(signal)
        except Exception:
            logger.warning("生成信号失败: %s", d.isoformat(), exc_info=True)
            continue
    logger.info("每日信号生成完成: 成功%d条", len(signals))
    return signals


if __name__ == "__main__":
    today = date.today()
    signal = get_daily_signal(today)
    print("=== 今日信号 ===")
    for k, v in signal.items():
        print(f"  {k}: {v}")

    jieqi = get_jieqi_rotation(today)
    if jieqi:
        print(f"\n今日节气: {jieqi['jieqi']}")
        print(f"推荐五行: {jieqi['recommended_wuxing']}")
        print(f"推荐板块: {jieqi['sectors']}")
