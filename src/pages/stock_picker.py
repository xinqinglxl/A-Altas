"""
财神选股 - 分类别推荐（八字合盘 / 五行匹配 / 幸运数字 / 幸运颜色 / 天干择时）
进入页面自动加载，每个类别默认推荐 5 只股票并附推荐理由。
"""

import streamlit as st
from datetime import date

from src.data.db import db, UserProfile
from src.strategy.scorer import get_categorized_picks, get_usd_price
from src.data.exchange import get_usd_cny_latest
from src.metaphysics.fortune import get_lucky_numbers, get_lucky_colors
from src.strategy.scorer import _user_bazi_from_profile
from src.utils.logger import get_logger
from src.utils.user_guard import require_user_profile
from src.components.user_header import render_user_header

logger = get_logger(__name__)

# ── 分类配置 ──
CATEGORY_CONFIG = [
    {
        "key": "bazi",
        "icon": "🧬",
        "title": "八字合盘推荐",
        "desc": "公司八字与你的八字契合度最高的股票",
        "score_field": "bazi_score",
        "score_label": "合盘分",
    },
    {
        "key": "wuxing",
        "icon": "⚖️",
        "title": "五行匹配推荐",
        "desc": "板块五行与你的日主五行关系最佳的股票",
        "score_field": "wuxing_score",
        "score_label": "五行分",
    },
    {
        "key": "lucky_number",
        "icon": "🔢",
        "title": "幸运数字推荐",
        "desc": "股票代码中包含你幸运数字的股票",
        "score_field": "composite_score",
        "score_label": "财神指数",
    },
    {
        "key": "lucky_color",
        "icon": "🎨",
        "title": "幸运颜色推荐",
        "desc": "板块五行对应你幸运颜色的股票",
        "score_field": "wuxing_score",
        "score_label": "五行分",
    },
    {
        "key": "timing",
        "icon": "⏰",
        "title": "天干择时推荐",
        "desc": "今日日柱五行与板块五行关系最佳的股票",
        "score_field": "timing_score",
        "score_label": "择时分",
    },
]


def stock_picker_page():
    st.title("财神选股")
    st.caption("八字合盘 · 五行匹配 · 幸运数字 · 幸运颜色 · 天干择时 — 五维分类推荐")

    db.connect(reuse_if_open=True)

    # 顶部用户 header
    render_user_header()

    # 守卫：检查用户八字信息
    user = require_user_profile("财神选股")
    if user is None:
        db.close()
        return

    logger.info("财神选股页面加载: user=%s", user.name)

    # ---- 侧边栏：用户信息 ----
    with st.sidebar:
        st.subheader("当前用户")
        st.markdown(f"**{user.name}**")
        st.markdown(f"日主: **{user.day_master}**")
        if user.xi_shen:
            st.markdown(f"喜用神: **{user.xi_shen}**")
        if user.ji_shen:
            st.markdown(f"忌神: **{user.ji_shen}**")

        st.divider()

        # 幸运指标摘要
        user_bazi = _user_bazi_from_profile(user)
        lucky_nums = get_lucky_numbers(user_bazi)
        lucky_cols = get_lucky_colors(user_bazi)

        st.markdown("#### 你的幸运指标")
        if lucky_nums:
            st.markdown(f"幸运数字: **{'、'.join(str(n) for n in lucky_nums[:6])}**")
        if lucky_cols:
            st.markdown(f"幸运颜色: **{'、'.join(lucky_cols[:6])}**")

        st.divider()

        # 刷新按钮
        refresh = st.button("🔄 重新计算", use_container_width=True,
                            help="清除缓存并重新评分所有股票")

    # ---- 主区域：自动加载分类推荐 ----
    st.caption(f"评分日期: {date.today()}")

    # 汇率
    rate = get_usd_cny_latest() or 7.2
    st.caption(f"当前参考汇率: 1 USD = {rate:.4f} CNY")

    try:
        with st.spinner("正在计算财神指数..."):
            picks = get_categorized_picks(user, refresh=refresh)
    except Exception as e:
        logger.error("财神选股加载失败: %s", e, exc_info=True)
        st.error(f"加载失败：{e}")
        db.close()
        return

    if not picks:
        st.warning("暂无评分数据，请先在数据库中添加股票基本信息。")
        db.close()
        return

    # ---- 渲染每个分类 ----
    for cfg in CATEGORY_CONFIG:
        key = cfg["key"]
        items = picks.get(key, [])

        st.divider()
        st.subheader(f"{cfg['icon']} {cfg['title']}")
        st.caption(cfg["desc"])

        if not items:
            st.info(f"暂无符合条件的股票推荐")
            continue

        # 表头
        header_cols = st.columns([0.5, 2.2, 1.2, 4.5, 0.8, 0.8])
        headers = ["#", "代码 / 名称", cfg["score_label"], "推荐理由", "K线", "详情"]
        for col, h in zip(header_cols, headers):
            col.markdown(f"**{h}**")

        # 每行
        for idx, r in enumerate(items, 1):
            row_cols = st.columns([0.5, 2.2, 1.2, 4.5, 0.8, 0.8])

            with row_cols[0]:
                st.markdown(f"{idx}")

            with row_cols[1]:
                fake_flag = " 🔴" if r.get("data_source") == "fake" else ""
                st.markdown(f"**{r['stock_code']}** {r['stock_name']}{fake_flag}")
                if r.get("sector"):
                    st.caption(f"板块: {r['sector']}")

            with row_cols[2]:
                score_val = r.get(cfg["score_field"], 0)
                st.markdown(f"**{score_val:.1f}**")

            with row_cols[3]:
                st.caption(r.get("reason", r.get("summary", "")))

            with row_cols[4]:
                if st.button("📈", key=f"sp-{key}-kline-{r['stock_code']}",
                             help=f"查看 {r['stock_code']} K线"):
                    st.session_state["kline_stock"] = r["stock_code"]
                    st.switch_page("src/pages/kline_viewer.py")

            with row_cols[5]:
                if st.button("🏢", key=f"sp-{key}-detail-{r['stock_code']}",
                             help=f"查看 {r['stock_code']} 详情"):
                    st.session_state["stock_detail_code"] = r["stock_code"]
                    st.switch_page("src/pages/stock_detail.py")

    db.close()


if __name__ == "__main__":
    stock_picker_page()
