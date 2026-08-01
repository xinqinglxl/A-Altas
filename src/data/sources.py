"""
统一数据源模块 —— 封装 Baostock / 新浪 / 腾讯 三大免费数据源

数据源优先级:
  K线: Baostock > 新浪 > 腾讯 > 假数据
  IPO日期/行业: Baostock (唯一能获取科创板的源)
  实时行情: 新浪 > 腾讯
  汇率: 外汇管理局(已集成) > 新浪
"""

import json
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 请求间隔（秒）
API_SLEEP = 0.5

# HTTP 请求头
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}
TENCENT_HEADERS = {"Referer": "https://gu.qq.com"}
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ──────────────────────────────────────────────
#  Baostock 数据源
# ──────────────────────────────────────────────

_bs_logged_in = False


def _baostock_login():
    """登录 Baostock（全局只需一次）"""
    global _bs_logged_in
    if _bs_logged_in:
        return True
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code == "0":
            _bs_logged_in = True
            logger.info("Baostock 登录成功")
            return True
        else:
            logger.error("Baostock 登录失败: %s %s", lg.error_code, lg.error_msg)
            return False
    except Exception:
        logger.error("Baostock 登录异常", exc_info=True)
        return False


def _baostock_logout():
    """登出 Baostock"""
    global _bs_logged_in
    if _bs_logged_in:
        try:
            import baostock as bs

            bs.logout()
            _bs_logged_in = False
        except Exception:
            pass


# ──────────────────────────────────────────────
#  Baostock: 股票基础信息 (IPO日期 + 行业)
# ──────────────────────────────────────────────


def baostock_get_stock_info(code: str) -> Optional[dict]:
    """
    通过 Baostock 获取单只股票的基础信息

    Args:
        code: 6位股票代码，如 '600519', '000001', '688072'

    Returns:
        {code, name, ipo_date, out_date, type, status, industry}
    """
    if not _baostock_login():
        return None

    import baostock as bs

    # 转换代码格式 600519 -> sh.600519
    if code.startswith(("6", "9")):
        bs_code = f"sh.{code}"
    else:
        bs_code = f"sz.{code}"

    result = {"code": code, "name": None, "ipo_date": None,
              "industry": None, "exchange": "SH" if code.startswith(("6", "9")) else "SZ"}

    try:
        # 股票基本信息（含 IPO 日期）
        rs = bs.query_stock_basic(code=bs_code)
        if rs.error_code != "0":
            logger.warning("Baostock query_stock_basic 失败: %s %s", bs_code, rs.error_msg)
            return None

        while rs.next():
            row = rs.get_row_data()
            # row: [code, code_name, ipoDate, outDate, type, status]
            result["name"] = row[1] if len(row) > 1 else None
            if len(row) > 2 and row[2]:
                try:
                    result["ipo_date"] = datetime.strptime(row[2], "%Y-%m-%d").date()
                except ValueError:
                    pass
            if len(row) > 3 and row[3]:
                try:
                    result["out_date"] = datetime.strptime(row[3], "%Y-%m-%d").date()
                except ValueError:
                    pass
            result["status"] = row[5] if len(row) > 5 else None

        # 行业分类（CSRC 证监会行业分类）
        rs2 = bs.query_stock_industry(code=bs_code)
        if rs2.error_code == "0":
            while rs2.next():
                row2 = rs2.get_row_data()
                # row2: [updateDate, code, code_name, industry, industryClassification]
                if len(row2) > 3 and row2[3]:
                    result["industry"] = row2[3]
                    result["industry_classification"] = row2[4] if len(row2) > 4 else None

        logger.debug("Baostock 获取股票信息: %s %s IPO=%s 行业=%s",
                     code, result.get("name"), result.get("ipo_date"), result.get("industry"))
        return result

    except Exception:
        logger.error("Baostock 获取股票信息异常: %s", code, exc_info=True)
        return None


def baostock_batch_stock_info(codes: list[str], sleep: float = 0.3) -> list[dict]:
    """
    批量获取多只股票的基础信息（含 IPO 日期和行业）

    Args:
        codes: 股票代码列表
        sleep: 每次请求间隔（秒）

    Returns:
        信息字典列表
    """
    results = []
    for i, code in enumerate(codes):
        info = baostock_get_stock_info(code)
        if info:
            results.append(info)
        else:
            logger.warning("Baostock 获取 %s 失败，跳过", code)

        if (i + 1) % 10 == 0:
            logger.info("Baostock 批量获取进度: %d/%d", i + 1, len(codes))

        time.sleep(sleep)

    logger.info("Baostock 批量获取完成: %d/%d 成功", len(results), len(codes))
    return results


# ──────────────────────────────────────────────
#  Baostock: 历史K线
# ──────────────────────────────────────────────


def baostock_get_kline(
    code: str,
    start_date: str = "",
    end_date: str = "",
    days: int = 180,
    adjust: str = "3",
) -> pd.DataFrame:
    """
    通过 Baostock 获取历史K线数据

    Args:
        code: 6位股票代码
        start_date/end_date: 日期范围 YYYYMMDD
        days: 默认天数（start_date 为空时使用）
        adjust: 复权类型 '1'后复权 '2'前复权 '3'不复权

    Returns:
        DataFrame: time, open, high, low, close, volume, amount, turn
    """
    if not _baostock_login():
        return pd.DataFrame()

    import baostock as bs

    # 代码格式转换
    if code.startswith(("6", "9")):
        bs_code = f"sh.{code}"
    else:
        bs_code = f"sz.{code}"

    # 日期处理
    if start_date and end_date:
        s = start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:]
        e = end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:]
    else:
        e = date.today().strftime("%Y-%m-%d")
        s = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,code,open,high,low,close,volume,amount,turn,pctChg",
            start_date=s,
            end_date=e,
            frequency="d",
            adjustflag=adjust,
        )

        if rs.error_code != "0":
            logger.warning("Baostock K线获取失败: %s %s", bs_code, rs.error_msg)
            return pd.DataFrame()

        data_list = []
        while (rs.error_code == "0") and rs.next():
            row = rs.get_row_data()
            data_list.append({
                "time": row[0],
                "open": float(row[2]) if row[2] else 0,
                "high": float(row[3]) if row[3] else 0,
                "low": float(row[4]) if row[4] else 0,
                "close": float(row[5]) if row[5] else 0,
                "volume": float(row[6]) if row[6] else 0,
                "amount": float(row[7]) if row[7] else 0,
            })

        df = pd.DataFrame(data_list)
        if not df.empty:
            # 过滤无效数据（停牌时 open=0）
            df = df[df["open"] > 0].reset_index(drop=True)

        logger.info("Baostock K线: %s, %d 条", code, len(df))
        return df

    except Exception:
        logger.error("Baostock K线获取异常: %s", code, exc_info=True)
        return pd.DataFrame()


# ──────────────────────────────────────────────
#  新浪财经: 实时行情 + 历史K线 + 汇率
# ──────────────────────────────────────────────


def sina_get_realtime_quotes(codes: list[str]) -> list[dict]:
    """
    新浪实时行情

    Args:
        codes: 股票代码列表 ['600519', '000001']

    Returns:
        行情字典列表
    """
    # 转换为新浪格式 sh600519 / sz000001
    sina_codes = []
    for c in codes:
        if c.startswith(("6", "9")):
            sina_codes.append(f"sh{c}")
        else:
            sina_codes.append(f"sz{c}")

    url = f"http://hq.sinajs.cn/list={','.join(sina_codes)}"

    try:
        resp = requests.get(url, headers=SINA_HEADERS, timeout=10)
        resp.encoding = "gbk"
        lines = resp.text.strip().split("\n")

        results = []
        for line in lines:
            if "=" not in line or 'var' not in line:
                continue
            data_str = line.split("=", 1)[1].strip().strip('"')
            if not data_str:
                continue
            parts = data_str.split(",")
            if len(parts) < 32:
                continue

            results.append({
                "code": parts[0],
                "name": parts[0],  # 新浪实时行情第一个字段是名称
                "open": float(parts[1]) if parts[1] else 0,
                "pre_close": float(parts[2]) if parts[2] else 0,
                "price": float(parts[3]) if parts[3] else 0,
                "high": float(parts[4]) if parts[4] else 0,
                "low": float(parts[5]) if parts[5] else 0,
                "volume": float(parts[8]) if parts[8] else 0,
                "amount": float(parts[9]) if parts[9] else 0,
                "date": parts[30] if len(parts) > 30 else "",
                "time": parts[31] if len(parts) > 31 else "",
            })

        logger.info("新浪实时行情: %d/%d 成功", len(results), len(codes))
        return results

    except Exception:
        logger.error("新浪实时行情获取异常", exc_info=True)
        return []


def sina_get_kline(
    code: str,
    datalen: int = 180,
    scale: int = 240,
) -> pd.DataFrame:
    """
    新浪历史K线

    Args:
        code: 6位股票代码
        datalen: K线条数
        scale: K线周期 5/15/30/60分钟/240日K/1200周K

    Returns:
        DataFrame: time, open, high, low, close, volume
    """
    sina_code = f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"

    url = "https://quotes.sina.cn/cn/api/jsonp_v2.php/var/CN_MarketDataService.getKLineData"
    params = {
        "symbol": sina_code,
        "scale": str(scale),
        "ma": "no",
        "datalen": str(datalen),
    }

    try:
        resp = requests.get(url, params=params, headers=SINA_HEADERS, timeout=15)
        text = resp.text

        # 解析 JSONP
        start = text.find("(")
        end = text.rfind(")")
        if start < 0 or end <= start:
            logger.warning("新浪K线 JSONP 解析失败: %s", code)
            return pd.DataFrame()

        data = json.loads(text[start + 1 : end])
        if not isinstance(data, list):
            return pd.DataFrame()

        records = []
        for item in data:
            records.append({
                "time": item.get("day", ""),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": float(item.get("volume", 0)),
            })

        df = pd.DataFrame(records)
        logger.info("新浪K线: %s, %d 条", code, len(df))
        return df

    except Exception:
        logger.error("新浪K线获取异常: %s", code, exc_info=True)
        return pd.DataFrame()


def sina_get_usd_cny_rate() -> Optional[float]:
    """新浪 USD/CNY 实时汇率"""
    url = "http://hq.sinajs.cn/list=fx_susdcny"
    try:
        resp = requests.get(url, headers=SINA_HEADERS, timeout=10)
        resp.encoding = "gbk"
        text = resp.text
        start = text.find('"')
        end = text.rfind('"')
        if start > 0 and end > start:
            parts = text[start + 1 : end].split(",")
            if len(parts) > 6:
                # parts[6] = 中间价
                rate = float(parts[6])
                logger.info("新浪汇率 USD/CNY = %s", rate)
                return rate
    except Exception:
        logger.error("新浪汇率获取异常", exc_info=True)
    return None


# ──────────────────────────────────────────────
#  腾讯证券: 实时行情 + 历史K线
# ──────────────────────────────────────────────


def tencent_get_realtime_quotes(codes: list[str]) -> list[dict]:
    """
    腾讯实时行情

    Args:
        codes: 股票代码列表

    Returns:
        行情字典列表
    """
    tencent_codes = []
    for c in codes:
        if c.startswith(("6", "9")):
            tencent_codes.append(f"sh{c}")
        else:
            tencent_codes.append(f"sz{c}")

    url = f"http://qt.gtimg.cn/q={','.join(tencent_codes)}"

    try:
        resp = requests.get(url, headers=TENCENT_HEADERS, timeout=10)
        resp.encoding = "gbk"
        lines = resp.text.strip().split(";")

        results = []
        for line in lines:
            if "=" not in line or len(line) < 20:
                continue
            data_str = line.split("=", 1)[1].strip().strip('"')
            if not data_str:
                continue
            parts = data_str.split("~")
            if len(parts) < 35:
                continue

            results.append({
                "code": parts[2] if len(parts) > 2 else "",
                "name": parts[1] if len(parts) > 1 else "",
                "price": float(parts[3]) if parts[3] else 0,
                "pre_close": float(parts[4]) if len(parts) > 4 and parts[4] else 0,
                "open": float(parts[5]) if len(parts) > 5 and parts[5] else 0,
                "high": float(parts[33]) if len(parts) > 33 and parts[33] else 0,
                "low": float(parts[34]) if len(parts) > 34 and parts[34] else 0,
                "volume": float(parts[6]) if len(parts) > 6 and parts[6] else 0,
                "amount": float(parts[37]) if len(parts) > 37 and parts[37] else 0,
                "change_pct": float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            })

        logger.info("腾讯实时行情: %d/%d 成功", len(results), len(codes))
        return results

    except Exception:
        logger.error("腾讯实时行情获取异常", exc_info=True)
        return []


def tencent_get_kline(
    code: str,
    start_date: str = "",
    end_date: str = "",
    days: int = 180,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """
    腾讯历史K线

    Args:
        code: 6位股票代码
        start_date/end_date: YYYY-MM-DD
        days: 默认天数
        adjust: 复权 qfq前复权 hfq后复权 不复权留空

    Returns:
        DataFrame: time, open, high, low, close, volume
    """
    tencent_code = f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"

    if start_date and end_date:
        s = start_date.replace("-", "")
        e = end_date.replace("-", "")
    else:
        e = date.today().strftime("%Y%m%d")
        s = (date.today() - timedelta(days=days)).strftime("%Y%m%d")

    # 腾讯日K线接口
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    param_str = f"{tencent_code},day,{s},{e},640,{adjust}"

    try:
        resp = requests.get(
            url, params={"param": param_str}, headers=TENCENT_HEADERS, timeout=15
        )
        data = resp.json()

        if "data" not in data:
            return pd.DataFrame()

        stock_data = data["data"].get(tencent_code, {})
        key = f"{adjust}day" if adjust else "day"
        klines = stock_data.get(key) or stock_data.get("day", [])

        if not klines:
            return pd.DataFrame()

        records = []
        for k in klines:
            records.append({
                "time": k[0],
                "open": float(k[1]) if k[1] else 0,
                "high": float(k[2]) if k[2] else 0,
                "low": float(k[3]) if k[3] else 0,
                "close": float(k[4]) if k[4] else 0,
                "volume": float(k[5]) if len(k) > 5 and k[5] else 0,
            })

        df = pd.DataFrame(records)
        # 过滤停牌数据
        df = df[df["open"] > 0].reset_index(drop=True)
        logger.info("腾讯K线: %s, %d 条", code, len(df))
        return df

    except Exception:
        logger.error("腾讯K线获取异常: %s", code, exc_info=True)
        return pd.DataFrame()


# ──────────────────────────────────────────────
#  统一接口: 自动回退
# ──────────────────────────────────────────────


def get_real_kline(
    code: str,
    start_date: str = "",
    end_date: str = "",
    days: int = 180,
) -> tuple[pd.DataFrame, str]:
    """
    获取真实K线数据（自动回退多数据源）

    优先级: Baostock > 新浪 > 腾讯

    Returns:
        (DataFrame, source_name) — source_name 为 'baostock'/'sina'/'tencent'/''
    """
    # 1. Baostock
    df = baostock_get_kline(code, start_date, end_date, days)
    if not df.empty:
        return df, "baostock"

    time.sleep(API_SLEEP)

    # 2. 新浪
    datalen = min(days + 30, 640)  # 新浪最大640条
    df = sina_get_kline(code, datalen=datalen)
    if not df.empty:
        # 新浪返回的是最近N条，需要按日期过滤
        if start_date:
            df["time"] = pd.to_datetime(df["time"])
            s = pd.to_datetime(start_date)
            df = df[df["time"] >= s].reset_index(drop=True)
            df["time"] = df["time"].dt.strftime("%Y-%m-%d")
        if end_date:
            df["time"] = pd.to_datetime(df["time"])
            e = pd.to_datetime(end_date)
            df = df[df["time"] <= e].reset_index(drop=True)
            df["time"] = df["time"].dt.strftime("%Y-%m-%d")
        return df, "sina"

    time.sleep(API_SLEEP)

    # 3. 腾讯
    s_date = start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:] if start_date else ""
    e_date = end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:] if end_date else ""
    df = tencent_get_kline(code, s_date, e_date, days)
    if not df.empty:
        return df, "tencent"

    return pd.DataFrame(), ""


def get_realtime_quote(code: str) -> Optional[dict]:
    """
    获取单只股票实时行情（自动回退）

    优先级: 新浪 > 腾讯
    """
    # 新浪
    quotes = sina_get_realtime_quotes([code])
    if quotes:
        return quotes[0]

    time.sleep(API_SLEEP)

    # 腾讯
    quotes = tencent_get_realtime_quotes([code])
    if quotes:
        return quotes[0]

    return None


def get_realtime_quotes_batch(codes: list[str]) -> list[dict]:
    """
    批量获取实时行情（自动回退）

    优先级: 新浪 > 腾讯
    """
    # 新浪
    quotes = sina_get_realtime_quotes(codes)
    if quotes:
        return quotes

    time.sleep(API_SLEEP)

    # 腾讯
    quotes = tencent_get_realtime_quotes(codes)
    if quotes:
        return quotes

    return []


def get_stock_info(code: str) -> Optional[dict]:
    """
    获取单只股票基础信息（IPO日期 + 行业）

    优先级: Baostock (唯一能获取科创板的源)
    """
    return baostock_get_stock_info(code)
