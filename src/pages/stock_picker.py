"""
财神选股 - 八字合盘 & 五行匹配推荐
"""

import streamlit as st
from datetime import date

from src.data.db import db, UserProfile, StockBasic
from src.strategy.scorer import get_caishen_ranking, get_usd_price, score_all_stocks
from src.data.exchange import get_usd_cny_latest


def stock_picker_page():
    st.title("财神选股")
    st.caption("基于八字合盘 + 五行匹配 + 天干择时的综合推荐")

    db.connect()

    # 检查是否有用户
    if "user_id" not in st.session_state:
        user = UserProfile.select().order_by(UserProfile.id.desc()).first()
        if user:
            st.session_state["user_id"] = user.id
        else:
            st.warning("请先在首页输入你的生辰八字")
            db.close()
            return

    user = UserProfile.get_by_id(st.session_state["user_id"])

    with st.sidebar:
        st.header("评分参数")
        refresh = st.button("重新计算评分", type="primary", use_container_width=True)

        st.divider()
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

    # ---- 主区域 ----
    with st.spinner("正在计算财神指数..."):
        ranking = get_caishen_ranking(user, refresh=refresh)

    if not ranking:
        st.warning("暂无评分数据，请先运行数据初始化。")
        db.close()
        return

    # 汇率
    rate = get_usd_cny_latest() or 7.2
    st.caption(f"当前参考汇率: 1 USD = {rate:.4f} CNY")

    # 排行榜表格
    st.subheader(f"财神排行榜 TOP {len(ranking)}")
    st.caption(f"评分日期: {date.today()}")

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

    for r in ranking[:5]:
        with st.expander(
            f"#{ranking.index(r)+1} {r['stock_code']} {r['stock_name']} "
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
