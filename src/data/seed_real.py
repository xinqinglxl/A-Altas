"""
真实数据填充模块
使用可用接口填充真实数据：
- 汇率: currency_boc_safe (国家外汇管理局, 最新至2026-07)
- 股票列表: index_stock_cons (沪深300成分股)
- 上市日期: stock_info_sh_name_code / stock_info_sz_name_code
- 行业信息: stock_info_sz_name_code (深市) / efinance (沪市补充)
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
API_SLEEP = 2.0


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
        time.sleep(API_SLEEP)
        return df
    except Exception:
        logger.error("获取沪深300成分股失败", exc_info=True)
        return None


def get_sh_stock_list():
    """获取沪市股票列表（含上市日期）"""
    import akshare as ak

    logger.info("获取沪市股票列表...")
    try:
        df = ak.stock_info_sh_name_code()
        logger.info("获取到 %d 只沪市股票", len(df))
        time.sleep(API_SLEEP)
        return df
    except Exception:
        logger.error("获取沪市股票列表失败", exc_info=True)
        return None


def get_sz_stock_list():
    """获取深市股票列表（含上市日期+行业）"""
    import akshare as ak

    logger.info("获取深市股票列表...")
    try:
        df = ak.stock_info_sz_name_code(symbol="A股列表")
        logger.info("获取到 %d 只深市股票", len(df))
        time.sleep(API_SLEEP)
        return df
    except Exception:
        logger.error("获取深市股票列表失败", exc_info=True)
        return None


def build_stock_info_dict(sh_df, sz_df):
    """
    将沪深交易所数据合并为统一字典
    key: 股票代码, value: {name, ipo_date, industry}
    """
    info_dict = {}

    # 沪市
    if sh_df is not None and not sh_df.empty:
        for _, row in sh_df.iterrows():
            code = str(row["证券代码"]).zfill(6)
            name = str(row["证券简称"]).strip()
            ipo_date = None
            try:
                ipo_str = str(row.get("上市日期", ""))
                if ipo_str and ipo_str != "nan":
                    ipo_date = datetime.strptime(ipo_str, "%Y-%m-%d").date()
            except Exception:
                pass
            info_dict[code] = {
                "name": name,
                "ipo_date": ipo_date,
                "industry": None,  # 沪市列表无行业信息
                "exchange": "SH",
            }

    # 深市（补充行业信息）
    if sz_df is not None and not sz_df.empty:
        for _, row in sz_df.iterrows():
            code = str(row["A股代码"]).zfill(6)
            name = str(row["A股简称"]).strip()
            ipo_date = None
            try:
                ipo_str = str(row.get("A股上市日期", ""))
                if ipo_str and ipo_str != "nan":
                    ipo_date = datetime.strptime(ipo_str, "%Y-%m-%d").date()
            except Exception:
                pass
            industry = str(row.get("所属行业", "")).strip()
            if industry == "nan":
                industry = None

            if code in info_dict:
                # 已有沪市数据，补充行业
                if industry:
                    info_dict[code]["industry"] = industry
            else:
                info_dict[code] = {
                    "name": name,
                    "ipo_date": ipo_date,
                    "industry": industry,
                    "exchange": "SZ",
                }

    logger.info("合并后共 %d 只股票信息", len(info_dict))
    return info_dict


def guess_sector_from_name(name: str) -> str:
    """
    根据股票名称猜测板块（当无行业数据时的后备方案）
    返回板块名和五行
    """
    name = name.strip()
    # 银行
    if "银行" in name:
        return "银行", "金"
    # 证券/保险
    if "证券" in name or "中信" in name or "华泰" in name:
        return "证券", "金"
    if "保险" in name:
        return "保险", "金"
    # 地产
    if "地产" in name or "置业" in name or "万科" in name or "保利" in name:
        return "房地产开发", "土"
    # 钢铁
    if "钢" in name or "宝武" in name:
        return "钢铁", "金"
    # 电力
    if "电力" in name or "核电" in name:
        return "电力", "火"
    # 煤炭
    if "煤" in name:
        return "煤炭", "土"
    # 医药
    if "药" in name or "医药" in name or "生物" in name or "医疗" in name:
        return "中药", "木"
    # 食品饮料
    if "酒" in name or "乳" in name or "食品" in name:
        return "饮料制造", "水"
    # 半导体/科技
    if "芯" in name or "半导体" in name or "科技" in name or "电子" in name:
        return "半导体", "火"
    # 汽车
    if "汽车" in name or "车" in name:
        return "汽车零部件", "金"
    # 默认
    return "通用设备", "金"


def get_industry_from_efinance(code: str) -> str | None:
    """
    通过 efinance 获取个股行业信息
    返回行业名称（如 '半导体', '银行', '化学制药'）
    """
    try:
        import efinance as ef
        info = ef.stock.get_base_info(code)
        if info is not None and "所处行业" in info.index:
            industry = str(info["所处行业"]).strip()
            if industry and industry != "nan":
                return industry
    except Exception:
        logger.debug("efinance 获取 %s 行业失败", code, exc_info=True)
    return None


def map_efinance_industry(industry: str) -> tuple[str, str]:
    """
    将 efinance 的行业名称映射到申万板块名和五行
    efinance 行业如: '半导体', '银行', '化学制药', '元件', '生物制品'
    """
    # 直接匹配申万板块名
    if industry in SECTOR_WUXING_MAP:
        return industry, SECTOR_WUXING_MAP[industry]

    # 模糊匹配
    for sector, wx in SECTOR_WUXING_MAP.items():
        if sector in industry or industry in sector:
            return sector, wx

    # 关键词匹配
    keyword_map = {
        "银行": ("银行", "金"),
        "证券": ("证券", "金"),
        "保险": ("保险", "金"),
        "地产": ("房地产开发", "土"),
        "钢铁": ("钢铁", "金"),
        "电力": ("电力", "火"),
        "煤炭": ("煤炭", "土"),
        "药": ("中药", "木"),
        "生物": ("生物制品", "木"),
        "医疗": ("中药", "木"),
        "酒": ("饮料制造", "水"),
        "乳": ("饮料制造", "水"),
        "食品": ("饮料制造", "水"),
        "芯": ("半导体", "火"),
        "半导体": ("半导体", "火"),
        "电子": ("电子元件", "火"),
        "元件": ("电子元件", "火"),
        "汽车": ("汽车零部件", "金"),
        "光伏": ("光伏设备", "火"),
        "风电": ("风电设备", "火"),
        "军工": ("军工装备", "火"),
        "石油": ("石油石化", "火"),
        "化工": ("化学制品", "土"),
        "建材": ("建筑材料", "土"),
        "水泥": ("水泥", "土"),
        "建筑": ("基础建设", "土"),
        "航运": ("航运港口", "水"),
        "物流": ("物流", "水"),
        "交通": ("铁路公路", "水"),
        "旅游": ("旅游及景区", "水"),
        "酒店": ("酒店餐饮", "水"),
        "软件": ("计算机设备", "火"),
        "通信": ("通信设备", "火"),
        "传媒": ("数字媒体", "火"),
        "游戏": ("游戏", "火"),
        "农业": ("种植业", "木"),
        "林业": ("林业", "木"),
        "环保": ("环保", "水"),
        "水务": ("水务", "水"),
    }
    for keyword, (sector, wx) in keyword_map.items():
        if keyword in industry:
            return sector, wx

    return industry, "金"  # 默认金


def seed_stocks_real(max_stocks: int = 50):
    """
    填充真实股票数据：
    - 沪深300成分股的代码、名称
    - 真实上市日期（来自交易所数据）
    - 真实行业信息（深市有，沪市用名称猜测）
    - 公司成立日期仍为模拟数据（交易所不提供）
    """
    import random

    # 1. 获取沪深300成分股
    hs300_df = get_hs300_stocks()
    if hs300_df is None or hs300_df.empty:
        logger.error("无法获取沪深300成分股，终止股票数据填充")
        return

    # 2. 获取沪深交易所股票列表
    sh_df = get_sh_stock_list()
    sz_df = get_sz_stock_list()

    # 3. 合并为统一字典
    info_dict = build_stock_info_dict(sh_df, sz_df)

    # 4. 遍历沪深300成分股，填充数据
    stocks = []
    for _, row in hs300_df.iterrows():
        code = str(row["品种代码"]).zfill(6)
        name = str(row["品种名称"]).strip()

        # 从交易所数据中查找详细信息
        info = info_dict.get(code, {})
        real_name = info.get("name", name)
        ipo_date = info.get("ipo_date")
        industry = info.get("industry")

        data_source = "real" if ipo_date else "fake"

        # 如果没有真实IPO日期，生成假日期
        if not ipo_date:
            ipo_year = random.randint(2010, 2024)
            ipo_month = random.randint(1, 12)
            ipo_day = random.randint(1, 28)
            ipo_date = date(ipo_year, ipo_month, ipo_day)

        # 确定板块和五行
        if industry:
            # 深市有CSRC行业信息
            wuxing = get_csrc_industry_wuxing(industry)
            sector = industry
            if not wuxing:
                sector, wuxing = guess_sector_from_name(real_name)
                data_source = "partial"
        else:
            # 无交易所行业信息，尝试 efinance
            ef_industry = get_industry_from_efinance(code)
            if ef_industry:
                sector, wuxing = map_efinance_industry(ef_industry)
                logger.debug("  %s efinance行业: %s → %s(%s)", code, ef_industry, sector, wuxing)
                # 行业来自efinance，上市日期可能来自交易所或假数据
                if data_source == "fake":
                    data_source = "partial"  # 行业真实，IPO日期假
                # 如果IPO真实+行业真实，保持real
            else:
                # efinance也获取失败，用名称猜测
                sector, wuxing = guess_sector_from_name(real_name)
                if data_source == "real":
                    data_source = "partial"  # 上市日期真实，行业为猜测
            time.sleep(1.0)  # efinance 请求间隔

        # 公司成立日期（假数据，交易所不提供）
        years_before = random.randint(3, 15)
        days_before = random.randint(0, 365)
        founded_date = ipo_date - timedelta(days=int(365.25 * years_before + days_before))

        stocks.append({
            "code": code,
            "name": real_name,
            "founded_date": founded_date,
            "ipo_date": ipo_date,
            "sector": sector,
            "wuxing": wuxing,
            "data_source": data_source,
        })

        if len(stocks) >= max_stocks:
            break

    logger.info("准备写入 %d 只股票（含真实上市日期）", len(stocks))

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

    db.close()


if __name__ == "__main__":
    seed_all_real(max_stocks=50)
