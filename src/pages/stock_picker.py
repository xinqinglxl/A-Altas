"""
财神选股 - 八字合盘 & 五行匹配推荐
"""

import streamlit as st
from datetime import date

from src.data.db import db, UserProfile, StockBasic
from src.strategy.scorer import get_caishen_ranking, get_usd_price, score_all_stocks
from src.data.exchange import get_usd_cny_latest
from src.utils.logger import get_logger
from src.utils.user_guard import require_user_profile
from src.components.user_header import render_user_header

logger = get_logger(__name__)


def stock_picker_page():
    st.title("财神选股")
    st.caption("基于八字合盘 + 五行匹配 + 天干择时的综合推荐")

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
        st.markdown("**图例**")
        st.markdown("🔴 假数据 - 数据为模拟生成")

    # ---- 主区域顶部工具栏：刷新按钮靠右 ----
    col_left, col_right = st.columns([4, 1])
    with col_left:
        st.subheader(f"财神排行榜")
        st.caption(f"评分日期: {date.today()}")
    with col_right:
        st.write("")  # 占位对齐
        refresh = st.button("🔄 重新计算", type="primary", use_container_width=True, help="清除缓存并重新评分")

    # ---- 主区域：排行榜 ----
    ranking = []
    try:
        with st.spinner("正在计算财神指数..."):
            ranking = get_caishen_ranking(user, refresh=refresh)
        logger.info("财神排行榜加载完成: %d 条结果, refresh=%s", len(ranking), refresh)
    except Exception as e:
        logger.error("财神排行榜加载失败: %s", e, exc_info=True)
        st.error(f"加载失败：{e}")

    if not ranking:
        st.warning("暂无评分数据。点击上方「重新计算」按钮生成排行榜。")
        if st.button("🔄 立即计算", type="primary"):
            st.rerun()
        db.close()
        return

    # 汇率
    rate = get_usd_cny_latest() or 7.2
    st.caption(f"当前参考汇率: 1 USD = {rate:.4f} CNY")

    # 构建表格数据
    table_data = []
    for i, r in enumerate(ranking, 1):
        fake_flag = "假" if r["data_source"] == "fake" else "真"
        table_data.append({
            "排名": i,
            "代码": r["stock_code"],
            "名称": r["stock_name"],
            "数据": fake_flag,
            "财神指数": f"{r['composite_score']:.1f}",
            "八字合盘": f"{r['bazi_score']:.1f}",
            "五行匹配": f"{r['wuxing_score']:.1f}",
            "天干择时": f"{r['timing_score']:.1f}",
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "排名": st.column_config.NumberColumn(width="small"),
            "数据": st.column_config.TextColumn(width="small"),
            "财神指数": st.column_config.TextColumn(width="small"),
            "八字合盘": st.column_config.TextColumn(width="small"),
            "五行匹配": st.column_config.TextColumn(width="small"),
            "天干择时": st.column_config.TextColumn(width="small"),
        },
    )

    # 详情展开
    st.divider()
    st.subheader("TOP 5 详细评分")

    for idx, r in enumerate(ranking[:5]):
        with st.expander(
            f"#{idx+1} {r['stock_code']} {r['stock_name']} "
            f"| 财神指数: {r['composite_score']:.1f}"
            f"{' [假数据]' if r['data_source'] == 'fake' else ''}"
        ):
            cols = st.columns(3)
            with cols[0]:
                st.metric("八字合盘", f"{r['bazi_score']:.1f} / 100")
            with cols[1]:
                st.metric("五行匹配", f"{r['wuxing_score']:.1f} / 100")
            with cols[2]:
                st.metric("天干择时", f"{r['timing_score']:.1f} / 100")

            st.markdown(f"**点评**: {r['summary']}")

            # 美元换算示例
            usd_info = get_usd_price(10.0)
            st.caption(
                f"参考: 10 CNY ≈ {usd_info['usd']} USD "
                f"(汇率: {usd_info['rate']}, 来源: {usd_info['rate_source']})"
            )

    db.close()


if __name__ == "__main__":
    stock_picker_page()
