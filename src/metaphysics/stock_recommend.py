"""
股票买入推荐评估模块。
综合技术面和玄学面，对扫描出的股票给出买入推荐等级和详细理由。

推荐维度：
- 技术面（40分）：连阳、均线多头、金叉、放量、涨幅方向
- 玄学面（60分）：股票五行 vs 用户日主 / 喜用神 / 当日日柱
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.metaphysics.bazi import BaziResult, GAN_WUXING, WUXING_SHENG, WUXING_KE, get_day_gan_zhi
from src.metaphysics.wuxing import get_sector_wuxing, wuxing_match_score
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StockRecommendation:
    """股票推荐评估结果"""
    code: str
    name: str
    total_score: int              # 0-100 综合评分
    level: str                    # 推荐等级
    emoji: str                    # 对应 emoji
    tech_score: int               # 技术面得分 0-40
    meta_score: int               # 玄学面得分 0-60
    tech_reasons: list[str] = field(default_factory=list)
    meta_reasons: list[str] = field(default_factory=list)
    all_reasons: list[str] = field(default_factory=list)


def evaluate_stock(
    stock_code: str,
    stock_name: str,
    stock_wuxing: Optional[str],
    stock_sector: Optional[str],
    matched_conditions: list[str],
    change_pct: Optional[float],
    volume: Optional[int],
    user_bazi: Optional[BaziResult],
    today: Optional[date] = None,
) -> StockRecommendation:
    """
    综合评估一只股票是否推荐买入。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        stock_wuxing: 股票五行属性（优先使用DB中存的值）
        stock_sector: 股票所属板块
        matched_conditions: 触发匹配的技术条件列表
        change_pct: 涨跌幅(%)
        volume: 成交量
        user_bazi: 用户八字，None 时玄学面得 0
        today: 评估日期，默认今天

    Returns:
        StockRecommendation 对象
    """
    if today is None:
        today = date.today()

    tech_score, tech_reasons = _evaluate_technical(matched_conditions, change_pct, volume)
    meta_score, meta_reasons = _evaluate_metaphysics(
        stock_wuxing, stock_sector, user_bazi, today, stock_name
    )

    total = tech_score + meta_score
    all_reasons = tech_reasons + meta_reasons

    # 确定等级和 emoji
    if total >= 75:
        level = "强烈推荐"
        emoji = "😍"
    elif total >= 60:
        level = "推荐"
        emoji = "😊"
    elif total >= 45:
        level = "中性"
        emoji = "😐"
    elif total >= 30:
        level = "谨慎"
        emoji = "😟"
    else:
        level = "回避"
        emoji = "😡"

    return StockRecommendation(
        code=stock_code,
        name=stock_name,
        total_score=total,
        level=level,
        emoji=emoji,
        tech_score=tech_score,
        tech_reasons=tech_reasons,
        meta_score=meta_score,
        meta_reasons=meta_reasons,
        all_reasons=all_reasons,
    )


def _evaluate_technical(
    matched_conditions: list[str],
    change_pct: Optional[float],
    volume: Optional[int],
) -> tuple[int, list[str]]:
    """技术面评分 0-40"""
    score = 15  # 能出现在扫描结果中说明已有一定技术面基础
    reasons = []

    cond_text = " ".join(matched_conditions).lower()

    if "连阳" in cond_text:
        score += 10
        reasons.append("出现连续阳线，短期多头强势")
    if "多头排列" in cond_text:
        score += 10
        reasons.append("均线呈多头排列，趋势向上")
    if "金叉" in cond_text:
        score += 8
        reasons.append("均线金叉信号，技术面转多")
    if "放量" in cond_text:
        score += 7
        reasons.append("成交量放大，资金介入明显")
    if "新高" in cond_text:
        score += 5
        reasons.append("创近期新高，突破阻力位")

    if change_pct is not None:
        if change_pct > 0:
            score += min(int(change_pct), 5)
            if change_pct > 3:
                reasons.append(f"当日涨幅 {change_pct:.1f}%，走势强劲")
        else:
            score -= min(int(abs(change_pct)), 10)
            if change_pct < -3:
                reasons.append(f"当日跌幅 {abs(change_pct):.1f}%，短期承压")

    # 成交量参考
    if volume is not None and volume > 0:
        if volume > 100_000_000:
            reasons.append("成交量活跃(>1亿手)，流动性充裕")
        elif volume < 10_000_000:
            reasons.append("成交量偏低，流动性一般")

    score = max(0, min(40, score))
    return score, reasons


def _evaluate_metaphysics(
    stock_wuxing: Optional[str],
    stock_sector: Optional[str],
    user_bazi: Optional[BaziResult],
    today: date,
    stock_name: str,
) -> tuple[int, list[str]]:
    """玄学面评分 0-60"""
    reasons = []

    if user_bazi is None:
        return 0, ["未设置用户八字，无法进行玄学评估"]

    # 确定股票五行：优先进DB存的值，其次从板块推导
    wx = stock_wuxing
    if not wx and stock_sector:
        wx = get_sector_wuxing(stock_sector)

    if not wx:
        return 10, [f"无法确定{stock_name}的五行属性，暂时给基础分"]

    score = 20  # 基础分

    # 1. 股票五行 vs 用户日主五行（0-20分）
    dm = user_bazi.day_master
    if dm:
        relation_score = wuxing_match_score(dm, wx)
        meta_points = int((relation_score - 50) * 0.4)  # 映射到 -20 ~ +20
        score += meta_points

        if relation_score >= 75:
            reasons.append(f"股票五行「{wx}」与日主「{dm}」比和或相生，契合度高")
        elif relation_score >= 50:
            reasons.append(f"股票五行「{wx}」与日主「{dm}」关系中性")
        else:
            reasons.append(f"股票五行「{wx}」与日主「{dm}」相克，契合度低")

    # 2. 股票五行 vs 用户喜用神（0-20分）
    if wx in user_bazi.xi_shen:
        score += 20
        reasons.append(f"股票五行「{wx}」是喜用神，能量加持")
    elif wx in user_bazi.ji_shen:
        score -= 15
        reasons.append(f"股票五行「{wx}」是忌神，应谨慎对待")

    # 3. 股票五行 vs 当日日柱五行（0-20分）
    try:
        day_gan, _ = get_day_gan_zhi(today)
        day_wx = GAN_WUXING.get(day_gan)

        if day_wx:
            if day_wx == wx:
                score += 5
                reasons.append(f"当日五行「{day_wx}」与股票五行比和")
            elif WUXING_SHENG.get(day_wx) == wx:
                score += 10
                reasons.append(f"当日五行「{day_wx}」生股票五行「{wx}」，时运有利")
            elif WUXING_SHENG.get(wx) == day_wx:
                score += 3
                reasons.append(f"股票五行「{wx}」生当日五行「{day_wx}」，能量外泄")
            elif WUXING_KE.get(day_wx) == wx:
                score -= 10
                reasons.append(f"当日五行「{day_wx}」克股票五行「{wx}」，时运不利")
    except Exception:
        logger.debug("获取当日日柱失败", exc_info=True)

    # 4. 板块五行提示
    if stock_sector and wx:
        reasons.append(f"所属板块: {stock_sector}（五行: {wx}）")

    score = max(0, min(60, score))
    return score, reasons
