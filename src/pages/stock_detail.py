"""
股票详情 — F10 式股票档案
参考东方财富 F10：公司概况 / 实时行情 / 股东信息 / 财务分析 / 资金流向 / 玄学档案
"""

import streamlit as st

from src.components.user_header import render_user_header
from src.data.db import db, StockBazi, StockBasic, StockScore
from src.data.stock_profile import (
    fmt_num,
    fmt_pct,
    fmt_wan,
    fmt_yi,
    get_f10_base_info,
    get_f10_belong_boards,
    get_f10_financials,
    get_f10_history_bill,
    get_f10_quote_snapshot,
    get_f10_top10_holders,
)
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_user

logger = get_logger(__name__)

# 数据缓存 TTL
TTL_SHORT = 300   # 5分钟：行情快照
TTL_MID = 3600    # 1小时：基本面/股东/板块
TTL_LONG = 12 * 3600  # 12小时：财务数据


@st.cache_data(ttl=TTL_MID, show_spinner=False)
def _cached_base_info(code: str):
    return get_f10_base_info(code)


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def _cached_snapshot(code: str):
    return get_f10_quote_snapshot(code)


@st.cache_data(ttl=TTL_MID, show_spinner=False)
def _cached_holders(code: str):
    return get_f10_top10_holders(code)


@st.cache_data(ttl=TTL_MID, show_spinner=False)
def _cached_boards(code: str):
    return get_f10_belong_boards(code)


@st.cache_data(ttl=TTL_SHORT, show_spinner=False)
def _cached_bill(code: str):
    return get_f10_history_bill(code)


@st.cache_data(ttl=TTL_LONG, show_spinner=False)
def _cached_financials(code: str):
    return get_f10_financials(code, recent_quarters=4)


# ═══════════════════════════════════════════
#  各 Tab 渲染
# ═══════════════════════════════════════════


def _render_overview(code: str, stock: StockBasic):
    """Tab 1: 公司概况"""
    info = _cached_base_info(code)
    boards = _cached_boards(code)

    # ── 顶部行情指标条 ──
    if info:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.metric("总市值", fmt_yi(info["total_mv"]))
        with c2:
            st.metric("流通市值", fmt_yi(info["circ_mv"]))
        with c3:
            st.metric("市盈率(动)", fmt_num(info["pe"]))
        with c4:
            st.metric("市净率", fmt_num(info["pb"]))
        with c5:
            st.metric("ROE", fmt_pct(info["roe"]))
        with c6:
            st.metric("净利润", fmt_yi(info["net_profit"]))

    st.divider()

    # ── 公司资料表 ──
    st.subheader("📋 公司资料")
    col_l, col_r = st.columns(2)

    with col_l:
        rows_l = [
            ("股票代码", code),
            ("股票名称", stock.name if stock else (info or {}).get("name", "—")),
            ("上市交易所", "上交所" if code.startswith(("6", "9")) else "深交所"),
            ("上市日期", str(stock.ipo_date) if stock and stock.ipo_date else "—"),
            ("所属行业", (info or {}).get("industry") or (stock.sector if stock else None) or "—"),
            ("板块五行", (stock.wuxing if stock else None) or "—"),
        ]
        for k, v in rows_l:
            c1, c2 = st.columns([1, 2])
            c1.caption(f"**{k}**")
            c2.caption(str(v))

    with col_r:
        rows_r = [
            ("毛利率", fmt_pct((info or {}).get("gross_margin"))),
            ("净利率", fmt_pct((info or {}).get("net_margin"))),
            (
                "数据来源",
                "真实" if (stock and stock.data_source == "real") else "模拟",
            ),
        ]
        for k, v in rows_r:
            c1, c2 = st.columns([1, 2])
            c1.caption(f"**{k}**")
            c2.caption(str(v))

    # ── 所属板块 ──
    if boards is not None and not boards.empty:
        st.subheader("🏷️ 所属板块")
        names = boards["板块名称"].tolist()
        # 用胶囊式标签展示
        tags_html = "".join(
            f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:2px 10px;'
            f'border-radius:12px;background:#f0f2f6;color:#333;font-size:13px;">{n}</span>'
            for n in names
        )
        st.markdown(tags_html, unsafe_allow_html=True)
        st.caption(f"共 {len(names)} 个所属板块 · 数据来源: 东方财富")


def _render_quote(code: str):
    """Tab 2: 实时行情 + 五档盘口"""
    snap = _cached_snapshot(code)
    if not snap:
        st.warning("暂无行情数据")
        return

    pct = snap["change_pct"]
    delta_str = f"{pct:+.2f}%" if pct is not None else None

    # ── 关键行情 ──
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("最新价", fmt_num(snap["price"]), delta_str)
    with c2:
        st.metric("今开", fmt_num(snap["open"]))
    with c3:
        st.metric("昨收", fmt_num(snap["pre_close"]))
    with c4:
        st.metric("最高", fmt_num(snap["high"]))
    with c5:
        st.metric("最低", fmt_num(snap["low"]))
    with c6:
        st.metric("换手率", fmt_pct(snap["turnover"]))

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("成交量(手)", fmt_num(snap["volume"], 0))
    with c2:
        st.metric("成交额", fmt_yi(snap["amount"]))
    with c3:
        st.metric("均价", fmt_num(snap["avg_price"]))

    st.caption(f"行情时间: {snap.get('time') or '—'} · 涨停 {fmt_num(snap['limit_up'])} / 跌停 {fmt_num(snap['limit_down'])}")

    st.divider()

    # ── 五档盘口 ──
    st.subheader("📊 五档盘口")
    col_sell, col_buy = st.columns(2)

    with col_sell:
        st.caption("**卖五档**")
        sell_rows = [
            (5, snap["sell_5"], snap["sell_5_vol"]),
            (4, snap["sell_4"], snap["sell_4_vol"]),
            (3, snap["sell_3"], snap["sell_3_vol"]),
            (2, snap["sell_2"], snap["sell_2_vol"]),
            (1, snap["sell_1"], snap["sell_1_vol"]),
        ]
        sell_data = [
            {
                "档位": f"卖{lv}",
                "价格": fmt_num(p),
                "数量(手)": fmt_num(v, 0) if v else "—",
            }
            for lv, p, v in sell_rows
        ]
        st.table(sell_data)

    with col_buy:
        st.caption("**买五档**")
        buy_rows = [
            (1, snap["buy_1"], snap["buy_1_vol"]),
            (2, snap["buy_2"], snap["buy_2_vol"]),
            (3, snap["buy_3"], snap["buy_3_vol"]),
            (4, snap["buy_4"], snap["buy_4_vol"]),
            (5, snap["buy_5"], snap["buy_5_vol"]),
        ]
        buy_data = [
            {
                "档位": f"买{lv}",
                "价格": fmt_num(p),
                "数量(手)": fmt_num(v, 0) if v else "—",
            }
            for lv, p, v in buy_rows
        ]
        st.table(buy_data)


def _render_holders(code: str):
    """Tab 3: 十大股东"""
    holders = _cached_holders(code)
    if holders is None or holders.empty:
        st.warning("暂无股东数据")
        return

    # 取最新一期
    latest_date = holders["更新日期"].max()
    latest = holders[holders["更新日期"] == latest_date].copy()
    latest = latest.head(10)

    # 历史期次可选
    dates = sorted(holders["更新日期"].unique(), reverse=True)
    if len(dates) > 1:
        sel_date = st.selectbox("报告期", dates, index=0, key="holder-date")
        latest = holders[holders["更新日期"] == sel_date].head(10)
    else:
        sel_date = latest_date

    st.caption(f"报告期: **{sel_date}** · 数据来源: 东方财富")

    rows = []
    for _, r in latest.iterrows():
        rows.append({
            "股东名称": r["股东名称"],
            "持股数量": r["持股数"],
            "持股比例": r["持股比例"],
            "增减": r["增减"],
            "变动率": r["变动率"],
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_financials(code: str):
    """Tab 4: 财务分析（Baostock 季频数据）"""
    fin = _cached_financials(code)
    profit = fin.get("profit")
    growth = fin.get("growth")
    balance = fin.get("balance")

    has_data = any(
        df is not None and not df.empty for df in (profit, growth, balance)
    )
    if not has_data:
        st.warning("暂无财务数据（数据源: Baostock，可能未覆盖该股票）")
        return

    st.caption("数据来源: Baostock 季频财报 · 单位: 元 / %")

    # ── 盈利能力 ──
    if profit is not None and not profit.empty:
        st.subheader("💰 盈利能力")
        rows = []
        for _, r in profit.iterrows():
            rows.append({
                "报告期": r["quarter"],
                "净资产收益率ROE": fmt_pct(r["roe_avg"], mul100=True),
                "销售净利率": fmt_pct(r["np_margin"], mul100=True),
                "销售毛利率": fmt_pct(r["gp_margin"], mul100=True),
                "净利润": fmt_yi(r["net_profit"]),
                "每股收益TTM": fmt_num(r["eps_ttm"]),
                "总股本(亿股)": fmt_num(r["total_share"] and r["total_share"] / 1e8) if r["total_share"] else "—",
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)

    # ── 成长能力 ──
    if growth is not None and not growth.empty:
        st.subheader("📈 成长能力（同比）")
        rows = []
        for _, r in growth.iterrows():
            rows.append({
                "报告期": r["quarter"],
                "净资产同比": fmt_pct(r["yoy_equity"], mul100=True),
                "总资产同比": fmt_pct(r["yoy_asset"], mul100=True),
                "净利润同比": fmt_pct(r["yoy_ni"], mul100=True),
                "每股收益同比": fmt_pct(r["yoy_eps"], mul100=True),
                "扣非净利润同比": fmt_pct(r["yoy_pni"], mul100=True),
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)

    # ── 偿债能力 ──
    if balance is not None and not balance.empty:
        st.subheader("🏦 偿债能力")
        rows = []
        for _, r in balance.iterrows():
            rows.append({
                "报告期": r["quarter"],
                "流动比率": fmt_num(r["current_ratio"]),
                "速动比率": fmt_num(r["quick_ratio"]),
                "现金比率": fmt_num(r["cash_ratio"]),
                "资产负债率": fmt_pct(r["liability_to_asset"], mul100=True),
                "权益乘数": fmt_num(r["asset_to_equity"]),
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_cashflow(code: str):
    """Tab 5: 资金流向"""
    bill = _cached_bill(code)
    if bill is None or bill.empty:
        st.warning("暂无资金流向数据")
        return

    st.caption(f"近 {len(bill)} 个交易日 · 数据来源: 东方财富")

    # ── 汇总指标 ──
    recent_5 = bill.tail(5)
    recent_20 = bill.tail(20)

    def _sum_col(df, col):
        return float(df[col].sum()) if col in df else None

    c1, c2, c3 = st.columns(3)
    with c1:
        v = _sum_col(recent_5, "主力净流入")
        st.metric("近5日主力净流入", fmt_yi(v), delta=fmt_pct(v / abs(v) * 100) if v else None)
    with c2:
        v = _sum_col(recent_20, "主力净流入")
        st.metric("近20日主力净流入", fmt_yi(v))
    with c3:
        avg_pct = float(recent_20["主力净流入占比"].mean()) if "主力净流入占比" in recent_20 else None
        st.metric("近20日主力净流入占比均值", fmt_pct(avg_pct))

    # ── 近10日明细 ──
    st.subheader("📉 近10日资金明细")
    rows = []
    for _, r in bill.tail(10).iloc[::-1].iterrows():
        main_in = r.get("主力净流入")
        rows.append({
            "日期": r["日期"],
            "收盘价": fmt_num(r.get("收盘价")),
            "涨跌幅": fmt_pct(r.get("涨跌幅")),
            "主力净流入": fmt_wan(main_in),
            "超大单净流入": fmt_wan(r.get("超大单净流入")),
            "大单净流入": fmt_wan(r.get("大单净流入")),
            "中单净流入": fmt_wan(r.get("中单净流入")),
            "小单净流入": fmt_wan(r.get("小单净流入")),
            "主力占比": fmt_pct(r.get("主力净流入占比")),
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)

    # ── 资金流向柱状图 ──
    st.subheader("📊 主力净流入趋势（近60日）")
    try:
        import plotly.graph_objects as go

        colors = ["#e74c3c" if v > 0 else "#27ae60" for v in bill["主力净流入"]]
        fig = go.Figure(
            go.Bar(x=bill["日期"], y=bill["主力净流入"] / 1e8, marker_color=colors)
        )
        fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="",
            yaxis_title="主力净流入(亿)",
            yaxis=dict(gridcolor="#eee"),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        # plotly 不可用时退化为表格
        st.line_chart(bill.set_index("日期")[["主力净流入"]])


def _render_metaphysics(code: str, stock: StockBasic):
    """Tab 6: 玄学档案（本项目特色）"""
    if not stock:
        st.warning("该股票不在本地数据库中，无玄学档案")
        return

    st.subheader("🔮 五行属性")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("板块五行", stock.wuxing or "—")
    with c2:
        st.metric("所属板块", stock.sector or "—")
    with c3:
        st.metric("上市日期", str(stock.ipo_date or "—"))

    st.divider()

    # ── 公司八字 ──
    st.subheader("☯️ 公司八字排盘")
    bazis = list(
        StockBazi.select().where(StockBazi.stock == stock)
    )
    if bazis:
        for bz in bazis:
            label = "成立时间排盘" if bz.bazi_type == "founded" else "上市时间排盘"
            with st.expander(f"📅 {label}", expanded=len(bazis) == 1):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.caption("**年柱**")
                    st.code(f"{bz.year_gan}{bz.year_zhi}", language=None)
                with col2:
                    st.caption("**月柱**")
                    st.code(f"{bz.month_gan}{bz.month_zhi}", language=None)
                with col3:
                    st.caption("**日柱**")
                    st.code(f"{bz.day_gan}{bz.day_zhi}", language=None)
                with col4:
                    st.caption("**时柱**")
                    st.code(f"{bz.hour_gan or '?'}{bz.hour_zhi or '?'}", language=None)
                st.caption(f"日主五行: **{bz.day_master}**")
    else:
        st.info("暂无公司八字数据（需先运行数据种子脚本）")

    st.divider()

    # ── 玄学评分 ──
    st.subheader("⭐ 我的玄学评分")
    user = get_current_user()
    if user is None:
        st.info("请先在【八字排盘】页面设置生辰八字，即可查看个性化玄学评分")
        return

    from datetime import date as dt_date

    scores = (
        StockScore
        .select()
        .where(
            StockScore.stock == stock,
            StockScore.user == user,
            StockScore.calc_date == dt_date.today(),
        )
    )
    score = next(iter(scores), None)

    if score:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("八字合盘", f"{score.bazi_score:.0f}")
        with c2:
            st.metric("五行匹配", f"{score.wuxing_score:.0f}")
        with c3:
            st.metric("天干择时", f"{score.timing_score:.0f}")
        with c4:
            st.metric("综合财神指数", f"{score.composite_score:.0f}")
        if score.summary:
            st.caption(f"💬 {score.summary}")
        st.caption(f"评分日期: {score.calc_date} · 可在【财神选股】页面刷新评分")
    else:
        st.info("今日暂无评分，可在【财神选股】页面刷新评分")


# ═══════════════════════════════════════════
#  主页面
# ═══════════════════════════════════════════


def stock_detail_page():
    st.title("股票详情")
    st.caption("F10 式股票档案 · 公司概况 / 实时行情 / 股东信息 / 财务分析 / 资金流向 / 玄学档案")

    render_user_header()

    db.connect(reuse_if_open=True)

    # ── 初始化持久化状态 ──
    if "detail_loaded" not in st.session_state:
        st.session_state["detail_loaded"] = None  # 当前展示的股票代码

    # ── 读取从其他页面传入的股票代码 ──
    auto_stock = st.session_state.pop("stock_detail_code", None)
    if auto_stock:
        st.session_state["detail_loaded"] = auto_stock

    # ── 顶部查询表单 ──
    default_code = st.session_state.get("detail_loaded") or "000001"
    with st.form("detail_query"):
        col_c, col_btn, col_k = st.columns([3, 1, 1])
        with col_c:
            code = st.text_input(
                "股票代码", value=default_code, key="detail-code",
                placeholder="输入6位代码，如 000001",
                label_visibility="collapsed",
            )
        with col_btn:
            submitted = st.form_submit_button("🔍 查询", type="primary", use_container_width=True)
        with col_k:
            goto_kline = st.form_submit_button("📈 看K线", use_container_width=True)

    if goto_kline:
        st.session_state["kline_stock"] = code.strip()
        db.close()
        st.switch_page("src/pages/kline_viewer.py")
        return

    code = code.strip()
    if submitted and code:
        st.session_state["detail_loaded"] = code
    elif not st.session_state.get("detail_loaded"):
        db.close()
        st.info("输入股票代码，点击【查询】查看详情")
        return

    code = st.session_state["detail_loaded"]

    # ── 本地数据库基本信息 ──
    stock = StockBasic.get_or_none(StockBasic.code == code)
    stock_name = stock.name if stock else code

    # ── 标题栏 ──
    t1, t2 = st.columns([4, 1])
    with t1:
        st.markdown(f"### 🏢 {stock_name}（{code}）")
    with t2:
        st.caption("上交所" if code.startswith(("6", "9")) else "深交所")

    # ── Tabs ──
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["📋 公司概况", "⚡ 实时行情", "👥 股东信息", "💰 财务分析", "💵 资金流向", "🔮 玄学档案"]
    )

    with tab1:
        _render_overview(code, stock)
    with tab2:
        _render_quote(code)
    with tab3:
        _render_holders(code)
    with tab4:
        _render_financials(code)
    with tab5:
        _render_cashflow(code)
    with tab6:
        _render_metaphysics(code, stock)

    db.close()


if __name__ == "__main__":
    stock_detail_page()
