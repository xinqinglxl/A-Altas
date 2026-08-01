"""
数据库模型定义和连接管理
"""

import os
from datetime import date, datetime

from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "a_altas.db")
db = SqliteDatabase(DB_PATH, pragmas={"foreign_keys": 1, "journal_mode": "wal"})


class BaseModel(Model):
    class Meta:
        database = db


class UserProfile(BaseModel):
    """用户八字档案"""

    name = CharField(default="默认用户")
    sex = IntegerField(default=1)  # 1=男, 0=女
    birth_date = DateField()  # 公历出生日期
    birth_time = CharField(max_length=10, default="00:00")  # 出生时间 HH:MM
    is_solar = BooleanField(default=True)  # True=公历, False=农历

    # 八字四柱
    year_gan = CharField(max_length=4)  # 年干
    year_zhi = CharField(max_length=4)  # 年支
    month_gan = CharField(max_length=4)
    month_zhi = CharField(max_length=4)
    day_gan = CharField(max_length=4)
    day_zhi = CharField(max_length=4)
    hour_gan = CharField(max_length=4)
    hour_zhi = CharField(max_length=4)

    # 五行
    day_master = CharField(max_length=4)  # 日主五行
    xi_shen = CharField(max_length=20, null=True)  # 喜用神（金木水火土，逗号分隔）
    ji_shen = CharField(max_length=20, null=True)  # 忌神

    # 星座 & 生肖
    zodiac = CharField(max_length=10, null=True)  # 星座
    shengxiao = CharField(max_length=4, null=True)  # 生肖

    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "user_profile"


class StockBasic(BaseModel):
    """股票基本信息"""

    code = CharField(max_length=10, unique=True)  # 股票代码
    name = CharField(max_length=50)
    founded_date = DateField(null=True)  # 公司成立日期
    ipo_date = DateField(null=True)  # IPO日期
    sector = CharField(max_length=100, null=True)  # 所属板块
    wuxing = CharField(max_length=4, null=True)  # 板块五行属性
    data_source = CharField(max_length=20, default="real")  # real | fake

    class Meta:
        table_name = "stock_basic"


class StockBazi(BaseModel):
    """公司八字排盘结果"""

    stock = ForeignKeyField(StockBasic, backref="bazi", unique=True)
    bazi_type = CharField(max_length=10)  # founded | ipo
    year_gan = CharField(max_length=4)
    year_zhi = CharField(max_length=4)
    month_gan = CharField(max_length=4)
    month_zhi = CharField(max_length=4)
    day_gan = CharField(max_length=4)
    day_zhi = CharField(max_length=4)
    hour_gan = CharField(max_length=4, null=True)  # 无具体时间则用默认子时
    hour_zhi = CharField(max_length=4, null=True)
    day_master = CharField(max_length=4)  # 日主五行

    class Meta:
        table_name = "stock_bazi"
        indexes = ((("stock", "bazi_type"), True),)


class SectorWuxing(BaseModel):
    """板块五行映射表"""

    sector_name = CharField(max_length=100, unique=True)  # 板块名称
    wuxing = CharField(max_length=4)  # 金木水火土
    parent_wuxing = CharField(max_length=4, null=True)  # 父板块五行

    class Meta:
        table_name = "sector_wuxing"


class ExchangeRate(BaseModel):
    """汇率数据"""

    date = DateField()
    usd_cny = FloatField()  # 1 USD = ? CNY
    data_source = CharField(max_length=20, default="real")

    class Meta:
        table_name = "exchange_rate"
        indexes = ((("date",), True),)


class DailySignal(BaseModel):
    """每日玄学择时信号"""

    date = DateField(unique=True)

    # 日柱
    day_gan = CharField(max_length=4)
    day_zhi = CharField(max_length=4)
    day_wuxing = CharField(max_length=4)  # 日干五行

    # 黄历
    yi = TextField(null=True)  # 宜
    ji = TextField(null=True)  # 忌
    caishen = CharField(max_length=10, null=True)  # 财神方位

    # 节气
    jieqi = CharField(max_length=10, null=True)  # 若是节气日则填名称

    # 信号
    trade_signal = CharField(max_length=10, null=True)  # 宜买入/宜观望/忌交易
    recommended_wuxing = CharField(max_length=20, null=True)  # 推荐五行板块

    class Meta:
        table_name = "daily_signal"


class StockScore(BaseModel):
    """股票玄学评分缓存"""

    stock = ForeignKeyField(StockBasic, backref="scores")
    user = ForeignKeyField(UserProfile, backref="scores")
    calc_date = DateField(default=date.today)

    bazi_score = FloatField(default=0)  # 八字合盘分 0-100
    wuxing_score = FloatField(default=0)  # 五行匹配分 0-100
    timing_score = FloatField(default=0)  # 天干择时分 0-100
    composite_score = FloatField(default=0)  # 综合财神指数 0-100

    summary = TextField(null=True)  # 简短点评

    class Meta:
        table_name = "stock_score"
        indexes = ((("stock", "user", "calc_date"), True),)


def init_db():
    """初始化数据库，创建所有表"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db.connect()
    db.create_tables(
        [
            UserProfile,
            StockBasic,
            StockBazi,
            SectorWuxing,
            ExchangeRate,
            DailySignal,
            StockScore,
        ],
        safe=True,
    )
    db.close()


if __name__ == "__main__":
    init_db()
    print(f"数据库初始化完成: {DB_PATH}")
