"""
数据填充模块
负责从真实数据源采集数据，并对无法获取的数据生成假数据并标注
"""

import random
from datetime import date, datetime, timedelta

from src.data.db import (
    DailySignal,
    ExchangeRate,
    SectorWuxing,
    StockBasic,
    StockBazi,
    UserProfile,
    db,
    init_db,
)
from src.data.exchange import generate_fake_exchange_rates, get_usd_cny_history
from src.metaphysics.bazi import BaziResult, calc_bazi, calc_company_bazi
from src.metaphysics.ganzhi import generate_daily_signals
from src.metaphysics.wuxing import SECTOR_WUXING_MAP
from src.utils.logger import get_logger

logger = get_logger(__name__)


def seed_sector_wuxing():
    """填充板块五行映射表（静态数据）"""
    with db.atomic():
        for sector, wuxing in SECTOR_WUXING_MAP.items():
            SectorWuxing.get_or_create(
                sector_name=sector,
                defaults={"wuxing": wuxing},
            )
    logger.info("已填充 %d 条板块五行映射", len(SECTOR_WUXING_MAP))


def seed_exchange_rates():
    """填充汇率数据（优先真实数据，失败则用假数据）"""
    df = get_usd_cny_history()

    if df.empty or len(df) < 100:
        logger.info("真实汇率数据不足，使用模拟数据")
        fake_data = generate_fake_exchange_rates(days=400)
        source = "fake"
    else:
        fake_data = [
            {"date": row["date"].date() if hasattr(row["date"], "date") else row["date"],
             "usd_cny": float(row["usd_cny"])}
            for _, row in df.iterrows()
        ]
        source = "real"

    with db.atomic():
        for item in fake_data:
            if isinstance(item["date"], datetime):
                item["date"] = item["date"].date()
            ExchangeRate.get_or_create(
                date=item["date"],
                defaults={
                    "usd_cny": item["usd_cny"],
                    "data_source": source,
                },
            )

    count = ExchangeRate.select().count()
    logger.info("已填充 %d 条汇率记录 (来源: %s)", count, source)


def seed_stocks_enhanced():
    """
    填充股票数据：
    - 真实数据：股票代码、名称、上市日期
    - 假数据：公司成立日期（基于上市日期估算）、高管星座
    """
    import akshare as ak

    # 使用真实的沪深300成分股作为样本
    try:
        df = ak.index_stock_cons(symbol="000300")
        if df.empty:
            raise ValueError("empty")
        logger.info("成功获取沪深300成分股数据")
    except Exception:
        logger.warning("获取沪深300成分股失败，使用预设股票列表")
        # 备用：直接用预设股票列表
        preset = [
            ("000001", "平安银行"), ("000002", "万科A"), ("000858", "五粮液"),
            ("002415", "海康威视"), ("300750", "宁德时代"), ("600519", "贵州茅台"),
            ("600036", "招商银行"), ("601318", "中国平安"), ("600276", "恒瑞医药"),
            ("002594", "比亚迪"), ("300059", "东方财富"), ("601012", "隆基绿能"),
            ("600900", "长江电力"), ("000333", "美的集团"), ("002475", "立讯精密"),
            ("600809", "山西汾酒"), ("300124", "汇川技术"), ("603259", "药明康德"),
            ("688111", "金山办公"), ("600030", "中信证券"),
        ]
        df = type("obj", (object,), {
            "iterrows": lambda self: ((i, type("r", (object,), {
                "品种代码": c, "品种名称": n
            })()) for i, (c, n) in enumerate(preset))
        })()

    # 获取沪深300里每只股票的上市日期
    stocks = []
    for _, row in df.iterrows():
        code = str(row["品种代码"])
        name = str(row["品种名称"])

        # 尝试获取真实上市日期
        ipo_date = None
        data_source = "fake"  # 默认假数据
        try:
            info = ak.stock_individual_info_em(symbol=code)
            if not info.empty:
                info_dict = dict(zip(info["item"], info["value"]))
                ipo_str = info_dict.get("上市日期", "")
                if ipo_str and ipo_str != "None":
                    ipo_date = datetime.strptime(str(ipo_str), "%Y%m%d").date()
                    data_source = "real"
        except Exception:
            logger.debug("获取股票 %s %s 上市日期失败", code, name)

        # 假数据：无真实IPO日期时生成合理假日期
        if not ipo_date:
            ipo_year = random.randint(2010, 2024)
            ipo_month = random.randint(1, 12)
            ipo_day = random.randint(1, 28)
            ipo_date = date(ipo_year, ipo_month, ipo_day)

        # 假数据：成立日期（基于IPO日期往前推3~15年）
        years_before = random.randint(3, 15)
        days_before = random.randint(0, 365)
        founded_date = ipo_date - timedelta(days=int(365.25 * years_before + days_before))
        founded_date_str = "模拟"

        # 假数据：随机分配板块
        sector_list = list(SECTOR_WUXING_MAP.keys())
        sector = random.choice(sector_list) if sector_list else "银行"
        wuxing = SECTOR_WUXING_MAP.get(sector, "")

        stocks.append({
            "code": code,
            "name": name,
            "founded_date": founded_date,
            "ipo_date": ipo_date,
            "sector": sector,
            "wuxing": wuxing,
            "data_source": data_source,
        })

        # 避免过量请求
        if len(stocks) >= 50:
            break

    logger.debug("准备写入 %d 只股票", len(stocks))

    # 写入数据库
    with db.atomic():
        for s in stocks:
            stock, created = StockBasic.get_or_create(
                code=s["code"],
                defaults={
                    "name": s["name"],
                    "founded_date": s["founded_date"],
                    "ipo_date": s["ipo_date"],
                    "sector": s["sector"],
                    "wuxing": s["wuxing"],
                    "data_source": s["data_source"],
                },
            )
            if created:
                # 排公司八字
                if s["founded_date"]:
                    try:
                        bazi = calc_company_bazi(s["founded_date"])
                        StockBazi.create(
                            stock=stock,
                            bazi_type="founded",
                            year_gan=bazi.year_gan,
                            year_zhi=bazi.year_zhi,
                            month_gan=bazi.month_gan,
                            month_zhi=bazi.month_zhi,
                            day_gan=bazi.day_gan,
                            day_zhi=bazi.day_zhi,
                            hour_gan=bazi.hour_gan,
                            hour_zhi=bazi.hour_zhi,
                            day_master=bazi.day_master,
                        )
                    except Exception:
                        logger.warning("公司 %s 成立八字排盘失败", s["code"], exc_info=True)
                # 上市八字
                if s["ipo_date"]:
                    try:
                        bazi = calc_company_bazi(s["ipo_date"])
                        StockBazi.get_or_create(
                            stock=stock,
                            bazi_type="ipo",
                            defaults={
                                "year_gan": bazi.year_gan,
                                "year_zhi": bazi.year_zhi,
                                "month_gan": bazi.month_gan,
                                "month_zhi": bazi.month_zhi,
                                "day_gan": bazi.day_gan,
                                "day_zhi": bazi.day_zhi,
                                "hour_gan": bazi.hour_gan,
                                "hour_zhi": bazi.hour_zhi,
                                "day_master": bazi.day_master,
                            },
                        )
                    except Exception:
                        logger.warning("公司 %s 上市八字排盘失败", s["code"], exc_info=True)

    real_count = sum(1 for s in stocks if s["data_source"] == "real")
    fake_count = sum(1 for s in stocks if s["data_source"] == "fake")
    logger.info("已填充 %d 只股票 (真实: %d, 部分假数据: %d)", len(stocks), real_count, fake_count)


def seed_daily_signals(days: int = 90):
    """预生成每日择时信号"""
    today = date.today()
    start = today - timedelta(days=days)
    signals = generate_daily_signals(start, days + 30)

    with db.atomic():
        count = 0
        for s in signals:
            d = date.fromisoformat(s["date"])
            yi_str = ",".join(s["yi"]) if s["yi"] else None
            ji_str = ",".join(s["ji"]) if s["ji"] else None
            rec_str = ",".join(s["recommended_wuxing"]) if s["recommended_wuxing"] else None

            _, created = DailySignal.get_or_create(
                date=d,
                defaults={
                    "day_gan": s["day_gan"],
                    "day_zhi": s["day_zhi"],
                    "day_wuxing": s["day_wuxing"],
                    "yi": yi_str,
                    "ji": ji_str,
                    "caishen": s.get("caishen"),
                    "jieqi": s.get("jieqi"),
                    "trade_signal": s["trade_signal"],
                    "recommended_wuxing": rec_str,
                },
            )
            if created:
                count += 1
    logger.info("已生成 %d 条每日信号", count)


def seed_all():
    """一键初始化所有数据"""
    logger.info("=" * 40)
    logger.info("A-ALTAS 数据初始化开始")
    logger.info("=" * 40)

    init_db()
    logger.info("[1/4] 数据库表创建完成")

    seed_sector_wuxing()
    logger.info("[2/4] 板块五行映射完成")

    seed_exchange_rates()
    logger.info("[3/4] 汇率数据完成")

    seed_stocks_enhanced()
    seed_daily_signals()
    logger.info("[4/4] 股票数据 & 每日信号完成")

    logger.info("=" * 40)
    logger.info("A-ALTAS 数据初始化完成！")
    logger.info("=" * 40)


if __name__ == "__main__":
    seed_all()
