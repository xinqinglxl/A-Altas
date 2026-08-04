"""
星座算命模块。
基于西方占星学，计算：
- 星座档案（元素 / 模式 / 守护星 / 幸运数字 / 幸运颜色 / 幸运方位 / 性格特质 / 适配板块）
- 每日运势评分（守护星日 / 元素和谐度 / 星座模式行动力 / 幸运数字共振 / 水星逆行 / 月相 / 幸运星期）
- 个人当日运势综合（综合 / 财运 / 事业 / 爱情 评分 + 建议 + 适配板块）
- 未来幸运日扫描
- 水星逆行检测
- 月相计算

数据来源：用户 UserProfile.zodiac 字段（在八字排盘时已自动计算并存储）
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from src.metaphysics.bazi import get_zodiac, ZODIAC_RANGES
from src.utils.logger import get_logger
from src.utils.trading_calendar import is_trading_day, get_non_trading_reason

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
#  星座档案数据
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ZodiacProfile:
    """星座档案（不可变静态数据）"""
    name: str               # 中文名
    name_en: str            # 英文名
    symbol: str             # 符号
    element: str            # 元素: 火/土/风/水
    modality: str           # 模式: 基本宫/固定宫/变动宫
    ruling_planet: str      # 守护星
    co_ruling_planet: str   # 副守护星（现代占星）
    lucky_numbers: tuple    # 幸运数字
    lucky_colors: tuple     # 幸运颜色
    lucky_direction: str    # 幸运方位
    lucky_weekday: int      # 幸运星期 (0=周一 ... 6=周日)
    keywords: tuple         # 性格关键词
    traits: str             # 性格描述
    favorable_sectors: tuple  # 适配A股板块
    trading_style: str      # 交易风格


# 12 星座完整档案
ZODIAC_PROFILES: dict[str, ZodiacProfile] = {
    "白羊座": ZodiacProfile(
        name="白羊座", name_en="Aries", symbol="♈",
        element="火", modality="基本宫", ruling_planet="火星", co_ruling_planet="火星",
        lucky_numbers=(1, 9), lucky_colors=("红色", "橙色", "亮黄"),
        lucky_direction="正东", lucky_weekday=1,  # Tuesday
        keywords=("勇敢", "冒险", "开创", "冲动", "热情"),
        traits="天生的领导者，敢于冒险，行动力极强。交易中容易被冲动驱动，适合短线快进快出。",
        favorable_sectors=("军工", "能源", "体育", "钢铁", "新能源车"),
        trading_style="激进短线，敢追龙头，止损果断",
    ),
    "金牛座": ZodiacProfile(
        name="金牛座", name_en="Taurus", symbol="♉",
        element="土", modality="固定宫", ruling_planet="金星", co_ruling_planet="金星",
        lucky_numbers=(2, 6), lucky_colors=("绿色", "粉色", "大地色"),
        lucky_direction="东南", lucky_weekday=4,  # Friday
        keywords=("稳健", "务实", "享受", "固执", "耐心"),
        traits="最务实的星座，重视价值和安全感。交易中善于发现低估品种，持有耐心极强。",
        favorable_sectors=("银行", "房地产", "食品饮料", "消费", "农业"),
        trading_style="价值投资，长线持有，不追涨杀跌",
    ),
    "双子座": ZodiacProfile(
        name="双子座", name_en="Gemini", symbol="♊",
        element="风", modality="变动宫", ruling_planet="水星", co_ruling_planet="水星",
        lucky_numbers=(3, 5), lucky_colors=("黄色", "银色", "天蓝"),
        lucky_direction="正西", lucky_weekday=2,  # Wednesday
        keywords=("灵活", "好奇", "善变", "机智", "善交际"),
        traits="思维敏捷，信息收集能力极强。交易中善于捕捉市场热点和题材轮动。",
        favorable_sectors=("通信", "传媒", "电子", "互联网", "半导体"),
        trading_style="题材轮动，快进快出，善于捕捉热点",
    ),
    "巨蟹座": ZodiacProfile(
        name="巨蟹座", name_en="Cancer", symbol="♋",
        element="水", modality="基本宫", ruling_planet="月亮", co_ruling_planet="月亮",
        lucky_numbers=(2, 7), lucky_colors=("白色", "银色", "浅蓝"),
        lucky_direction="正北", lucky_weekday=0,  # Monday
        keywords=("敏感", "顾家", "直觉", "保护", "念旧"),
        traits="直觉敏锐，情绪驱动型。交易中擅长凭感觉判断顶底，但也容易情绪化操作。",
        favorable_sectors=("食品", "农业", "家居", "白酒", "乳业"),
        trading_style="凭直觉交易，善于抄底逃顶但需控制情绪",
    ),
    "狮子座": ZodiacProfile(
        name="狮子座", name_en="Leo", symbol="♌",
        element="火", modality="固定宫", ruling_planet="太阳", co_ruling_planet="太阳",
        lucky_numbers=(1, 4), lucky_colors=("金色", "橙色", "明黄"),
        lucky_direction="正南", lucky_weekday=6,  # Sunday
        keywords=("自信", "霸气", "表现", "慷慨", "骄傲"),
        traits="天生的王者，喜欢大格局。交易中偏好龙头股和明星标的，敢于重仓。",
        favorable_sectors=("娱乐", "奢侈品", "游戏", "影视", "黄金"),
        trading_style="重仓龙头，追求大收益，不怕高调",
    ),
    "处女座": ZodiacProfile(
        name="处女座", name_en="Virgo", symbol="♍",
        element="土", modality="变动宫", ruling_planet="水星", co_ruling_planet="水星",
        lucky_numbers=(5, 7), lucky_colors=("藏青", "灰色", "米色"),
        lucky_direction="西南", lucky_weekday=2,  # Wednesday
        keywords=("细致", "分析", "完美", "谨慎", "服务"),
        traits="最善于分析的星座，追求完美和精确。交易中擅长基本面研究和数据挖掘。",
        favorable_sectors=("医药", "环保", "精密制造", "检测", "化工"),
        trading_style="数据驱动，精细选股，严格风控",
    ),
    "天秤座": ZodiacProfile(
        name="天秤座", name_en="Libra", symbol="♎",
        element="风", modality="基本宫", ruling_planet="金星", co_ruling_planet="金星",
        lucky_numbers=(6, 9), lucky_colors=("蓝色", "粉色", "淡绿"),
        lucky_direction="西北", lucky_weekday=4,  # Friday
        keywords=("平衡", "优雅", "合作", "犹豫", "审美"),
        traits="追求平衡与和谐，善于权衡利弊。交易中擅长资产配置和仓位管理。",
        favorable_sectors=("美容", "服装", "艺术", "珠宝", "家电"),
        trading_style="均衡配置，注重风险收益比，善于调仓",
    ),
    "天蝎座": ZodiacProfile(
        name="天蝎座", name_en="Scorpio", symbol="♏",
        element="水", modality="固定宫", ruling_planet="冥王星", co_ruling_planet="火星",
        lucky_numbers=(4, 8), lucky_colors=("暗红", "黑色", "深紫"),
        lucky_direction="正北", lucky_weekday=1,  # Tuesday (co-ruler Mars)
        keywords=("深沉", "洞察", "执着", "隐忍", "蜕变"),
        traits="最神秘的星座，洞察力极强。交易中善于发现暗线和预期差，敢于逆向投资。",
        favorable_sectors=("矿业", "金融", "医药", "军工", "石油"),
        trading_style="逆向投资，敢于抄底冷门，善于挖掘预期差",
    ),
    "射手座": ZodiacProfile(
        name="射手座", name_en="Sagittarius", symbol="♐",
        element="火", modality="变动宫", ruling_planet="木星", co_ruling_planet="木星",
        lucky_numbers=(3, 9), lucky_colors=("紫色", "青绿", "宝蓝"),
        lucky_direction="东南", lucky_weekday=3,  # Thursday
        keywords=("乐观", "自由", "探索", "哲学", "冒险"),
        traits="天生的乐观主义者，视野开阔。交易中偏好成长股和新兴赛道。",
        favorable_sectors=("旅游", "教育", "航天", "跨境电商", "新能源"),
        trading_style="追成长股，偏好新兴产业，仓位灵活",
    ),
    "摩羯座": ZodiacProfile(
        name="摩羯座", name_en="Capricorn", symbol="♑",
        element="土", modality="基本宫", ruling_planet="土星", co_ruling_planet="土星",
        lucky_numbers=(8, 10), lucky_colors=("棕色", "黑色", "深灰"),
        lucky_direction="正东", lucky_weekday=5,  # Saturday
        keywords=("务实", "隐忍", "雄心", "纪律", "传统"),
        traits="最有纪律性的星座，目标明确。交易中严格执行策略，擅长长期布局。",
        favorable_sectors=("建筑", "基建", "银行", "电力", "煤炭"),
        trading_style="严格纪律，长线布局，按计划执行",
    ),
    "水瓶座": ZodiacProfile(
        name="水瓶座", name_en="Aquarius", symbol="♒",
        element="风", modality="固定宫", ruling_planet="天王星", co_ruling_planet="土星",
        lucky_numbers=(4, 7), lucky_colors=("电蓝", "银色", "荧光绿"),
        lucky_direction="正西", lucky_weekday=5,  # Saturday (co-ruler Saturn)
        keywords=("独立", "创新", "叛逆", "理性", "人道"),
        traits="最创新的星座，思维独特。交易中偏好科技前沿和颠覆性创新标的。",
        favorable_sectors=("科技", "新能源", "航空", "人工智能", "量子计算"),
        trading_style="追逐前沿科技，偏好创新标的，不随大流",
    ),
    "双鱼座": ZodiacProfile(
        name="双鱼座", name_en="Pisces", symbol="♓",
        element="水", modality="变动宫", ruling_planet="海王星", co_ruling_planet="木星",
        lucky_numbers=(7, 12), lucky_colors=("海绿", "薰衣草紫", "浅粉"),
        lucky_direction="正南", lucky_weekday=3,  # Thursday (co-ruler Jupiter)
        keywords=("浪漫", "慈悲", "直觉", "艺术", "梦幻"),
        traits="最富直觉的星座，感性而细腻。交易中善于感受市场情绪和资金流向。",
        favorable_sectors=("酒类", "医药", "影视", "化妆品", "水产"),
        trading_style="情绪感知型，善于捕捉市场氛围和资金偏好",
    ),
}


# ═══════════════════════════════════════════════════════════
#  元素兼容性
# ═══════════════════════════════════════════════════════════

# 西方占星元素兼容性（与五行不同）
# 火 + 风 = 互相促进（阳性元素和谐）
# 土 + 水 = 互相滋养（阴性元素和谐）
# 火 + 水 = 冲突
# 其余 = 中性
ELEMENT_COMPAT: dict[tuple[str, str], float] = {
    # 同元素 → 和谐
    ("火", "火"): 1.0, ("土", "土"): 1.0, ("风", "风"): 1.0, ("水", "水"): 1.0,
    # 火 + 风 → 高度和谐
    ("火", "风"): 1.0, ("风", "火"): 1.0,
    # 土 + 水 → 和谐
    ("土", "水"): 1.0, ("水", "土"): 1.0,
    # 火 + 水 → 冲突
    ("火", "水"): -1.0, ("水", "火"): -1.0,
    # 火 + 土 → 轻微不和（火焦土）
    ("火", "土"): -0.3, ("土", "火"): -0.3,
    # 风 + 水 → 轻微不和（风散水）
    ("风", "水"): -0.3, ("水", "风"): -0.3,
    # 风 + 土 → 轻微不和（风蚀土）
    ("风", "土"): -0.3, ("土", "风"): -0.3,
}

ELEMENT_DESC = {"火": "热情行动", "土": "务实稳健", "风": "思维灵活", "水": "直觉感性"}

# 星座模式 → 交易行动力
MODALITY_TRADE_SCORE = {"基本宫": 8, "固定宫": 5, "变动宫": 3}
MODALITY_DESC = {
    "基本宫": "开创行动，适合建仓和启动新策略",
    "固定宫": "稳固持有，适合持仓不动和守仓",
    "变动宫": "灵活调整，适合调仓换股和适应变化",
}

# 星期 → 守护星
WEEKDAY_PLANET = {
    0: "月亮",   # Monday
    1: "火星",   # Tuesday
    2: "水星",   # Wednesday
    3: "木星",   # Thursday
    4: "金星",   # Friday
    5: "土星",   # Saturday
    6: "太阳",   # Sunday
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ═══════════════════════════════════════════════════════════
#  水星逆行数据（2024-2027 近似日期）
# ═══════════════════════════════════════════════════════════

MERCURY_RETROGRADES: list[tuple[date, date]] = [
    # 2024
    (date(2024, 4, 2), date(2024, 4, 25)),
    (date(2024, 8, 5), date(2024, 8, 29)),
    (date(2024, 12, 15), date(2025, 1, 1)),
    # 2025
    (date(2025, 3, 15), date(2025, 4, 7)),
    (date(2025, 7, 18), date(2025, 8, 11)),
    (date(2025, 11, 9), date(2025, 11, 29)),
    # 2026
    (date(2026, 2, 25), date(2026, 3, 20)),
    (date(2026, 6, 29), date(2026, 7, 23)),
    (date(2026, 10, 24), date(2026, 11, 13)),
    # 2027
    (date(2027, 2, 11), date(2027, 3, 5)),
    (date(2027, 6, 17), date(2027, 7, 11)),
    (date(2027, 10, 14), date(2027, 11, 4)),
]


def is_mercury_retrograde(target_date: date) -> tuple[bool, Optional[str]]:
    """
    检查指定日期是否处于水星逆行期。

    Returns:
        (是否逆行, 描述文案)
    """
    for start, end in MERCURY_RETROGRADES:
        if start <= target_date <= end:
            days_into = (target_date - start).days
            total_days = (end - start).days
            phase = "逆行初期" if days_into < total_days // 3 \
                else "逆行中期" if days_into < total_days * 2 // 3 \
                else "逆行末期"
            return True, f"水星{phase}（{start.strftime('%m/%d')} - {end.strftime('%m/%d')}）"
    return False, None


# ═══════════════════════════════════════════════════════════
#  月相计算
# ═══════════════════════════════════════════════════════════

# 参考新月: 2000-01-06 18:14 UTC
_NEW_MOON_REF = date(2000, 1, 6)
_SYNODIC_MONTH = 29.530588853  # 朔望月周期（天）

MOON_PHASES = [
    (0, 1.85, "新月", "🌑", 8, "新的开始，适合建仓和启动新策略"),
    (1.85, 5.54, "蛾眉月", "🌒", 5, "蓄势待发，适合研究观察和小仓位试探"),
    (5.54, 9.23, "上弦月", "🌓", 3, "行动推进，适合加仓和执行计划"),
    (9.23, 12.92, "盈凸月", "🌔", 5, "势头强劲，适合持仓待涨"),
    (12.92, 16.61, "满月", "🌕", -3, "情绪高潮，容易出现非理性操作，需谨慎"),
    (16.61, 20.30, "亏凸月", "🌖", 3, "收获回落，适合减仓兑现利润"),
    (20.30, 23.99, "下弦月", "🌗", 0, "反思调整，适合复盘和修正策略"),
    (23.99, 27.68, "残月", "🌘", -2, "收尾清理，适合清仓和等待新周期"),
    (27.68, 29.53, "新月前夕", "🌑", 6, "周期重启前夜，适合布局下一个机会"),
]


def get_moon_phase(target_date: date) -> tuple[str, str, int, str]:
    """
    计算指定日期的月相。

    Returns:
        (月相名称, emoji, 评分加成, 描述)
    """
    days_since = (target_date - _NEW_MOON_REF).days
    moon_age = days_since % _SYNODIC_MONTH

    for start, end, name, emoji, score, desc in MOON_PHASES:
        if start <= moon_age < end:
            return name, emoji, score, desc

    # fallback
    return "新月", "🌑", 8, "新的开始"


# ═══════════════════════════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class ConstellationDayScore:
    """星座日运势评分结果"""
    date: date
    score: int               # 0-100 综合评分
    reasons: list[str] = field(default_factory=list)
    is_trading_day: bool = True
    non_trading_reason: Optional[str] = None

    # 星象详情
    sun_sign: str = ""        # 当日太阳所在星座
    moon_phase: str = ""      # 月相
    moon_emoji: str = ""
    ruling_planet_today: str = ""  # 当日守护星
    mercury_retrograde: bool = False

    @property
    def level(self) -> str:
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
class ConstellationFortune:
    """星座个人当日运势综合"""
    date: date
    zodiac: str               # 用户星座
    profile: ZodiacProfile     # 星座档案

    overall_score: int        # 综合运势 0-100
    wealth_score: int         # 财运 0-100
    career_score: int         # 事业运 0-100
    love_score: int           # 爱情运 0-100

    lucky_numbers: list[int]
    lucky_colors: list[str]
    lucky_direction: str
    lucky_weekday: str

    # 星象详情
    sun_sign: str              # 当日太阳星座
    element_harmony: str       # 元素和谐描述
    ruling_planet_today: str   # 当日守护星
    is_planet_day: bool        # 是否守护星日
    moon_phase: str
    moon_emoji: str
    mercury_retrograde: bool
    mercury_desc: Optional[str]

    advice: str                # 交易建议
    favorable_sectors: list[str]  # 适配板块
    trading_style: str         # 交易风格提示

    reasons: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
#  核心计算函数
# ═══════════════════════════════════════════════════════════

def get_zodiac_profile(zodiac: str) -> Optional[ZodiacProfile]:
    """获取星座档案"""
    return ZODIAC_PROFILES.get(zodiac)


def _get_sun_sign(target_date: date) -> str:
    """获取指定日期太阳所在的星座"""
    return get_zodiac(target_date.month, target_date.day)


def _digit_root(n: int) -> int:
    """计算数字的数根（反复相加至一位数）"""
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n


def _lucky_number_resonance(target_date: date, lucky_numbers: tuple) -> tuple[bool, int]:
    """
    检查日期数字与幸运数字的共振。

    将日期的年+月+日相加后取数根，与幸运数字比对。

    Returns:
        (是否共振, 数根值)
    """
    total = target_date.year + target_date.month + target_date.day
    root = _digit_root(total)
    return root in lucky_numbers, root


def score_day_constellation(target_date: date, zodiac: str) -> ConstellationDayScore:
    """
    用星座占星学为指定日期评分。

    评分维度（基础 50 分）：
    1. 守护星日加成 (+15 / +8)
    2. 元素和谐度 (+12 / -10)
    3. 星座模式行动力 (+8 / +5 / +3)
    4. 幸运数字共振 (+10)
    5. 水星逆行惩罚 (-15)
    6. 月相加成 (+8 ~ -3)
    7. 幸运星期 (+10)
    """
    profile = get_zodiac_profile(zodiac)
    if profile is None:
        return ConstellationDayScore(date=target_date, score=50, reasons=["未知星座"])

    score = 50
    reasons = []

    # ── 1. 守护星日加成 ──
    weekday = target_date.weekday()
    today_planet = WEEKDAY_PLANET.get(weekday, "")
    ruling = profile.ruling_planet
    co_ruling = profile.co_ruling_planet

    if today_planet == ruling:
        score += 15
        reasons.append(f"⭐ 守护星日：今日{WEEKDAY_CN[weekday]}由{ruling}守护，与你的守护星一致 (+15)")
    elif today_planet == co_ruling and co_ruling != ruling:
        score += 8
        reasons.append(f"☆ 副守护星日：今日{WEEKDAY_CN[weekday]}由{co_ruling}守护，与你的副守护星一致 (+8)")

    # ── 2. 元素和谐度 ──
    current_sun = _get_sun_sign(target_date)
    current_profile = get_zodiac_profile(current_sun)
    if current_profile:
        compat = ELEMENT_COMPAT.get((profile.element, current_profile.element), 0)
        if compat >= 1.0:
            score += 12
            reasons.append(
                f"🔥 元素和谐：你的{profile.element}元素与当前{current_sun}的{current_profile.element}元素高度和谐 (+12)"
            )
        elif compat <= -1.0:
            score -= 10
            reasons.append(
                f"💧 元素冲突：你的{profile.element}元素与当前{current_sun}的{current_profile.element}元素相克 (-10)"
            )
        elif compat <= -0.3:
            score -= 3
            reasons.append(
                f"⚖️ 元素微调：你的{profile.element}与当前{current_sun}的{current_profile.element}略有摩擦 (-3)"
            )

    # ── 3. 星座模式行动力 ──
    if current_profile:
        modality_score = MODALITY_TRADE_SCORE.get(current_profile.modality, 0)
        score += modality_score
        reasons.append(
            f"🔄 星座模式：当前太阳在{current_profile.modality}，{MODALITY_DESC[current_profile.modality]} (+{modality_score})"
        )

    # ── 4. 幸运数字共振 ──
    resonates, root = _lucky_number_resonance(target_date, profile.lucky_numbers)
    if resonates:
        score += 10
        reasons.append(
            f"🔢 数字共振：今日数字根为{root}，与你的幸运数字{profile.lucky_numbers}共振 (+10)"
        )

    # ── 5. 水星逆行惩罚 ──
    is_retro, retro_desc = is_mercury_retrograde(target_date)
    if is_retro:
        score -= 15
        reasons.append(f"⚠️ 水星逆行：{retro_desc}，沟通/决策/电子设备易受干扰 (-15)")
    else:
        reasons.append("✅ 水星顺行：沟通顺畅，决策清晰")

    # ── 6. 月相加成 ──
    moon_name, moon_emoji, moon_score, moon_desc = get_moon_phase(target_date)
    score += moon_score
    if moon_score > 0:
        reasons.append(f"{moon_emoji} {moon_name}：{moon_desc} (+{moon_score})")
    elif moon_score < 0:
        reasons.append(f"{moon_emoji} {moon_name}：{moon_desc} ({moon_score})")
    else:
        reasons.append(f"{moon_emoji} {moon_name}：{moon_desc}")

    # ── 7. 幸运星期 ──
    if weekday == profile.lucky_weekday:
        score += 10
        reasons.append(f"📅 幸运星期：{WEEKDAY_CN[weekday]}是你的幸运日 (+10)")

    # ── 交易日状态 ──
    td = is_trading_day(target_date)
    ntr = None
    if not td:
        ntr = get_non_trading_reason(target_date)

    score = max(0, min(100, score))

    return ConstellationDayScore(
        date=target_date,
        score=score,
        reasons=reasons,
        is_trading_day=td,
        non_trading_reason=ntr,
        sun_sign=current_sun,
        moon_phase=moon_name,
        moon_emoji=moon_emoji,
        ruling_planet_today=today_planet,
        mercury_retrograde=is_retro,
    )


def get_constellation_lucky_days(
    zodiac: str,
    start_date: Optional[date] = None,
    days: int = 30,
    top_n: int = 5,
) -> list[ConstellationDayScore]:
    """
    扫描未来 N 天，返回运势最好的 top_n 天。

    Args:
        zodiac: 用户星座
        start_date: 起始日期（默认今天）
        days: 扫描天数
        top_n: 返回前几名

    Returns:
        按评分降序排列的 ConstellationDayScore 列表
    """
    if start_date is None:
        start_date = date.today()

    results: list[ConstellationDayScore] = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        result = score_day_constellation(d, zodiac)
        results.append(result)

    # 按评分降序，同分按日期升序
    results.sort(key=lambda x: (-x.score, x.date))
    return results[:top_n]


def get_constellation_fortune(
    zodiac: str,
    target_date: Optional[date] = None,
) -> Optional[ConstellationFortune]:
    """
    获取星座个人当日运势综合。

    Args:
        zodiac: 用户星座
        target_date: 目标日期（默认今天）

    Returns:
        ConstellationFortune 或 None（星座无效时）
    """
    if target_date is None:
        target_date = date.today()

    profile = get_zodiac_profile(zodiac)
    if profile is None:
        return None

    # 基础评分
    day_score = score_day_constellation(target_date, zodiac)
    base = day_score.score

    # 财运：基础分 + 土元素/金星/木星加成
    wealth = base
    current_sun = _get_sun_sign(target_date)
    current_profile = get_zodiac_profile(current_sun)
    if current_profile:
        if current_profile.element == "土":
            wealth = min(100, wealth + 10)
        if current_profile.ruling_planet == "金星":
            wealth = min(100, wealth + 8)
        if current_profile.ruling_planet == "木星":
            wealth = min(100, wealth + 5)

    # 水逆对财运影响更大
    if day_score.mercury_retrograde:
        wealth = max(0, wealth - 10)

    # 事业运：基础分 + 火元素/太阳/土星加成
    career = base
    if current_profile:
        if current_profile.element == "火":
            career = min(100, career + 10)
        if current_profile.ruling_planet == "太阳":
            career = min(100, career + 8)
        if current_profile.ruling_planet == "土星":
            career = min(100, career + 5)

    # 爱情运：基础分 + 水元素/金星/月亮加成
    love = base
    if current_profile:
        if current_profile.element == "水":
            love = min(100, love + 10)
        if current_profile.ruling_planet == "金星":
            love = min(100, love + 8)
        if current_profile.ruling_planet == "月亮":
            love = min(100, love + 5)

    # 幸运星期
    weekday = target_date.weekday()
    lucky_wd = WEEKDAY_CN[profile.lucky_weekday]

    # 元素和谐描述
    if current_profile:
        compat = ELEMENT_COMPAT.get((profile.element, current_profile.element), 0)
        if compat >= 1.0:
            harmony = f"你的{profile.element}元素与当前{current_sun}({current_profile.element})高度和谐"
        elif compat <= -1.0:
            harmony = f"你的{profile.element}元素与当前{current_sun}({current_profile.element})相克冲突"
        elif compat <= -0.3:
            harmony = f"你的{profile.element}元素与当前{current_sun}({current_profile.element})略有摩擦"
        else:
            harmony = f"你的{profile.element}元素与当前{current_sun}({current_profile.element})中性相处"
    else:
        harmony = "未知"

    # 水逆
    is_retro, retro_desc = is_mercury_retrograde(target_date)

    # 月相
    moon_name, moon_emoji, _, moon_desc = get_moon_phase(target_date)

    # 建议文案
    advice = _build_advice(profile, day_score, current_profile, is_retro)

    return ConstellationFortune(
        date=target_date,
        zodiac=zodiac,
        profile=profile,
        overall_score=base,
        wealth_score=max(0, min(100, wealth)),
        career_score=max(0, min(100, career)),
        love_score=max(0, min(100, love)),
        lucky_numbers=list(profile.lucky_numbers),
        lucky_colors=list(profile.lucky_colors),
        lucky_direction=profile.lucky_direction,
        lucky_weekday=lucky_wd,
        sun_sign=current_sun,
        element_harmony=harmony,
        ruling_planet_today=WEEKDAY_PLANET.get(weekday, ""),
        is_planet_day=(WEEKDAY_PLANET.get(weekday, "") == profile.ruling_planet),
        moon_phase=moon_name,
        moon_emoji=moon_emoji,
        mercury_retrograde=is_retro,
        mercury_desc=retro_desc,
        advice=advice,
        favorable_sectors=list(profile.favorable_sectors),
        trading_style=profile.trading_style,
        reasons=day_score.reasons,
    )


def _build_advice(
    profile: ZodiacProfile,
    day_score: ConstellationDayScore,
    current_profile: Optional[ZodiacProfile],
    is_retro: bool,
) -> str:
    """根据评分生成交易建议"""
    parts = []

    if day_score.score >= 75:
        parts.append(f"今日星象极佳，{profile.trading_style}。")
    elif day_score.score >= 60:
        parts.append(f"今日运势不错，可以按你的风格操作——{profile.trading_style}。")
    elif day_score.score >= 45:
        parts.append("今日运势平稳，建议轻仓观望或小仓位试探。")
    elif day_score.score >= 30:
        parts.append("今日星象不佳，建议控制仓位，避免大额操作。")
    else:
        parts.append("今日运势低迷，建议空仓休息，等待更好的时机。")

    # 水逆提醒
    if is_retro:
        parts.append("水星逆行期间，避免签合同、大额交易和重大决策，注意通信和电子设备故障。")

    # 元素提醒
    if current_profile:
        compat = ELEMENT_COMPAT.get((profile.element, current_profile.element), 0)
        if compat >= 1.0:
            parts.append(f"当前{current_profile.name}月，{ELEMENT_DESC[current_profile.element]}的能量与你高度契合，{profile.favorable_sectors[0]}等板块值得关注。")
        elif compat <= -1.0:
            parts.append(f"当前{current_profile.name}月，元素相克，建议降低风险敞口，优先关注{profile.favorable_sectors[0]}等防御性板块。")

    # 幸运方位
    if day_score.score >= 60:
        parts.append(f"交易时面向{profile.lucky_direction}方位，穿戴{profile.lucky_colors[0]}系衣物可增强运势。")

    return " ".join(parts)


# ═══════════════════════════════════════════════════════════
#  星座配对兼容性
# ═══════════════════════════════════════════════════════════

def zodiac_compatibility(zodiac1: str, zodiac2: str) -> tuple[int, str]:
    """
    计算两个星座的兼容性评分。

    Returns:
        (0-100 评分, 描述)
    """
    p1 = get_zodiac_profile(zodiac1)
    p2 = get_zodiac_profile(zodiac2)
    if not p1 or not p2:
        return 50, "未知星座"

    score = 50
    reasons = []

    # 元素兼容
    compat = ELEMENT_COMPAT.get((p1.element, p2.element), 0)
    if compat >= 1.0:
        score += 25
        reasons.append(f"{p1.element}与{p2.element}元素高度和谐")
    elif compat <= -1.0:
        score -= 15
        reasons.append(f"{p1.element}与{p2.element}元素相克")
    elif compat <= -0.3:
        score -= 5
        reasons.append(f"{p1.element}与{p2.element}元素略有摩擦")

    # 模式兼容
    if p1.modality == p2.modality:
        score += 10
        reasons.append(f"同为{p1.modality}，行动节奏一致")
    else:
        # 不同模式互补
        score += 5
        reasons.append(f"{p1.modality}与{p2.modality}互补")

    # 守护星关系
    if p1.ruling_planet == p2.ruling_planet:
        score += 15
        reasons.append(f"同为{p1.ruling_planet}守护，气质相近")

    score = max(0, min(100, score))
    desc = "；".join(reasons)
    return score, desc


if __name__ == "__main__":
    # 测试
    today = date.today()
    for z in ["白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
              "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座"]:
        fortune = get_constellation_fortune(z, today)
        if fortune:
            print(f"{z}: 综合{fortune.overall_score} 财运{fortune.wealth_score} "
                  f"事业{fortune.career_score} 爱情{fortune.love_score}")
