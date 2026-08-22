"""
止损止盈计算模块。
根据买入价 + 当日运势评分 + 股票五行关系，计算符合运势的止损点和止盈点。

核心逻辑：
- 运势好时放宽止盈目标、正常止损（让利润奔跑）
- 运势差时收紧止损、降低止盈预期（保住本金，见好就收）
- 股票五行与用户八字关系也会微调止盈止损幅度
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.metaphysics.bazi import BaziResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StopProfitResult:
    """止损止盈计算结果"""
    entry_price: float           # 买入价
    stop_loss: float             # 止损价
    take_profit: float            # 止盈价
    stop_loss_pct: float          # 止损百分比（负数）
    take_profit_pct: float        # 止盈百分比（正数）
    fortune_score: int            # 当日运势评分 0-100
    fortune_level: str            # 运势等级
    reasons: list[str] = field(default_factory=list)

    # 当前价对比（可选，传入后计算）
    current_price: Optional[float] = None
    pnl_pct: Optional[float] = None       # 当前盈亏百分比
    status: str = ""                      # 状态: safe / warning / danger / target / profit
    status_emoji: str = ""                # 状态对应 emoji


def _fortune_to_params(fortune_score: int) -> tuple[float, float, str]:
    """将运势评分映射为止损/止盈参数。
    返回 (stop_loss_pct, take_profit_pct, level)
    """
    if fortune_score >= 80:
        return -0.05, 0.15, "大吉"
    elif fortune_score >= 65:
        return -0.04, 0.10, "吉"
    elif fortune_score >= 50:
        return -0.03, 0.06, "平"
    elif fortune_score >= 35:
        return -0.02, 0.04, "小凶"
    else:
        return -0.015, 0.02, "凶"


def calc_stop_profit(
    entry_price: float,
    fortune_score: int,
    user_bazi: Optional[BaziResult] = None,
    stock_wuxing: Optional[str] = None,
    current_price: Optional[float] = None,
) -> StopProfitResult:
    """
    根据买入价和运势计算止损止盈点。

    Args:
        entry_price: 买入价
        fortune_score: 当日运势评分 0-100
        user_bazi: 用户八字（可选，用于五行微调）
        stock_wuxing: 股票五行属性（可选）
        current_price: 当前价（可选，传入后计算盈亏状态）

    Returns:
        StopProfitResult 对象
    """
    sl_pct, tp_pct, level = _fortune_to_params(fortune_score)
    reasons: list[str] = []

    reasons.append(f"运势{level}({fortune_score}分) → 止损{sl_pct*100:.1f}% / 止盈+{tp_pct*100:.0f}%")

    # ── 五行微调 ──
    if user_bazi and stock_wuxing:
        wx = stock_wuxing
        dm = user_bazi.day_master

        # 喜用神加持 → 止盈更宽，止损略宽
        if wx in user_bazi.xi_shen:
            tp_pct += 0.02
            sl_pct -= 0.005
            reasons.append(f"股票五行「{wx}」为喜用神 → 止盈+2% / 止损放宽0.5%")

        # 忌神 → 止盈降低，止损收紧
        elif wx in user_bazi.ji_shen:
            tp_pct -= 0.02
            sl_pct += 0.005
            reasons.append(f"股票五行「{wx}」为忌神 → 止盈-2% / 止损收紧0.5%")

        # 日主比和 → 稳健，微调
        if dm and wx == dm:
            tp_pct += 0.01
            reasons.append(f"股票五行「{wx}」与日主「{dm}」比和 → 止盈+1%")

    # 限制范围
    sl_pct = max(-0.10, min(-0.005, sl_pct))
    tp_pct = max(0.01, min(0.20, tp_pct))

    stop_loss = round(entry_price * (1 + sl_pct), 2)
    take_profit = round(entry_price * (1 + tp_pct), 2)

    result = StopProfitResult(
        entry_price=round(entry_price, 2),
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_loss_pct=round(sl_pct * 100, 1),
        take_profit_pct=round(tp_pct * 100, 1),
        fortune_score=fortune_score,
        fortune_level=level,
        reasons=reasons,
    )

    # ── 当前价对比 ──
    if current_price is not None and current_price > 0:
        result.current_price = round(current_price, 2)
        result.pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)

        if current_price <= stop_loss:
            result.status = "danger"
            result.status_emoji = "🔴"
        elif current_price >= take_profit:
            result.status = "target"
            result.status_emoji = "🟣"
        elif current_price <= entry_price * (1 + sl_pct * 0.5):
            # 接近止损价（止损幅度的一半以内）
            result.status = "warning"
            result.status_emoji = "🟠"
        elif current_price >= entry_price * (1 + tp_pct * 0.8):
            # 接近止盈价（止盈幅度的80%以上）
            result.status = "profit"
            result.status_emoji = "🟢"
        else:
            result.status = "safe"
            result.status_emoji = "🟡"

    return result


def batch_calc_stop_profit(
    positions: list[dict],
    fortune_score: int,
    user_bazi: Optional[BaziResult] = None,
) -> dict[str, StopProfitResult]:
    """
    批量计算多只股票的止损止盈。

    Args:
        positions: 持仓列表，每项含 {code, entry_price, wuxing, current_price}
        fortune_score: 当日运势评分
        user_bazi: 用户八字

    Returns:
        {stock_code: StopProfitResult} 字典
    """
    results = {}
    for pos in positions:
        try:
            r = calc_stop_profit(
                entry_price=pos["entry_price"],
                fortune_score=fortune_score,
                user_bazi=user_bazi,
                stock_wuxing=pos.get("wuxing"),
                current_price=pos.get("current_price"),
            )
            results[pos["code"]] = r
        except Exception as e:
            logger.warning("止损止盈计算失败: %s — %s", pos.get("code"), e)
    return results
