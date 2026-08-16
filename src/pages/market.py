"""
行情扫描 — 技术条件选股
支持N连阳、涨幅筛选、均线排列、金叉、放量、新高等多条件组合
"""

from datetime import date

import streamlit as st

from src.components.user_header import render_user_header
from src.data.db import db, StockBasic
from src.metaphysics.bazi import BaziResult
from src.metaphysics.stock_recommend import evaluate_stock
from src.strategy.market_scanner import (
    ALL_CONDITIONS,
    CONDITION_MAP,
    scan_market,
)
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_user

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

    # 初始化 session_state
    if "mkt_results" not in st.session_state:
        st.session_state["mkt_results"] = None
    if "mkt_total" not in st.session_state:
        st.session_state["mkt_total"] = 0

    if scan_clicked and selected_ids:
        # ── 执行扫描 ──
        with st.spinner(f"正在扫描全市场股票（K线回溯 {lookback} 天）..."):
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

            # 持久化结果
            st.session_state["mkt_results"] = results
            st.session_state["mkt_total"] = total_stocks
    elif scan_clicked and not selected_ids:
        st.warning("请至少选择一个筛选条件")

    # ═══════════════════════════════════════════
    #  从 session_state 恢复并展示结果
    # ═══════════════════════════════════════════
    results = st.session_state.get("mkt_results")
    total_stocks = st.session_state.get("mkt_total", 0)

    if results is None:
        if not scan_clicked:
            st.info("选择条件后点击「开始扫描」")
        return

    if not results:
        st.warning("没有股票满足当前条件，试试放宽参数？")
        return

    # 构建结果展示（每行带 K线按钮）
    st.divider()
    st.subheader(f"扫描结果（匹配 {len(results)} / {total_stocks} 只）")

    # 表头
    h_cols = st.columns([1, 2, 1, 1, 1, 1.5, 1, 1, 2])
    headers = ["代码", "名称", "涨跌幅", "最新价", "成交量", "触发条件", "推荐", "详情", "操作"]
    for i, h in enumerate(headers):
        with h_cols[i]:
            st.caption(f"**{h}**")

    st.divider()

    # 获取用户八字以供玄学评估
    user_bazi: BaziResult | None = None
    user = get_current_user()
    if user:
        try:
            from src.metaphysics.bazi import calc_bazi
            if user.birth_date and user.birth_time:
                user_bazi = calc_bazi(user.birth_date, user.birth_time)
        except Exception:
            pass

    for r in results:
        row_cols = st.columns([1, 2, 1, 1, 1, 1.5, 1, 1, 2])

        pct = r["change_pct"]
        if pct > 0:
            change_str = f"🔴 +{pct:.2f}%"
        elif pct < 0:
            change_str = f"🟢 {pct:.2f}%"
        else:
            change_str = "➖ 0.00%"

        tags = " · ".join(r["matched_conditions"])

        # 综合推荐评估
        rec = evaluate_stock(
            stock_code=r["code"],
            stock_name=r["name"],
            stock_wuxing=r.get("wuxing"),
            stock_sector=r.get("sector"),
            matched_conditions=r["matched_conditions"],
            change_pct=pct,
            volume=r.get("volume"),
            user_bazi=user_bazi,
        )

        with row_cols[0]:
            st.code(r["code"], language=None)
        with row_cols[1]:
            st.write(r["name"])
            st.caption(f"{r.get('sector', '')} | {r.get('wuxing', '')}")
        with row_cols[2]:
            st.write(change_str)
        with row_cols[3]:
            st.write(f"¥{r['price']:.2f}")
        with row_cols[4]:
            st.write(f"{r['volume']:,}" if r["volume"] > 0 else "—")
        with row_cols[5]:
            st.caption(tags)
        with row_cols[6]:
            st.write(f"{rec.emoji} {rec.total_score}")
        with row_cols[7]:
            # 点击推荐 emoji 弹出详细分析
            with st.popover(f"{rec.emoji} 详情", use_container_width=True):
                st.markdown(f"### {rec.emoji} {r['name']}（{r['code']}）")
                st.metric("综合推荐分", f"{rec.total_score} / 100", delta=f"{rec.level}")

                st.divider()
                st.markdown(f"**技术面**（{rec.tech_score}/40 分）")
                for reason in rec.tech_reasons:
                    st.markdown(f"- {reason}")

                st.divider()
                st.markdown(f"**玄学面**（{rec.meta_score}/60 分）")
                if user_bazi is None:
                    st.caption("（需设置用户八字信息）")
                for reason in rec.meta_reasons:
                    st.markdown(f"- {reason}")

                if not rec.tech_reasons and not rec.meta_reasons:
                    st.caption("暂无详细分析数据")
        with row_cols[8]:
            col_k, col_d = st.columns([1, 1])
            with col_k:
                if st.button("📈 K线", key=f"mkt-kline-{r['code']}", help=f"查看 {r['code']} K线"):
                    st.session_state["kline_stock"] = r["code"]
                    st.switch_page("src/pages/kline_viewer.py")
            with col_d:
                if st.button("🏢 详情", key=f"mkt-detail-{r['code']}", help=f"查看 {r['code']} 股票详情"):
                    st.session_state["stock_detail_code"] = r["code"]
                    st.switch_page("src/pages/stock_detail.py")

    # ── 数据来源说明 ──
    sources = set(r.get("source", "unknown") for r in results)
    source_text = " · ".join(sorted(sources))
    st.caption(f"数据来源: {source_text}")


if __name__ == "__main__":
    market_page()
