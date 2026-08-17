"""
综合评分引擎 - 财神指数
结合八字合盘、五行匹配、天干择时、黄历信号
"""

from datetime import date, datetime
from typing import Optional

from src.data.db import (
    DailySignal,
    ExchangeRate,
    StockBasic,
    StockBazi,
    StockScore,
    UserProfile,
    db,
)
from src.metaphysics.bazi import GAN_WUXING, BaziResult, bazi_compatibility, calc_bazi
from src.metaphysics.ganzhi import get_daily_signal, get_ganzhi_timing_score
from src.metaphysics.wuxing import wuxing_match_score
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _user_bazi_from_profile(user: UserProfile) -> BaziResult:
    """从 UserProfile 重建 BaziResult"""
    return BaziResult(
        year_gan=user.year_gan,
        year_zhi=user.year_zhi,
        month_gan=user.month_gan,
        month_zhi=user.month_zhi,
        day_gan=user.day_gan,
        day_zhi=user.day_zhi,
        hour_gan=user.hour_gan,
        hour_zhi=user.hour_zhi,
        day_master=GAN_WUXING.get(user.day_gan, "未知"),
        shengxiao=user.shengxiao or "未知",
        zodiac=user.zodiac or "未知",
        xi_shen=(user.xi_shen.split(",") if user.xi_shen else []),
        ji_shen=(user.ji_shen.split(",") if user.ji_shen else []),
    )




def _stock_bazi_from_db(stock: StockBasic, bazi_type: str = "founded") -> Optional[BaziResult]:
    """从 StockBazi 表重建 BaziResult"""
    try:
        sb = StockBazi.select().where(
            StockBazi.stock == stock,
            StockBazi.bazi_type == bazi_type,
        ).first()
    except Exception:
        return None

    if not sb:
        return None

    return BaziResult(
        year_gan=sb.year_gan,
        year_zhi=sb.year_zhi,
        month_gan=sb.month_gan,
        month_zhi=sb.month_zhi,
        day_gan=sb.day_gan,
        day_zhi=sb.day_zhi,
        hour_gan=sb.hour_gan or "",
        hour_zhi=sb.hour_zhi or "",
        day_master=sb.day_master,
    )


def score_stock(
    stock: StockBasic,
    user: UserProfile,
    target_date: Optional[date] = None,
) -> dict:
    """
    对单只股票进行综合玄学评分

    Returns:
        dict with bazi_score, wuxing_score, timing_score, composite_score, summary
    """
    if target_date is None:
        target_date = date.today()

    logger.debug("评分开始: stock=%s(%s), user=%s", stock.code, stock.name, user.name)
    scores = {}
    notes = []

    # 1. 八字合盘分
    user_bazi = _user_bazi_from_profile(user)
    stock_bazi = _stock_bazi_from_db(stock)
    if stock_bazi:
        bazi_score = bazi_compatibility(user_bazi, stock_bazi)
        notes.append(f"八字合盘: {bazi_score:.0f}分")
    else:
        bazi_score = 50
        notes.append("八字数据缺失，使用默认分")

    # 2. 五行匹配分
    user_xi_shen = user_bazi.xi_shen
    if stock.wuxing and user_xi_shen:
        wuxing_score = wuxing_match_score(user_bazi.day_master, stock.wuxing)
        notes.append(f"五行'{stock.wuxing}'匹配: {wuxing_score:.0f}分")
    else:
        wuxing_score = 50
        notes.append("五行数据不完整，使用默认分")

    # 3. 天干择时分
    signal = get_daily_signal(target_date)
    timing_score = get_ganzhi_timing_score(
        day_wuxing=signal["day_wuxing"],
        sector_wuxing=stock.wuxing or "",
        user_xi_shen=user_xi_shen,
    )
    notes.append(
        f"今日{signal['day_gan']}{signal['day_zhi']}日择时: {timing_score:.0f}分"
    )

    # 4. 综合财神指数
    composite = bazi_score * 0.35 + wuxing_score * 0.30 + timing_score * 0.35

    result = {
        "stock_code": stock.code,
        "stock_name": stock.name,
        "bazi_score": round(bazi_score, 1),
        "wuxing_score": round(wuxing_score, 1),
        "timing_score": round(timing_score, 1),
        "composite_score": round(composite, 1),
        "summary": " | ".join(notes),
        "data_source": stock.data_source,
        "wuxing": stock.wuxing or "",
        "sector": stock.sector or "",
    }

    logger.debug(
        "评分完成: %s(%s) → 综合=%.1f (八字=%.1f, 五行=%.1f, 择时=%.1f)",
        stock.code, stock.name,
        result["composite_score"], result["bazi_score"],
        result["wuxing_score"], result["timing_score"],
    )
    return result


def score_all_stocks(
    user: UserProfile,
    target_date: Optional[date] = None,
    top_n: int = 20,
) -> list[dict]:
    """
    对数据库中的所有股票进行评分并排序
    """
    stocks = StockBasic.select()
    logger.info("全量评分开始: 共 %d 只股票", stocks.count())
    results = []
    for stock in stocks:
        try:
            s = score_stock(stock, user, target_date)
            results.append(s)
        except Exception:
            logger.warning("股票 %s 评分失败", stock.code, exc_info=True)
            continue

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    logger.info("全量评分完成: top_n=%d, 最高分=%.1f (%s)",
                min(top_n, len(results)),
                results[0]["composite_score"] if results else 0,
                results[0]["stock_name"] if results else "")
    return results[:top_n]


def save_score_cache(
    stock: StockBasic,
    user: UserProfile,
    scores: dict,
):
    """保存评分到缓存表"""
    try:
        StockScore.create(
            stock=stock,
            user=user,
            calc_date=date.today(),
            bazi_score=scores["bazi_score"],
            wuxing_score=scores["wuxing_score"],
            timing_score=scores["timing_score"],
            composite_score=scores["composite_score"],
            summary=scores["summary"],
        )
    except Exception:
        pass


def get_caishen_ranking(
    user: UserProfile,
    target_date: Optional[date] = None,
    refresh: bool = False,
) -> list[dict]:
    """
    获取财神排行榜

    优先读取缓存，refresh=True 时清除旧缓存并重新计算
    """
    if target_date is None:
        target_date = date.today()

    # refresh=True 时先删除旧缓存
    if refresh:
        StockScore.delete().where(
            StockScore.user == user,
            StockScore.calc_date == target_date,
        ).execute()
        logger.info("已清除旧缓存: user=%s, date=%s", user.name, target_date.isoformat())

    if not refresh:
        cached = StockScore.select().where(
            StockScore.user == user,
            StockScore.calc_date == target_date,
        ).order_by(StockScore.composite_score.desc())

        if cached.count() > 0:
            logger.info("使用缓存评分: user=%s, date=%s, count=%d", user.name, target_date.isoformat(), cached.count())
            results = []
            for c in cached:
                results.append({
                    "stock_code": c.stock.code,
                    "stock_name": c.stock.name,
                    "bazi_score": c.bazi_score,
                    "wuxing_score": c.wuxing_score,
                    "timing_score": c.timing_score,
                    "composite_score": c.composite_score,
                    "summary": c.summary or "",
                    "data_source": c.stock.data_source,
                })
            return results

    # 重新计算
    logger.info("重新计算评分: user=%s, date=%s", user.name, target_date.isoformat())
    results = score_all_stocks(user, target_date)
    for r in results:
        try:
            stock = StockBasic.get(StockBasic.code == r["stock_code"])
            save_score_cache(stock, user, r)
        except Exception:
            pass

    return results


def get_all_scores(
    user: UserProfile,
    target_date: Optional[date] = None,
    refresh: bool = False,
) -> list[dict]:
    """
    获取所有股票的完整评分列表（带 DB 缓存）。

    与 get_caishen_ranking 不同，此函数返回全部股票评分（不限 top_n），
    且结果中包含 wuxing / sector 字段，供分类推荐使用。

    Returns:
        按 composite_score 降序排列的完整评分列表
    """
    if target_date is None:
        target_date = date.today()

    # refresh=True 时先删除旧缓存
    if refresh:
        StockScore.delete().where(
            StockScore.user == user,
            StockScore.calc_date == target_date,
        ).execute()
        logger.info("已清除旧缓存: user=%s, date=%s", user.name, target_date.isoformat())

    if not refresh:
        cached = StockScore.select().where(
            StockScore.user == user,
            StockScore.calc_date == target_date,
        ).order_by(StockScore.composite_score.desc())

        if cached.count() > 0:
            logger.info("使用缓存评分(全量): user=%s, date=%s, count=%d",
                        user.name, target_date.isoformat(), cached.count())
            results = []
            for c in cached:
                results.append({
                    "stock_code": c.stock.code,
                    "stock_name": c.stock.name,
                    "bazi_score": c.bazi_score,
                    "wuxing_score": c.wuxing_score,
                    "timing_score": c.timing_score,
                    "composite_score": c.composite_score,
                    "summary": c.summary or "",
                    "data_source": c.stock.data_source,
                    "wuxing": c.stock.wuxing or "",
                    "sector": c.stock.sector or "",
                })
            return results

    # 重新计算全量
    logger.info("重新计算全量评分: user=%s, date=%s", user.name, target_date.isoformat())
    stocks = StockBasic.select()
    results = []
    for stock in stocks:
        try:
            s = score_stock(stock, user, target_date)
            results.append(s)
            save_score_cache(stock, user, s)
        except Exception:
            logger.warning("股票 %s 评分失败", stock.code, exc_info=True)
            continue

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    logger.info("全量评分完成: %d 只股票", len(results))
    return results


def get_categorized_picks(
    user: UserProfile,
    target_date: Optional[date] = None,
    refresh: bool = False,
    top_n: int = 5,
) -> dict[str, list[dict]]:
    """
    按不同玄学维度分类推荐股票。

    分类维度:
        - bazi:        八字合盘推荐（按 bazi_score 排序）
        - wuxing:      五行匹配推荐（按 wuxing_score 排序）
        - lucky_number: 幸运数字推荐（股票代码含幸运数字）
        - lucky_color:  幸运颜色推荐（板块五行对应幸运颜色）
        - timing:      天干择时推荐（按 timing_score 排序）

    Returns:
        {"bazi": [...], "wuxing": [...], "lucky_number": [...],
         "lucky_color": [...], "timing": [...]}
        每个列表包含 top_n 个 dict，额外包含 "reason" 字段。
    """
    from src.metaphysics.fortune import (
        WUXING_COLORS,
        get_lucky_colors,
        get_lucky_numbers,
    )
    from src.metaphysics.ganzhi import get_daily_signal
    from src.metaphysics.wuxing import get_wuxing_relation

    if target_date is None:
        target_date = date.today()

    all_scores = get_all_scores(user, target_date, refresh)
    if not all_scores:
        return {}

    user_bazi = _user_bazi_from_profile(user)
    lucky_numbers = get_lucky_numbers(user_bazi)
    lucky_colors = get_lucky_colors(user_bazi)
    day_master = user_bazi.day_master or ""

    # 颜色 → 五行 反向映射
    color_to_wuxing: dict[str, str] = {}
    for wx, colors in WUXING_COLORS.items():
        for c in colors:
            color_to_wuxing[c] = wx

    # 幸运颜色对应的五行集合
    lucky_wuxing_from_colors: set[str] = set()
    for c in lucky_colors:
        wx = color_to_wuxing.get(c)
        if wx:
            lucky_wuxing_from_colors.add(wx)

    # 今日日柱信息
    signal = get_daily_signal(target_date)
    day_gan_zhi = f"{signal['day_gan']}{signal['day_zhi']}"
    day_wuxing = signal["day_wuxing"]

    categories: dict[str, list[dict]] = {}

    # ── 1. 八字合盘推荐 ──
    bazi_sorted = sorted(all_scores, key=lambda x: x["bazi_score"], reverse=True)
    categories["bazi"] = []
    for r in bazi_sorted[:top_n]:
        reason = (
            f"八字合盘 {r['bazi_score']:.1f} 分"
            f"（日主「{day_master}」与公司八字契合度高）"
        )
        categories["bazi"].append({**r, "reason": reason})

    # ── 2. 五行匹配推荐 ──
    wuxing_sorted = sorted(all_scores, key=lambda x: x["wuxing_score"], reverse=True)
    categories["wuxing"] = []
    for r in wuxing_sorted[:top_n]:
        stock_wx = r.get("wuxing", "")
        relation = get_wuxing_relation(day_master, stock_wx) if stock_wx and day_master else "未知"
        reason = (
            f"板块五行「{stock_wx or '未知'}」与日主「{day_master}」"
            f"关系为「{relation}」，匹配分 {r['wuxing_score']:.1f}"
        )
        categories["wuxing"].append({**r, "reason": reason})

    # ── 3. 幸运数字推荐 ──
    number_matches = []
    for r in all_scores:
        code = r["stock_code"]
        matched = [n for n in lucky_numbers if str(n) in code]
        if matched:
            number_matches.append({
                **r,
                "matched_numbers": matched,
                "match_count": len(matched),
            })
    number_matches.sort(
        key=lambda x: (x["match_count"], x["composite_score"]),
        reverse=True,
    )
    categories["lucky_number"] = []
    for r in number_matches[:top_n]:
        nums = "、".join(str(n) for n in r["matched_numbers"])
        reason = (
            f"代码 {r['stock_code']} 含幸运数字 {nums}，"
            f"财神指数 {r['composite_score']:.1f}"
        )
        categories["lucky_number"].append({**r, "reason": reason})

    # ── 4. 幸运颜色推荐 ──
    color_matches = []
    for r in all_scores:
        stock_wx = r.get("wuxing", "")
        if stock_wx and stock_wx in lucky_wuxing_from_colors:
            matched_colors = [
                c for c, wx in color_to_wuxing.items()
                if wx == stock_wx and c in lucky_colors
            ]
            color_matches.append({**r, "matched_colors": matched_colors})
    color_matches.sort(key=lambda x: x["wuxing_score"], reverse=True)
    categories["lucky_color"] = []
    for r in color_matches[:top_n]:
        colors_str = "、".join(r["matched_colors"][:3])
        stock_wx = r.get("wuxing", "")
        relation = get_wuxing_relation(day_master, stock_wx) if stock_wx and day_master else "未知"
        reason = (
            f"板块五行「{stock_wx}」对应幸运颜色 {colors_str}，"
            f"与日主「{relation}」，五行匹配 {r['wuxing_score']:.1f}"
        )
        categories["lucky_color"].append({**r, "reason": reason})

    # ── 5. 天干择时推荐 ──
    timing_sorted = sorted(all_scores, key=lambda x: x["timing_score"], reverse=True)
    categories["timing"] = []
    for r in timing_sorted[:top_n]:
        stock_wx = r.get("wuxing", "")
        relation = get_wuxing_relation(day_wuxing, stock_wx) if stock_wx else "未知"
        reason = (
            f"今日 {day_gan_zhi}（{day_wuxing}）与板块「{stock_wx or '未知'}」"
            f"关系「{relation}」，择时分 {r['timing_score']:.1f}"
        )
        categories["timing"].append({**r, "reason": reason})

    logger.info(
        "分类推荐完成: bazi=%d, wuxing=%d, lucky_number=%d, lucky_color=%d, timing=%d",
        len(categories["bazi"]),
        len(categories["wuxing"]),
        len(categories["lucky_number"]),
        len(categories["lucky_color"]),
        len(categories["timing"]),
    )
    return categories


def get_usd_price(
    cny_price: float,
    target_date: Optional[date] = None,
) -> dict:
    """将人民币价格转为美元价格"""
    if target_date is None:
        target_date = date.today()

    rate = ExchangeRate.select().where(
        ExchangeRate.date <= target_date
    ).order_by(ExchangeRate.date.desc()).first()

    if rate:
        usd_price = cny_price / rate.usd_cny
        return {
            "cny": round(cny_price, 4),
            "usd": round(usd_price, 4),
            "rate": rate.usd_cny,
            "rate_source": rate.data_source,
        }
    return {"cny": round(cny_price, 4), "usd": None, "rate": None, "rate_source": "unknown"}


if __name__ == "__main__":
    db.connect(reuse_if_open=True)

    # 测试：创建一个测试用户
    from src.metaphysics.bazi import calc_bazi
    test_bazi = calc_bazi(date(1990, 5, 15), "08:00")

    user, _ = UserProfile.get_or_create(
        birth_date=date(1990, 5, 15),
        defaults={
            "name": "测试用户",
            "birth_time": "08:00",
            "year_gan": test_bazi.year_gan,
            "year_zhi": test_bazi.year_zhi,
            "month_gan": test_bazi.month_gan,
            "month_zhi": test_bazi.month_zhi,
            "day_gan": test_bazi.day_gan,
            "day_zhi": test_bazi.day_zhi,
            "hour_gan": test_bazi.hour_gan,
            "hour_zhi": test_bazi.hour_zhi,
            "day_master": test_bazi.day_master,
            "shengxiao": test_bazi.shengxiao,
            "zodiac": test_bazi.zodiac,
            "xi_shen": ",".join(test_bazi.xi_shen),
            "ji_shen": ",".join(test_bazi.ji_shen),
        },
    )

    # 测试评分
    ranking = get_caishen_ranking(user, refresh=True)
    print("\n=== 财神排行榜 TOP 10 ===")
    for i, r in enumerate(ranking[:10], 1):
        flag = "[假]" if r["data_source"] == "fake" else "[真]"
        print(
            f"  #{i} {r['stock_code']} {r['stock_name']} {flag} | "
            f"综合:{r['composite_score']:.1f} | "
            f"八字:{r['bazi_score']:.1f} | "
            f"五行:{r['wuxing_score']:.1f} | "
            f"择时:{r['timing_score']:.1f}"
        )

    # 测试美元转换
    usd = get_usd_price(10.5)
    print(f"\n10.5 CNY = {usd['usd']} USD (汇率: {usd['rate']})")

    db.close()
