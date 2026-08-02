"""
自选股 — 默认首页
显示用户自选股列表，实时行情 + 五行属性 + 玄学评分
"""

from datetime import date

import pandas as pd
import streamlit as st

from src.components.user_header import render_user_header
from src.data.db import db, StockBasic, StockScore, Watchlist
from src.data.sources import get_realtime_quotes_batch
from src.metaphysics.wuxing import wuxing_color
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_user

logger = get_logger(__name__)

# 五行 → 颜色映射（用于标签）
WUXING_TAG_COLORS = {
    "金": "#f0c040", "木": "#4caf50", "水": "#2196f3",
    "火": "#f44336", "土": "#8d6e63",
}


def _load_watchlist(user) -> list[dict]:
    """加载用户自选股列表，合并评分和行情数据"""
    watched = (
        Watchlist
        .select(Watchlist, StockBasic)
        .join(StockBasic)
        .where(Watchlist.user == user)
        .order_by(Watchlist.added_at.desc())
    )

    results = []
    codes = []
    for w in watched:
        stock = w.stock
        codes.append(stock.code)
        results.append({
            "watch_id": w.id,
            "code": stock.code,
            "name": stock.name,
            "sector": stock.sector or "",
            "wuxing": stock.wuxing or "",
            "ipo_date": stock.ipo_date,
            "data_source": stock.data_source,
            "added_at": w.added_at,
            "note": w.note,
            "price": None,
            "change_pct": None,
            "prev_close": None,
            "score": None,
        })

    if not results:
        return []

    # ---- 获取最新评分 ----
    today = date.today()
    scores = (
        StockScore
        .select()
        .where(
            StockScore.user == user,
            StockScore.calc_date == today,
        )
    )
    score_map = {}
    for s in scores:
        score_map[s.stock.code] = s.composite_score

    for r in results:
        r["score"] = score_map.get(r["code"])

    # ---- 获取实时行情（静默失败） ----
    try:
        quotes = get_realtime_quotes_batch(codes)
        quote_map = {}
        for q in quotes:
            quote_map[q["code"]] = q

        for r in results:
            q = quote_map.get(r["code"])
            if q:
                r["price"] = q.get("price")
                r["prev_close"] = q.get("pre_close")
                if r["price"] and r["prev_close"] and r["prev_close"] > 0:
                    r["change_pct"] = round(
                        (r["price"] - r["prev_close"]) / r["prev_close"] * 100, 2
                    )
    except Exception:
        logger.warning("获取实时行情失败，使用缓存数据")

    return results


def _load_all_stocks() -> list[dict]:
    """加载所有可添加的股票"""
    stocks = StockBasic.select().order_by(StockBasic.code)
    return [
        {
            "code": s.code,
            "name": s.name,
            "sector": s.sector or "",
            "wuxing": s.wuxing or "",
            "ipo_date": s.ipo_date,
        }
        for s in stocks
    ]


def watchlist_page():
    render_user_header()

    st.title("自选股")
    st.caption("关注你的股票，追踪玄学评分与实时行情")

    db.connect(reuse_if_open=True)

    user = get_current_user()

    # ── 未设置用户 ──
    if user is None:
        st.info("请先在 **八字排盘** 页面设置你的生辰八字，之后即可在这里管理自选股。")
        db.close()
        return

    # ── 加载数据 ──
    watchlist_data = _load_watchlist(user)
    all_stocks = _load_all_stocks()

    # 已收藏的股票代码集合
    watched_codes = {w["code"] for w in watchlist_data}

    # ── 顶部操作栏 ──
    col_a, col_b, col_c = st.columns([3, 2, 2])
    with col_a:
        st.caption(f"共 **{len(watchlist_data)}** 只自选股")
    with col_b:
        pass
    with col_c:
        pass

    # ── 添加自选股 ──
    with st.expander("➕ 添加自选股", expanded=len(watchlist_data) == 0):
        available = [s for s in all_stocks if s["code"] not in watched_codes]

        if not available:
            st.success("已关注全部 48 只股票！")
        else:
            # 按代码或名称搜索
            search = st.text_input(
                "搜索股票",
                placeholder="输入代码或名称搜索...",
                key="watchlist-search",
                label_visibility="collapsed",
            )
            if search:
                available = [
                    s for s in available
                    if search.upper() in s["code"] or search in s["name"]
                ]

            if available:
                # 多选添加
                options = [f"{s['code']} {s['name']} ({s['wuxing'] or '-'})" for s in available]
                selected = st.multiselect(
                    "选择要添加的股票",
                    options=options,
                    key="watchlist-add",
                    label_visibility="collapsed",
                    placeholder="点击选择股票...",
                )

                if selected and st.button("确认添加", type="primary"):
                    added = 0
                    for sel in selected:
                        code = sel.split(" ")[0]
                        try:
                            stock = StockBasic.get(StockBasic.code == code)
                            _, created = Watchlist.get_or_create(
                                user=user,
                                stock=stock,
                            )
                            if created:
                                added += 1
                        except Exception as e:
                            logger.warning("添加自选股失败: %s %s", code, e)

                    if added > 0:
                        st.success(f"已添加 {added} 只股票")
                        st.rerun()
                    else:
                        st.info("所选股票已在自选列表中")

    # ── 自选股列表 ──
    if not watchlist_data:
        st.info("还没有自选股，点击上方「添加自选股」开始关注")
        db.close()
        return

    # 构建表格
    rows = []
    for w in watchlist_data:
        # 涨跌图标
        pct = w["change_pct"]
        if pct is not None:
            if pct > 0:
                change_str = f"🔴 +{pct:.2f}%"
            elif pct < 0:
                change_str = f"🟢 {pct:.2f}%"
            else:
                change_str = "➖ 0.00%"
        else:
            change_str = "—"

        # 价格
        price_str = f"¥{w['price']:.2f}" if w["price"] else "—"

        # 评分
        score = w["score"]
        if score is not None:
            if score >= 80:
                score_str = f"🌟 {score:.0f}"
            elif score >= 60:
                score_str = f"⭐ {score:.0f}"
            elif score >= 40:
                score_str = f"🔸 {score:.0f}"
            else:
                score_str = f"🔹 {score:.0f}"
        else:
            score_str = "—"

        # 五行标签颜色
        wx = w["wuxing"]
        wx_color = WUXING_TAG_COLORS.get(wx, "#888")

        rows.append({
            "代码": w["code"],
            "名称": w["name"],
            "最新价": price_str,
            "涨跌幅": change_str,
            "五行": wx,
            "评分": score_str,
            "_score_val": score or 0,
            "_pct_val": pct,
            "_watch_id": w["watch_id"],
        })

    df = pd.DataFrame(rows)

    # 列配置
    col_config = {
        "代码": st.column_config.TextColumn("代码", width="small"),
        "名称": st.column_config.TextColumn("名称", width="small"),
        "最新价": st.column_config.TextColumn("最新价", width="small"),
        "涨跌幅": st.column_config.TextColumn("涨跌幅", width="small"),
        "五行": st.column_config.TextColumn("五行", width="small"),
        "评分": st.column_config.TextColumn("玄学评分", width="small"),
        "_score_val": st.column_config.NumberColumn("", width=None),
        "_pct_val": st.column_config.NumberColumn("", width=None),
        "_watch_id": st.column_config.NumberColumn("", width=None),
    }

    # 展示可排序表格（行点击跳转K线）
    sel = st.dataframe(
        df,
        column_config=col_config,
        column_order=["代码", "名称", "最新价", "涨跌幅", "五行", "评分"],
        hide_index=True,
        use_container_width=True,
        height=max(38 * (len(rows) + 1), 200),
        on_select="rerun",
        selection_mode="single-row",
        key="wl-table",
    )

    # 行点击 → 跳转K线页面
    if sel is not None and hasattr(sel, "selection") and sel.selection.get("rows"):
        row_idx = sel.selection["rows"][0]
        if row_idx < len(rows):
            code = rows[row_idx]["代码"]
            st.session_state["kline_stock"] = code
            st.session_state["wl-table"] = {"selection": {"rows": []}}
            st.switch_page("src/pages/kline_viewer.py")

    # ── 操作按钮 ──
    st.divider()
    col_del, col_empty = st.columns([1, 4])
    with col_del:
        to_remove = st.multiselect(
            "移除自选",
            options=[f"{w['code']} {w['name']}" for w in watchlist_data],
            key="watchlist-remove",
            label_visibility="collapsed",
            placeholder="选择要移除的股票...",
        )
        if to_remove and st.button("确认移除", type="secondary"):
            removed = 0
            for item in to_remove:
                code = item.split(" ")[0]
                try:
                    stock = StockBasic.get(StockBasic.code == code)
                    deleted = Watchlist.delete().where(
                        Watchlist.user == user,
                        Watchlist.stock == stock,
                    ).execute()
                    removed += deleted
                except Exception as e:
                    logger.warning("移除自选股失败: %s %s", code, e)
            if removed > 0:
                st.success(f"已移除 {removed} 只股票")
                st.rerun()

    db.close()


if __name__ == "__main__":
    watchlist_page()
