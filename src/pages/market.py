"""
行情扫描 — 技术条件选股
支持N连阳、涨幅筛选、均线排列、金叉、放量、新高等多条件组合
"""

from datetime import date

import pandas as pd
import streamlit as st

from src.components.user_header import render_user_header
from src.data.db import db, StockBasic
from src.strategy.market_scanner import (
    ALL_CONDITIONS,
    CONDITION_MAP,
    scan_market,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def market_page():
    render_user_header()

    st.title("行情扫描")
    st.caption("技术条件选股 · 多条件组合筛选 · 实时扫描")

    # ── 条件选择区 ──
    st.subheader("筛选条件")

    # 条件卡片
    cond_options = {c.name: c.id for c in ALL_CONDITIONS}
    selected_names = st.multiselect(
        "选择条件（可多选，满足任一即入选）",
        options=list(cond_options.keys()),
        default=["N连阳"],
        placeholder="点击选择技术条件...",
    )

    selected_ids = [cond_options[n] for n in selected_names]

    # 动态参数面板
    cond_params = {}
    if selected_ids:
        with st.expander("⚙️ 参数调整", expanded=True):
            cols = st.columns(min(len(selected_ids), 3))
            for i, cond_id in enumerate(selected_ids):
                cond = CONDITION_MAP[cond_id]
                with cols[i % 3]:
                    st.caption(f"**{cond.name}**")
                    for pname, (ptype, pdefault, plabel) in cond.params.items():
                        if cond_id not in cond_params:
                            cond_params[cond_id] = {}
                        if ptype is int:
                            cond_params[cond_id][pname] = st.number_input(
                                plabel,
                                value=pdefault,
                                min_value=1,
                                max_value=200,
                                step=1,
                                key=f"{cond_id}_{pname}",
                            )
                        elif ptype is float:
                            cond_params[cond_id][pname] = st.number_input(
                                plabel,
                                value=float(pdefault),
                                min_value=0.1,
                                max_value=50.0,
                                step=0.5,
                                key=f"{cond_id}_{pname}",
                            )

    # ── K线回溯天数 ──
    lookback = st.slider("K线回溯天数", min_value=30, max_value=365, value=90, step=10)

    # ── 扫描按钮 ──
    scan_clicked = st.button("🔍 开始扫描", type="primary", use_container_width=True)

    if not scan_clicked:
        st.info("选择条件后点击「开始扫描」")
        return

    if not selected_ids:
        st.warning("请至少选择一个筛选条件")
        return

    # ── 执行扫描 ──
    with st.spinner(f"正在扫描全市场股票（K线回溯 {lookback} 天）..."):

        # 获取所有股票代码
        db.connect(reuse_if_open=True)
        stocks = list(StockBasic.select().dicts())

        codes = [s["code"] for s in stocks]
        total_stocks = len(codes)
        st.caption(f"共 {total_stocks} 只股票待扫描")

        results = scan_market(
            codes=codes,
            conditions=selected_ids,
            cond_params=cond_params,
            lookback_days=lookback,
        )
        db.close()

    # ── 结果展示 ──
    st.divider()
    st.subheader(f"扫描结果（匹配 {len(results)} / {total_stocks} 只）")

    if not results:
        st.warning("没有股票满足当前条件，试试放宽参数？")
        return

    # 构建结果表格
    rows = []
    for r in results:
        # 涨跌颜色
        pct = r["change_pct"]
        if pct > 0:
            change_str = f"🔴 +{pct:.2f}%"
        elif pct < 0:
            change_str = f"🟢 {pct:.2f}%"
        else:
            change_str = "➖ 0.00%"

        # 匹配条件标签
        tags = " · ".join(r["matched_conditions"])

        # MA值
        ma_info = ", ".join(
            f"{k}={v}" for k, v in sorted(r["ma_values"].items())
        ) if r["ma_values"] else "—"

        rows.append({
            "代码": r["code"],
            "名称": r["name"],
            "板块": r.get("sector", ""),
            "五行": r.get("wuxing", ""),
            "最新价": f"¥{r['price']:.2f}",
            "涨跌幅": change_str,
            "成交量(手)": f"{r['volume']:,}" if r["volume"] > 0 else "—",
            "均线": ma_info,
            "匹配条件": tags,
            "_pct_val": pct,
        })

    df = pd.DataFrame(rows)

    col_config = {
        "代码": st.column_config.TextColumn("代码", width="small"),
        "名称": st.column_config.TextColumn("名称", width="small"),
        "板块": st.column_config.TextColumn("板块", width="medium"),
        "五行": st.column_config.TextColumn("五行", width="small"),
        "最新价": st.column_config.TextColumn("最新价", width="small"),
        "涨跌幅": st.column_config.TextColumn("涨跌幅", width="small"),
        "成交量(手)": st.column_config.TextColumn("成交量", width="small"),
        "均线": st.column_config.TextColumn("关键均线", width="medium"),
        "匹配条件": st.column_config.TextColumn("触发条件", width="medium"),
        "_pct_val": None,
    }

    sel = st.dataframe(
        df,
        column_config=col_config,
        column_order=[
            "代码", "名称", "板块", "五行", "最新价",
            "涨跌幅", "成交量(手)", "均线", "匹配条件",
        ],
        hide_index=True,
        use_container_width=True,
        height=max(38 * (len(rows) + 1), 300),
        on_select="rerun",
        selection_mode="single-row",
        key="mkt-table",
    )

    # 行点击 → 跳转K线
    if sel is not None and hasattr(sel, "selection") and sel.selection.get("rows"):
        row_idx = sel.selection["rows"][0]
        if row_idx < len(rows):
            code = rows[row_idx]["代码"]
            st.session_state["kline_stock"] = code
            st.session_state["mkt-table"] = {"selection": {"rows": []}}
            st.switch_page("src/pages/kline_viewer.py")

    # ── 数据来源说明 ──
    sources = set(r.get("source", "unknown") for r in results)
    source_text = " · ".join(sorted(sources))
    st.caption(f"数据来源: {source_text}")


if __name__ == "__main__":
    market_page()
