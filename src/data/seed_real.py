"""
真实数据填充模块
使用可用接口填充真实数据：
- 汇率: currency_boc_safe (国家外汇管理局, 最新至2026-07)
- 股票列表: index_stock_cons (沪深300成分股)
- 上市日期+行业: Baostock (支持全部A股含科创板, CSRC证监会行业分类)
- K线: Baostock > 新浪 > 腾讯 (自动回退)
"""

import time
from datetime import date, datetime, timedelta

import pandas as pd

from src.data.db import (
    DailySignal,
    ExchangeRate,
    SectorWuxing,
    StockBasic,
    StockBazi,
    StockScore,
    UserProfile,
    db,
    init_db,
)
from src.data.exchange import get_usd_cny_from_safe
from src.data.sources import baostock_get_stock_info, _baostock_logout
from src.metaphysics.bazi import calc_company_bazi
from src.metaphysics.ganzhi import generate_daily_signals
from src.metaphysics.wuxing import (
    CSRC_INDUSTRY_WUXING_MAP,
    SECTOR_WUXING_MAP,
    get_csrc_industry_wuxing,
    get_sector_wuxing,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 请求间隔（秒），防止被ban
API_SLEEP = 0.3


def seed_exchange_rates_real():
    """填充真实汇率数据（来自国家外汇管理局）"""
    logger.info("开始填充汇率数据...")

    df = get_usd_cny_from_safe()

    if df.empty:
        logger.error("无法获取汇率数据，跳过")
        return

    count = 0
    with db.atomic():
        for _, row in df.iterrows():
            d = row["date"]
            if isinstance(d, pd.Timestamp):
                d = d.date()
            elif isinstance(d, datetime):
                d = d.date()

            _, created = ExchangeRate.get_or_create(
                date=d,
                defaults={
                    "usd_cny": round(float(row["usd_cny"]), 4),
                    "data_source": "real",
                },
            )
            if created:
                count += 1

    total = ExchangeRate.select().count()
    latest = ExchangeRate.select().order_by(ExchangeRate.date.desc()).first()
    logger.info("汇率填充完成: 新增 %d 条, 总计 %d 条, 最新日期: %s, 汇率: %s",
                count, total,
                latest.date if latest else "N/A",
                latest.usd_cny if latest else "N/A")


def get_hs300_stocks():
    """获取沪深300成分股列表"""
    import akshare as ak

    logger.info("获取沪深300成分股...")
    try:
        df = ak.index_stock_cons(symbol="000300")
        logger.info("获取到 %d 只沪深300成分股", len(df))
        time.sleep(1.0)
        return df
    except Exception:
        logger.error("获取沪深300成分股失败", exc_info=True)
        return None


def guess_sector_from_name(name: str) -> tuple[str, str]:
    """
    根据股票名称猜测板块（当 Baostock 无行业数据时的后备方案）
    返回板块名和五行
    """
    name = name.strip()
    if "银行" in name:
        return "银行", "金"
    if "证券" in name or "中信" in name or "华泰" in name:
        return "证券", "金"
    if "保险" in name:
        return "保险", "金"
    if "地产" in name or "置业" in name or "万科" in name or "保利" in name:
        return "房地产开发", "土"
    if "钢" in name or "宝武" in name:
        return "钢铁", "金"
    if "电力" in name or "核电" in name:
        return "电力", "火"
    if "煤" in name:
        return "煤炭", "土"
    if "药" in name or "医药" in name or "生物" in name or "医疗" in name:
        return "中药", "木"
    if "酒" in name or "乳" in name or "食品" in name:
        return "饮料制造", "水"
    if "芯" in name or "半导体" in name or "科技" in name or "电子" in name:
        return "半导体", "火"
    if "汽车" in name or "车" in name:
        return "汽车零部件", "金"
    return "通用设备", "金"


def seed_stocks_real(max_stocks: int = 50):
    """
    填充真实股票数据：
    - 沪深300成分股的代码、名称（来自 akshare）
    - 真实上市日期 + CSRC行业分类（来自 Baostock，支持全部A股含科创板）
    - 公司成立日期仍为模拟数据（Baostock 不提供）
    """
    import random

    # 1. 获取沪深300成分股
    hs300_df = get_hs300_stocks()
    if hs300_df is None or hs300_df.empty:
        logger.error("无法获取沪深300成分股，终止股票数据填充")
        return

    # 2. 遍历成分股，用 Baostock 获取 IPO 日期和行业
    stocks = []
    success_count = 0
    for idx, row in hs300_df.iterrows():
        code = str(row["品种代码"]).zfill(6)
        name = str(row["品种名称"]).strip()

        # 从 Baostock 获取真实 IPO 日期和行业
        info = baostock_get_stock_info(code)

        if info and info.get("ipo_date"):
            ipo_date = info["ipo_date"]
            industry = info.get("industry")

            if industry:
                # Baostock 返回 CSRC 行业分类如 'C15酒、饮料和精制茶制造业'
                wuxing = get_csrc_industry_wuxing(industry)
                sector = industry
                if not wuxing:
                    # CSRC 映射失败，尝试名称猜测
                    sector, wuxing = guess_sector_from_name(name)
                    data_source = "partial"
                else:
                    data_source = "real"  # IPO + 行业都是真实的
            else:
                # 无行业数据，用名称猜测
                sector, wuxing = guess_sector_from_name(name)
                data_source = "partial"  # IPO真实，行业为猜测
        else:
            # Baostock 获取失败，使用假数据
            logger.warning("  Baostock 获取 %s 失败，使用假数据", code)
            ipo_year = random.randint(2010, 2024)
            ipo_month = random.randint(1, 12)
            ipo_day = random.randint(1, 28)
            ipo_date = date(ipo_year, ipo_month, ipo_day)
            sector, wuxing = guess_sector_from_name(name)
            data_source = "fake"

        # 公司成立日期（假数据，Baostock 不提供）
        years_before = random.randint(3, 15)
        days_before = random.randint(0, 365)
        founded_date = ipo_date - timedelta(days=int(365.25 * years_before + days_before))

        real_name = info.get("name", name) if info else name

        stocks.append({
            "code": code,
            "name": real_name,
            "founded_date": founded_date,
            "ipo_date": ipo_date,
            "sector": sector,
            "wuxing": wuxing,
            "data_source": data_source,
        })
        success_count += 1

        if len(stocks) >= max_stocks:
            break

        time.sleep(API_SLEEP)

    logger.info("Baostock 获取完成: %d/%d 成功", success_count, len(stocks))
    logger.info("准备写入 %d 只股票", len(stocks))

    # 5. 写入数据库
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

            if created or not stock.bazi.exists():
                # 清除旧八字数据
                StockBazi.delete().where(StockBazi.stock == stock).execute()

                # 排公司八字（成立日）
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

                # 排上市八字
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

    # 统计
    real_count = sum(1 for s in stocks if s["data_source"] == "real")
    partial_count = sum(1 for s in stocks if s["data_source"] == "partial")
    fake_count = sum(1 for s in stocks if s["data_source"] == "fake")
    logger.info("股票数据填充完成: 共 %d 只 (真实: %d, 部分真实: %d, 假数据: %d)",
                len(stocks), real_count, partial_count, fake_count)

    # 打印部分结果
    for s in stocks[:10]:
        logger.info("  %s %s | IPO: %s | 行业: %s(%s) | 来源: %s",
                     s["code"], s["name"], s["ipo_date"],
                     s["sector"], s["wuxing"], s["data_source"])


def seed_sector_wuxing():
    """填充板块五行映射表（静态数据 + CSRC行业大类）"""
    with db.atomic():
        # 申万板块映射
        for sector, wuxing in SECTOR_WUXING_MAP.items():
            SectorWuxing.get_or_create(
                sector_name=sector,
                defaults={"wuxing": wuxing},
            )
        # CSRC行业大类映射
        for code, wuxing in CSRC_INDUSTRY_WUXING_MAP.items():
            SectorWuxing.get_or_create(
                sector_name=f"CSRC-{code}",
                defaults={"wuxing": wuxing},
            )
    logger.info("已填充 %d 条板块五行映射", len(SECTOR_WUXING_MAP) + len(CSRC_INDUSTRY_WUXING_MAP))


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
                    "is_trading_day": s.get("is_trading_day", True),
                    "non_trading_reason": s.get("non_trading_reason"),
                },
            )
            if created:
                count += 1
    logger.info("已生成 %d 条每日信号", count)


def seed_all_real(max_stocks: int = 50):
    """使用真实数据一键初始化"""
    logger.info("=" * 50)
    logger.info("A-ALTAS 真实数据初始化开始")
    logger.info("=" * 50)

    # 初始化数据库表（先 drop 再 create，确保表结构最新）
    db.connect(reuse_if_open=True)
    db.drop_tables(
        [StockScore, StockBazi, StockBasic, DailySignal, ExchangeRate, SectorWuxing, UserProfile],
        safe=True,
    )
    db.create_tables(
        [UserProfile, SectorWuxing, ExchangeRate, DailySignal, StockBasic, StockBazi, StockScore],
        safe=True,
    )
    db.close()
    logger.info("[1/5] 数据库表就绪（已重建）")

    # 清空旧数据（表已重建，但以防万一）
    db.connect(reuse_if_open=True)
    tables = [StockScore, StockBazi, StockBasic, DailySignal, ExchangeRate, SectorWuxing]
    for t in tables:
        t.delete().execute()
    logger.info("旧数据已清空")

    seed_sector_wuxing()
    logger.info("[2/5] 板块五行映射完成")

    seed_exchange_rates_real()
    logger.info("[3/5] 汇率数据完成")

    seed_stocks_real(max_stocks=max_stocks)
    logger.info("[4/5] 股票数据完成")

    seed_daily_signals()
    logger.info("[5/5] 每日信号完成")

    # 统计
    logger.info("=" * 50)
    logger.info("数据统计:")
    logger.info("  汇率记录: %d 条", ExchangeRate.select().count())
    logger.info("  股票数量: %d 只", StockBasic.select().count())
    logger.info("  公司八字: %d 条", StockBazi.select().count())
    logger.info("  板块映射: %d 条", SectorWuxing.select().count())
    logger.info("  每日信号: %d 条", DailySignal.select().count())

    # 数据来源统计
    real = StockBasic.select().where(StockBasic.data_source == "real").count()
    partial = StockBasic.select().where(StockBasic.data_source == "partial").count()
    fake = StockBasic.select().where(StockBasic.data_source == "fake").count()
    logger.info("  数据来源 — 真实: %d, 部分真实: %d, 假数据: %d", real, partial, fake)

    real_rate = ExchangeRate.select().where(ExchangeRate.data_source == "real").count()
    logger.info("  汇率来源 — 真实: %d", real_rate)

    logger.info("=" * 50)
    logger.info("A-ALTAS 真实数据初始化完成！")
    logger.info("=" * 50)

    # 登出 Baostock
    _baostock_logout()

    db.close()


if __name__ == "__main__":
    seed_all_real(max_stocks=50)
