"""
股票 F10 档案数据模块 —— 公司概况/行情快照/十大股东/财务数据/资金流向

数据源:
  基础信息(市值/PE/PB/ROE): 东方财富 (efinance)
  行情快照(五档盘口):       东方财富 (efinance)
  十大股东:                 东方财富 (efinance)
  所属板块:                 东方财富 (efinance)
  资金流向:                 东方财富 (efinance)
  季频财务数据(盈利/成长/偿债/现金流): Baostock
"""

from datetime import date

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


def _to_float(v) -> float | None:
    """安全转 float"""
    if v is None or v == "" or v == "--":
        return None
    try:
        f = float(v)
        return f if f == f else None  # 过滤 NaN
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    f = _to_float(v)
    return int(f) if f is not None else None


# ──────────────────────────────────────────────
#  东方财富 (efinance): 基础信息 / 行情快照 / 股东 / 板块 / 资金
# ──────────────────────────────────────────────


def get_f10_base_info(code: str) -> dict | None:
    """东方财富 F10 基础信息: 市值/市盈率/市净率/ROE/毛利率/净利率/净利润/行业"""
    try:
        import efinance as ef

        row = ef.stock.get_base_info(code)
        if row is None or row.empty:
            return None
        return {
            "name": row.get("股票名称"),
            "industry": row.get("所处行业"),
            "net_profit": _to_float(row.get("净利润")),
            "total_mv": _to_float(row.get("总市值")),
            "circ_mv": _to_float(row.get("流通市值")),
            "pe": _to_float(row.get("市盈率(动)")),
            "pb": _to_float(row.get("市净率")),
            "roe": _to_float(row.get("ROE")),
            "gross_margin": _to_float(row.get("毛利率")),
            "net_margin": _to_float(row.get("净利率")),
        }
    except Exception:
        logger.warning("efinance 获取基础信息失败: %s", code, exc_info=True)
        return None


def get_f10_quote_snapshot(code: str) -> dict | None:
    """东方财富实时行情快照: 最新价/涨跌幅/五档盘口/换手率等"""
    try:
        import efinance as ef

        row = ef.stock.get_quote_snapshot(code)
        if row is None or row.empty:
            return None
        return {
            "name": row.get("名称"),
            "price": _to_float(row.get("最新价")),
            "change": _to_float(row.get("涨跌额")),
            "change_pct": _to_float(row.get("涨跌幅")),
            "open": _to_float(row.get("今开")),
            "pre_close": _to_float(row.get("昨收")),
            "high": _to_float(row.get("最高")),
            "low": _to_float(row.get("最低")),
            "avg_price": _to_float(row.get("均价")),
            "limit_up": _to_float(row.get("涨停价")),
            "limit_down": _to_float(row.get("跌停价")),
            "turnover": _to_float(row.get("换手率")),
            "volume": _to_float(row.get("成交量")),
            "amount": _to_float(row.get("成交额")),
            "time": row.get("时间"),
            # 五档
            "buy_1": _to_float(row.get("买1价")),
            "buy_1_vol": _to_float(row.get("买1数量")),
            "buy_2": _to_float(row.get("买2价")),
            "buy_2_vol": _to_float(row.get("买2数量")),
            "buy_3": _to_float(row.get("买3价")),
            "buy_3_vol": _to_float(row.get("买3数量")),
            "buy_4": _to_float(row.get("买4价")),
            "buy_4_vol": _to_float(row.get("买4数量")),
            "buy_5": _to_float(row.get("买5价")),
            "buy_5_vol": _to_float(row.get("买5数量")),
            "sell_1": _to_float(row.get("卖1价")),
            "sell_1_vol": _to_float(row.get("卖1数量")),
            "sell_2": _to_float(row.get("卖2价")),
            "sell_2_vol": _to_float(row.get("卖2数量")),
            "sell_3": _to_float(row.get("卖3价")),
            "sell_3_vol": _to_float(row.get("卖3数量")),
            "sell_4": _to_float(row.get("卖4价")),
            "sell_4_vol": _to_float(row.get("卖4数量")),
            "sell_5": _to_float(row.get("卖5价")),
            "sell_5_vol": _to_float(row.get("卖5数量")),
        }
    except Exception:
        logger.warning("efinance 获取行情快照失败: %s", code, exc_info=True)
        return None


def get_f10_top10_holders(code: str) -> pd.DataFrame:
    """东方财富十大股东"""
    try:
        import efinance as ef

        df = ef.stock.get_top10_stock_holder_info(code)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception:
        logger.warning("efinance 获取十大股东失败: %s", code, exc_info=True)
        return pd.DataFrame()


def get_f10_belong_boards(code: str) -> pd.DataFrame:
    """东方财富所属板块"""
    try:
        import efinance as ef

        df = ef.stock.get_belong_board(code)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception:
        logger.warning("efinance 获取所属板块失败: %s", code, exc_info=True)
        return pd.DataFrame()


def get_f10_history_bill(code: str) -> pd.DataFrame:
    """东方财富历史资金流向（近3个月日线）"""
    try:
        import efinance as ef

        df = ef.stock.get_history_bill(code)
        if df is None or df.empty:
            return pd.DataFrame()
        # 按日期升序，取最近60条
        df = df.sort_values("日期").tail(60).reset_index(drop=True)
        return df
    except Exception:
        logger.warning("efinance 获取历史资金流向失败: %s", code, exc_info=True)
        return pd.DataFrame()


# ──────────────────────────────────────────────
#  Baostock: 季频财务数据
# ──────────────────────────────────────────────


def _bs_code(code: str) -> str:
    return f"sh.{code}" if code.startswith(("6", "9")) else f"sz.{code}"


def get_f10_financials(code: str, recent_quarters: int = 4) -> dict[str, pd.DataFrame]:
    """
    Baostock 季频财务数据（最近 N 个季度，含当年）

    返回:
        {
            "quarters": ["2025Q1", ...],
            "profit": DataFrame  盈利能力,
            "growth": DataFrame  成长能力,
            "balance": DataFrame 偿债能力,
        }
    """
    from src.data.sources import _baostock_login

    if not _baostock_login():
        return {}

    import baostock as bs

    # 生成最近 N 个 (year, quarter)，从当前季度往回推
    today = date.today()
    quarters = []
    y, q = today.year, (today.month - 1) // 3 + 1  # 当前季度（1-4）
    # 当前季报通常未发布，从上一季度开始
    q -= 1
    if q == 0:
        y -= 1
        q = 4
    for _ in range(recent_quarters):
        quarters.append((y, q))
        q -= 1
        if q == 0:
            y -= 1
            q = 4

    bs_c = _bs_code(code)

    profit_rows, growth_rows, balance_rows = [], [], []
    labels = []

    for y, q in quarters:
        labels.append(f"{y}Q{q}")

        # 盈利能力
        rs = bs.query_profit_data(code=bs_c, year=y, quarter=q)
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            profit_rows.append({
                "quarter": f"{y}Q{q}",
                "pub_date": row[1],
                "roe_avg": _to_float(row[3]),
                "np_margin": _to_float(row[4]),
                "gp_margin": _to_float(row[5]),
                "net_profit": _to_float(row[6]),
                "eps_ttm": _to_float(row[7]),
                "total_share": _to_float(row[8]),
                "liqa_share": _to_float(row[9]),
            })
            break

        # 成长能力
        rs = bs.query_growth_data(code=bs_c, year=y, quarter=q)
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            growth_rows.append({
                "quarter": f"{y}Q{q}",
                "yoy_equity": _to_float(row[3]),
                "yoy_asset": _to_float(row[4]),
                "yoy_ni": _to_float(row[5]),
                "yoy_eps": _to_float(row[6]),
                "yoy_pni": _to_float(row[7]),
            })
            break

        # 偿债能力
        rs = bs.query_balance_data(code=bs_c, year=y, quarter=q)
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            balance_rows.append({
                "quarter": f"{y}Q{q}",
                "current_ratio": _to_float(row[3]),
                "quick_ratio": _to_float(row[4]),
                "cash_ratio": _to_float(row[5]),
                "yoy_liability": _to_float(row[6]),
                "liability_to_asset": _to_float(row[7]),
                "asset_to_equity": _to_float(row[8]),
            })
            break

    result = {
        "quarters": labels,
        "profit": pd.DataFrame(profit_rows),
        "growth": pd.DataFrame(growth_rows),
        "balance": pd.DataFrame(balance_rows),
    }
    logger.info("Baostock 财务数据: %s, %d 个季度", code, len(profit_rows))
    return result


# ──────────────────────────────────────────────
#  格式化工具
# ──────────────────────────────────────────────


def fmt_yi(v: float | None) -> str:
    """金额格式化为亿元"""
    if v is None:
        return "—"
    yi = v / 1e8
    if abs(yi) >= 100:
        return f"{yi:,.0f}亿"
    return f"{yi:,.2f}亿"


def fmt_wan(v: float | None) -> str:
    """金额格式化为万元"""
    if v is None:
        return "—"
    return f"{v / 1e4:,.2f}万"


def fmt_pct(v: float | None, mul100: bool = False) -> str:
    """百分比格式化。mul100=True 表示原始值已是小数需×100"""
    if v is None:
        return "—"
    val = v * 100 if mul100 else v
    return f"{val:.2f}%"


def fmt_num(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{digits}f}"
