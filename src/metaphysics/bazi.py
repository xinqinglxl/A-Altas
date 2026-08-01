"""
八字排盘模块
依赖 lunar-python 库实现八字四柱、五行、喜用神计算
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from lunar_python import Lunar, Solar

from src.utils.logger import get_logger

logger = get_logger(__name__)


# 天干五行映射
GAN_WUXING = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# 地支五行映射
ZHI_WUXING = {
    "寅": "木", "卯": "木",
    "巳": "火", "午": "火",
    "申": "金", "酉": "金",
    "亥": "水", "子": "水",
    "辰": "土", "戌": "土", "丑": "土", "未": "土",
}

# 天干阴阳
GAN_YINYANG = {
    "甲": "阳", "丙": "阳", "戊": "阳", "庚": "阳", "壬": "阳",
    "乙": "阴", "丁": "阴", "己": "阴", "辛": "阴", "癸": "阴",
}

# 五行生克关系
WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
# 反克（被克）
WUXING_BEI_KE = {v: k for k, v in WUXING_KE.items()}

# 十二生肖
SHENGXIAO_MAP = {
    "子": "鼠", "丑": "牛", "寅": "虎", "卯": "兔",
    "辰": "龙", "巳": "蛇", "午": "马", "未": "羊",
    "申": "猴", "酉": "鸡", "戌": "狗", "亥": "猪",
}

# 星座日期范围
ZODIAC_RANGES = [
    ("摩羯座", (1, 1), (1, 19)),
    ("水瓶座", (1, 20), (2, 18)),
    ("双鱼座", (2, 19), (3, 20)),
    ("白羊座", (3, 21), (4, 19)),
    ("金牛座", (4, 20), (5, 20)),
    ("双子座", (5, 21), (6, 21)),
    ("巨蟹座", (6, 22), (7, 22)),
    ("狮子座", (7, 23), (8, 22)),
    ("处女座", (8, 23), (9, 22)),
    ("天秤座", (9, 23), (10, 23)),
    ("天蝎座", (10, 24), (11, 22)),
    ("射手座", (11, 23), (12, 21)),
    ("摩羯座", (12, 22), (12, 31)),
]


@dataclass
class BaziResult:
    """八字排盘结果"""

    year_gan: str = ""
    year_zhi: str = ""
    month_gan: str = ""
    month_zhi: str = ""
    day_gan: str = ""
    day_zhi: str = ""
    hour_gan: str = ""
    hour_zhi: str = ""

    day_master: str = ""  # 日主五行
    shengxiao: str = ""  # 生肖
    zodiac: str = ""  # 星座
    xi_shen: list[str] = field(default_factory=list)  # 喜用神
    ji_shen: list[str] = field(default_factory=list)  # 忌神

    def __str__(self):
        return (
            f"八字: {self.year_gan}{self.year_zhi} "
            f"{self.month_gan}{self.month_zhi} "
            f"{self.day_gan}{self.day_zhi} "
            f"{self.hour_gan}{self.hour_zhi}  |  "
            f"日主{self.day_master} | 生肖{self.shengxiao} | {self.zodiac}"
        )

    def to_dict(self) -> dict:
        return {
            "year_gan": self.year_gan,
            "year_zhi": self.year_zhi,
            "month_gan": self.month_gan,
            "month_zhi": self.month_zhi,
            "day_gan": self.day_gan,
            "day_zhi": self.day_zhi,
            "hour_gan": self.hour_gan,
            "hour_zhi": self.hour_zhi,
            "day_master": self.day_master,
            "shengxiao": self.shengxiao,
            "zodiac": self.zodiac,
            "xi_shen": self.xi_shen,
            "ji_shen": self.ji_shen,
        }


def get_zodiac(month: int, day: int) -> str:
    """根据月日获取星座"""
    for z, start, end in ZODIAC_RANGES:
        sm, sd = start
        em, ed = end
        if (month == sm and day >= sd) or (month == em and day <= ed):
            return z
    return "未知"


def get_day_gan_zhi(solar_date: date) -> tuple[str, str]:
    """获取指定公历日期的日柱天干地支"""
    solar = Solar.fromYmd(solar_date.year, solar_date.month, solar_date.day)
    lunar = Lunar.fromSolar(solar)
    eight_char = lunar.getEightChar()
    return str(eight_char.getDayGan()), str(eight_char.getDayZhi())


def calc_bazi(
    birth_date: date,
    birth_time: str = "00:00",
    is_solar: bool = True,
) -> BaziResult:
    """
    计算八字排盘

    Args:
        birth_date: 出生日期
        birth_time: 出生时间 HH:MM (24h)
        is_solar: True=公历, False=农历

    Returns:
        BaziResult 八字结果
    """
    hour = int(birth_time.split(":")[0])
    logger.debug(
        "八字排盘开始: date=%s, time=%s, is_solar=%s",
        birth_date.isoformat(), birth_time, is_solar,
    )

    if is_solar:
        solar = Solar.fromYmdHms(birth_date.year, birth_date.month, birth_date.day, hour, 0, 0)
    else:
        lunar_obj = Lunar.fromYmdHms(birth_date.year, birth_date.month, birth_date.day, hour, 0, 0)
        solar = lunar_obj.getSolar()

    lunar = Lunar.fromSolar(solar)
    eight_char = lunar.getEightChar()

    result = BaziResult(
        year_gan=str(eight_char.getYearGan()),
        year_zhi=str(eight_char.getYearZhi()),
        month_gan=str(eight_char.getMonthGan()),
        month_zhi=str(eight_char.getMonthZhi()),
        day_gan=str(eight_char.getDayGan()),
        day_zhi=str(eight_char.getDayZhi()),
        hour_gan=str(eight_char.getTimeGan()),
        hour_zhi=str(eight_char.getTimeZhi()),
    )

    result.day_master = GAN_WUXING.get(result.day_gan, "未知")
    result.shengxiao = SHENGXIAO_MAP.get(result.year_zhi, "未知")
    result.zodiac = get_zodiac(solar.getMonth(), solar.getDay())

    xi_shen, ji_shen = _calc_xi_ji_shen(result)
    result.xi_shen = xi_shen
    result.ji_shen = ji_shen

    logger.info(
        "八字排盘完成: 日主=%s, 喜用神=%s, 忌神=%s",
        result.day_master, xi_shen, ji_shen,
    )
    return result


def _calc_xi_ji_shen(bazi: BaziResult) -> tuple[list[str], list[str]]:
    """
    简易喜用神/忌神计算

    原理：统计八字五行分布，最弱的五行为喜用神，最强的为忌神
    （这是简化算法，真正的喜用神需要看日主强弱、调候等，这里作为示意）
    """
    wuxing_count = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}

    for gan in [bazi.year_gan, bazi.month_gan, bazi.day_gan, bazi.hour_gan]:
        if gan in GAN_WUXING:
            wuxing_count[GAN_WUXING[gan]] += 1

    for zhi in [bazi.year_zhi, bazi.month_zhi, bazi.day_zhi, bazi.hour_zhi]:
        if zhi in ZHI_WUXING:
            wuxing_count[ZHI_WUXING[zhi]] += 1

    # 按出现次数排序
    sorted_wx = sorted(wuxing_count.items(), key=lambda x: x[1])

    # 最弱的 2 个为喜用神
    xi_shen = [wx for wx, cnt in sorted_wx if cnt < 2]

    # 最强的 2 个为忌神
    ji_shen = [wx for wx, cnt in sorted_wx[::-1] if cnt >= 3]

    logger.debug("喜用神计算: 分布=%s → 喜神=%s, 忌神=%s", dict(sorted_wx), xi_shen, ji_shen)
    return xi_shen, ji_shen


def bazi_compatibility(user_bazi: BaziResult, target_bazi: BaziResult) -> float:
    """
    八字合盘打分 (0-100)

    基础分 50
    + 日主五行相生: +20
    + 年支生肖六合: +15
    + 喜用神互补: +15
    """
    score = 50.0

    # 1. 日主五行关系
    u_wx = user_bazi.day_master
    t_wx = target_bazi.day_master

    if u_wx and t_wx:
        if WUXING_SHENG.get(u_wx) == t_wx:
            score += 20  # 我生动方 → 我去生TA
        elif WUXING_SHENG.get(t_wx) == u_wx:
            score += 20  # TA来生我
        elif WUXING_KE.get(u_wx) == t_wx:
            score -= 10  # 我克TA
        elif WUXING_KE.get(t_wx) == u_wx:
            score -= 15  # TA克我

    # 2. 生肖六合
    liuhe_pairs = {
        ("子", "丑"), ("寅", "亥"), ("卯", "戌"),
        ("辰", "酉"), ("巳", "申"), ("午", "未"),
    }
    for a, b in liuhe_pairs:
        if {user_bazi.year_zhi, target_bazi.year_zhi} == {a, b}:
            score += 15
            break

    # 3. 喜用神互补
    u_xi = set(user_bazi.xi_shen)
    t_ji = set(target_bazi.ji_shen)
    overlap = u_xi & t_ji
    if overlap:
        score += len(overlap) * 5  # 我的喜神正好是TA的忌神方向上的互补

    final_score = max(0, min(100, score))
    logger.debug(
        "八字合盘: 用户日主=%s, 目标日主=%s, 结果=%.1f",
        user_bazi.day_master, target_bazi.day_master, final_score,
    )
    return final_score


def calc_company_bazi(founded_date: date) -> BaziResult:
    """用公司成立日期排八字（时辰默认子时）"""
    return calc_bazi(founded_date, "00:00", is_solar=True)


if __name__ == "__main__":
    # 测试
    test_date = date(1990, 5, 15)
    result = calc_bazi(test_date, "08:00")
    print(result)
    print(f"喜用神: {result.xi_shen}")
    print(f"忌神: {result.ji_shen}")
    print(f"日柱: {get_day_gan_zhi(date.today())}")
