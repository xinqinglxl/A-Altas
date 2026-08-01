"""
幸运运势计算模块。
基于用户八字四柱、喜用神、日主五行，计算：
- 幸运数字（河图洛书）
- 幸运颜色（五行色系）
- 幸运方位（五行方位）
- 幸运日（扫描未来日柱与用户喜用神匹配）
- 个人当日运势综合评分
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from lunar_python import Lunar, Solar

from src.metaphysics.bazi import (
    BaziResult,
    GAN_WUXING,
    SHENGXIAO_MAP,
    WUXING_KE,
    WUXING_SHENG,
    get_day_gan_zhi,
)
from src.utils.logger import get_logger
from src.utils.trading_calendar import is_trading_day, get_non_trading_reason

logger = get_logger(__name__)

# ── 河图洛书：五行对应数字 ──
WUXING_NUMBERS = {
    "水": [1, 6],
    "火": [2, 7],
    "木": [3, 8],
    "金": [4, 9],
    "土": [5, 0],
}

# ── 五行颜色 ──
WUXING_COLORS = {
    "金": ["白色", "金色", "银色"],
    "木": ["青色", "绿色", "翠色"],
    "水": ["蓝色", "黑色", "玄色"],
    "火": ["红色", "紫色", "赤色"],
    "土": ["黄色", "棕色", "咖色"],
}

# ── 五行方位 ──
WUXING_DIRECTIONS = {
    "金": ["正西", "西北"],
    "木": ["正东", "东南"],
    "水": ["正北"],
    "火": ["正南"],
    "土": ["中央", "东北", "西南"],
}

# ── 五行方位角度（用于罗盘展示）──
WUXING_DIRECTION_ANGLE = {
    "金": 270,   # 正西
    "木": 90,    # 正东
    "水": 0,     # 正北
    "火": 180,   # 正南
    "土": -1,    # 中央
}

# ── 十二生肖六合 ──
LIUHE_PAIRS = {
    ("子", "丑"), ("寅", "亥"), ("卯", "戌"),
    ("辰", "酉"), ("巳", "申"), ("午", "未"),
}

# ── 十二生肖三合局 ──
SANHE_GROUPS = [
    {"申", "子", "辰"},  # 水局
    {"亥", "卯", "未"},  # 木局
    {"寅", "午", "戌"},  # 火局
    {"巳", "酉", "丑"},  # 金局
]


@dataclass
class LuckyDay:
    """幸运日信息"""
    date: date
    gan: str
    zhi: str
    wuxing: str
    score: int               # 0-100 运势评分
    reasons: list[str] = field(default_factory=list)
    is_trading_day: bool = True
    non_trading_reason: Optional[str] = None
    yi: list[str] = field(default_factory=list)   # 黄历宜
    ji: list[str] = field(default_factory=list)   # 黄历忌

    @property
    def level(self) -> str:
        """运势等级"""
        if self.score >= 80:
            return "大吉"
        elif self.score >= 65:
            return "吉"
        elif self.score >= 50:
            return "平"
        elif self.score >= 35:
            return "小凶"
        else:
            return "凶"


@dataclass
class PersonalFortune:
    """个人当日运势"""
    date: date
    overall_score: int          # 综合运势 0-100
    lucky_numbers: list[int]
    lucky_colors: list[str]
    lucky_directions: list[str]
    wealth_direction: str       # 财神方位
    day_gan: str
    day_zhi: str
    day_wuxing: str
    relation_to_day_master: str  # 当日五行与日主的关系
    advice: str                  # 建议
    lucky_stocks_hint: list[str]  # 幸运板块提示


def get_lucky_numbers(bazi: BaziResult) -> list[int]:
    """
    根据八字喜用神计算幸运数字。

    河图洛书：水1/6、火2/7、木3/8、金4/9、土5/0
    """
    numbers = []
    seen = set()

    # 喜用神对应的数字
    for wx in bazi.xi_shen:
        for n in WUXING_NUMBERS.get(wx, []):
            if n not in seen:
                numbers.append(n)
                seen.add(n)

    # 日主五行对应的数字（次优）
    for n in WUXING_NUMBERS.get(bazi.day_master, []):
        if n not in seen:
            numbers.append(n)
            seen.add(n)

    logger.debug("幸运数字: 喜用神=%s, 日主=%s → %s", bazi.xi_shen, bazi.day_master, numbers)
    return numbers


def get_lucky_colors(bazi: BaziResult) -> list[str]:
    """根据喜用神计算幸运颜色"""
    colors = []
    seen = set()

    for wx in bazi.xi_shen:
        for c in WUXING_COLORS.get(wx, []):
            if c not in seen:
                colors.append(c)
                seen.add(c)

    # 日主五行颜色
    for c in WUXING_COLORS.get(bazi.day_master, []):
        if c not in seen:
            colors.append(c)
            seen.add(c)

    return colors


def get_lucky_directions(bazi: BaziResult) -> list[str]:
    """根据喜用神计算幸运方位"""
    directions = []
    seen = set()

    for wx in bazi.xi_shen:
        for d in WUXING_DIRECTIONS.get(wx, []):
            if d not in seen:
                directions.append(d)
                seen.add(d)

    return directions


def _score_day(
    target_date: date,
    bazi: BaziResult,
) -> LuckyDay:
    """
    评估某一天的运势评分。

    评分维度：
    - 日干五行与用户喜用神匹配（+30 max）
    - 日干五行与日主五行关系（+25 / -20）
    - 生肖六合/三合（+20）
    - 黄历宜交易类关键词（+15）
    - 黄历忌凶煞关键词（-10）
    """
    solar = Solar.fromYmd(target_date.year, target_date.month, target_date.day)
    lunar = Lunar.fromSolar(solar)
    eight_char = lunar.getEightChar()

    day_gan = str(eight_char.getDayGan())
    day_zhi = str(eight_char.getDayZhi())
    day_wuxing = GAN_WUXING.get(day_gan, "未知")

    yi = lunar.getDayYi()
    ji = lunar.getDayJi()

    score = 50
    reasons = []

    # 1. 喜用神匹配
    if day_wuxing in bazi.xi_shen:
        score += 30
        reasons.append(f"日干{day_gan}({day_wuxing})为喜用神")
    elif day_wuxing in bazi.ji_shen:
        score -= 15
        reasons.append(f"日干{day_gan}({day_wuxing})为忌神")

    # 2. 日干五行与日主关系
    user_dm = bazi.day_master
    if user_dm and day_wuxing:
        if day_wuxing == user_dm:
            score += 15
            reasons.append(f"日干{day_wuxing}与日主{user_dm}比和")
        elif WUXING_SHENG.get(day_wuxing) == user_dm:
            score += 25
            reasons.append(f"日干{day_wuxing}生日主{user_dm}")
        elif WUXING_SHENG.get(user_dm) == day_wuxing:
            score += 10
            reasons.append(f"日主{user_dm}生日干{day_wuxing}")
        elif WUXING_KE.get(day_wuxing) == user_dm:
            score -= 20
            reasons.append(f"日干{day_wuxing}克日主{user_dm}")
        elif WUXING_KE.get(user_dm) == day_wuxing:
            score -= 10
            reasons.append(f"日主{user_dm}克日干{day_wuxing}")

    # 3. 生肖合
    user_year_zhi = bazi.year_zhi
    if user_year_zhi and day_zhi:
        pair = {user_year_zhi, day_zhi}
        # 六合
        for a, b in LIUHE_PAIRS:
            if pair == {a, b}:
                score += 20
                reasons.append(f"日支{day_zhi}与年支{user_year_zhi}六合")
                break

        # 三合
        for group in SANHE_GROUPS:
            if user_year_zhi in group and day_zhi in group:
                score += 15
                reasons.append(f"日支{day_zhi}与年支{user_year_zhi}三合({group})")
                break

    # 4. 黄历宜忌关键词
    yi_text = " ".join(yi) if yi else ""
    ji_text = " ".join(ji) if ji else ""

    good_kw = ["交易", "开市", "立券", "纳财", "求财", "纳财"]
    bad_kw = ["破土", "安葬", "行丧", "动土", "伐木"]

    good_hits = [k for k in good_kw if k in yi_text]
    bad_hits = [k for k in bad_kw if k in ji_text]

    if good_hits:
        score += 15
        reasons.append(f"黄历宜{'、'.join(good_hits)}")
    if bad_hits:
        score -= 10
        reasons.append(f"黄历忌{'、'.join(bad_hits)}")

    # 交易日状态
    trading = is_trading_day(target_date)
    non_trading_reason = get_non_trading_reason(target_date)
    if not trading:
        reasons.append(f"非交易日({non_trading_reason})")

    score = max(0, min(100, score))

    return LuckyDay(
        date=target_date,
        gan=day_gan,
        zhi=day_zhi,
        wuxing=day_wuxing,
        score=score,
        reasons=reasons,
        is_trading_day=trading,
        non_trading_reason=non_trading_reason,
        yi=yi,
        ji=ji,
    )


def get_lucky_days(
    bazi: BaziResult,
    start_date: Optional[date] = None,
    days: int = 30,
    top_n: int = 5,
) -> list[LuckyDay]:
    """
    扫描未来 N 天，返回运势最高的 top_n 个幸运日。

    Args:
        bazi: 用户八字
        start_date: 起始日期，默认今天
        days: 扫描天数
        top_n: 返回前 N 个

    Returns:
        按 score 降序排列的 LuckyDay 列表
    """
    if start_date is None:
        start_date = date.today()

    logger.info("幸运日扫描: start=%s, days=%d, top_n=%d", start_date, days, top_n)

    results = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        try:
            lucky = _score_day(d, bazi)
            results.append(lucky)
        except Exception:
            logger.warning("评分失败: %s", d.isoformat(), exc_info=True)

    # 按评分降序
    results.sort(key=lambda x: x.score, reverse=True)
    top = results[:top_n]

    logger.info(
        "幸运日扫描完成: 共%d天, top%d最高分=%.0f (%s)",
        len(results), len(top),
        top[0].score if top else 0,
        top[0].date.isoformat() if top else "",
    )
    return top


def get_personal_fortune(
    bazi: BaziResult,
    target_date: Optional[date] = None,
) -> PersonalFortune:
    """
    计算个人当日运势。

    Args:
        bazi: 用户八字
        target_date: 目标日期，默认今天

    Returns:
        PersonalFortune 对象
    """
    if target_date is None:
        target_date = date.today()

    lucky_day = _score_day(target_date, bazi)
    solar = Solar.fromYmd(target_date.year, target_date.month, target_date.day)
    lunar = Lunar.fromSolar(solar)
    wealth_dir = lunar.getDayPositionCai()

    # 当日五行与日主关系
    relation = _get_relation_desc(bazi.day_master, lucky_day.wuxing)

    # 幸运板块提示
    lucky_stocks = []
    from src.metaphysics.wuxing import get_wuxing_compatible_sectors
    favorable = []
    if lucky_day.wuxing in bazi.xi_shen:
        favorable.append(lucky_day.wuxing)
    favorable.extend(bazi.xi_shen[:2])
    if favorable:
        sectors = get_wuxing_compatible_sectors(list(set(favorable)))
        lucky_stocks = sectors[:5]

    # 建议
    if lucky_day.score >= 65:
        advice = "今日运势旺盛，宜积极布局，把握交易良机。"
    elif lucky_day.score >= 50:
        advice = "今日运势平稳，可适度操作，不宜过度激进。"
    elif lucky_day.score >= 35:
        advice = "今日运势偏弱，建议观望为主，控制仓位。"
    else:
        advice = "今日运势低迷，忌重仓交易，宜守不宜攻。"

    if not lucky_day.is_trading_day:
        advice = f"今日{lucky_day.non_trading_reason or '休市'}，无交易。{advice}"

    return PersonalFortune(
        date=target_date,
        overall_score=lucky_day.score,
        lucky_numbers=get_lucky_numbers(bazi),
        lucky_colors=get_lucky_colors(bazi),
        lucky_directions=get_lucky_directions(bazi),
        wealth_direction=wealth_dir,
        day_gan=lucky_day.gan,
        day_zhi=lucky_day.zhi,
        day_wuxing=lucky_day.wuxing,
        relation_to_day_master=relation,
        advice=advice,
        lucky_stocks_hint=lucky_stocks,
    )


def _get_relation_desc(mine: str, theirs: str) -> str:
    """五行关系描述"""
    if not mine or not theirs:
        return "未知"
    if mine == theirs:
        return "比和（同类相助）"
    if WUXING_SHENG.get(mine) == theirs:
        return "我生（泄气）"
    if WUXING_SHENG.get(theirs) == mine:
        return "生我（得助）"
    if WUXING_KE.get(mine) == theirs:
        return "我克（制财）"
    if WUXING_KE.get(theirs) == mine:
        return "克我（受制）"
    return "未知"


if __name__ == "__main__":
    from src.metaphysics.bazi import calc_bazi

    test_bazi = calc_bazi(date(1990, 5, 15), "08:00")
    print(f"八字: {test_bazi}")
    print(f"日主: {test_bazi.day_master}")
    print(f"喜用神: {test_bazi.xi_shen}")
    print(f"忌神: {test_bazi.ji_shen}")
    print()

    print("=== 幸运数字 ===")
    print(get_lucky_numbers(test_bazi))
    print("\n=== 幸运颜色 ===")
    print(get_lucky_colors(test_bazi))
    print("\n=== 幸运方位 ===")
    print(get_lucky_directions(test_bazi))
    print()

    print("=== 未来30天幸运日 TOP 5 ===")
    for ld in get_lucky_days(test_bazi, days=30, top_n=5):
        print(f"  {ld.date} {ld.gan}{ld.zhi}({ld.wuxing}) [{ld.level}] {ld.score}分")
        for r in ld.reasons:
            print(f"    - {r}")

    print("\n=== 今日个人运势 ===")
    fortune = get_personal_fortune(test_bazi)
    print(f"  综合运势: {fortune.overall_score}分")
    print(f"  幸运数字: {fortune.lucky_numbers}")
    print(f"  幸运颜色: {fortune.lucky_colors}")
    print(f"  幸运方位: {fortune.lucky_directions}")
    print(f"  财神方位: {fortune.wealth_direction}")
    print(f"  日干关系: {fortune.relation_to_day_master}")
    print(f"  幸运板块: {fortune.lucky_stocks_hint}")
    print(f"  建议: {fortune.advice}")
