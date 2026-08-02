"""
幸运运势 - 幸运数字 / 幸运颜色 / 幸运方位 / 幸运日 / 个人当日运势
需要用户八字信息，未输入时提示用户前往首页排盘
"""

import streamlit as st
from datetime import date, timedelta

from src.data.db import db
from src.metaphysics.bazi import BaziResult
from src.metaphysics.fortune import (
    LuckyDay,
    PersonalFortune,
    WUXING_COLORS,
    WUXING_DIRECTIONS,
    WUXING_NUMBERS,
    get_lucky_colors,
    get_lucky_days,
    get_lucky_directions,
    get_lucky_numbers,
    get_personal_fortune,
)
from src.metaphysics.wuxing import wuxing_color
from src.utils.logger import get_logger
from src.utils.user_guard import require_user_bazi, get_current_user
from src.components.user_header import render_user_header

logger = get_logger(__name__)


def lucky_page():
    st.title("幸运运势")
    st.caption("幸运数字 · 幸运颜色 · 幸运方位 · 幸运日 · 个人当日运势")

    db.connect()

    # 顶部用户 header
    render_user_header()

    # 守卫：检查用户八字信息
    bazi = require_user_bazi("幸运运势")
    if bazi is None:
        db.close()
        return

    user = get_current_user()
    logger.info("幸运运势页面加载: user=%s, 日主=%s", user.name, bazi.day_master)

    # ---- 侧边栏 ----
    with st.sidebar:
        st.header("用户档案")
        st.markdown(f"**{user.name}**")
        st.markdown(f"日主: **{bazi.day_master}**")
        if bazi.xi_shen:
            xi_display = " ".join([
                f":{wuxing_color(x)}[{x}]"
                for x in bazi.xi_shen
            ])
            st.markdown(f"喜用神: {', '.join(bazi.xi_shen)}")
        if bazi.ji_shen:
            st.markdown(f"忌神: {', '.join(bazi.ji_shen)}")
        st.markdown(f"生肖: {bazi.shengxiao} | {bazi.zodiac}")

        st.divider()
        st.header("扫描设置")
        scan_days = st.slider("幸运日扫描天数", min_value=7, max_value=90, value=30, step=7)
        top_n = st.slider("展示前几名", min_value=3, max_value=15, value=5)

    # ---- 主区域 ----

    # 1. 今日个人运势
    st.subheader("今日个人运势")
    _render_personal_fortune(bazi, date.today())

    # 2. 幸运数字 / 颜色 / 方位
    st.divider()
    st.subheader("你的幸运指标")
    _render_lucky_indicators(bazi)

    # 3. 未来幸运日
    st.divider()
    st.subheader(f"未来 {scan_days} 天幸运日 TOP {top_n}")
    _render_lucky_days(bazi, scan_days, top_n)

    # 4. 五行数字颜色方位对照表
    st.divider()
    with st.expander("五行数字 / 颜色 / 方位 对照表"):
        _render_reference_table()

    db.close()


def _render_personal_fortune(bazi: BaziResult, target_date: date):
    """渲染个人当日运势"""
    try:
        fortune = get_personal_fortune(bazi, target_date)
    except Exception as e:
        logger.error("个人运势计算失败: %s", e, exc_info=True)
        st.error(f"运势计算失败: {e}")
        return

    # 运势评分
    score = fortune.overall_score
    if score >= 80:
        level, color = "大吉", "#26a65b"
    elif score >= 65:
        level, color = "吉", "#2ecc71"
    elif score >= 50:
        level, color = "平", "#f39c12"
    elif score >= 35:
        level, color = "小凶", "#e67e22"
    else:
        level, color = "凶", "#e74c3c"

    # 运势卡片
    cols = st.columns([1, 1, 1, 1])

    with cols[0]:
        st.metric("综合运势", f"{score} 分")
        st.markdown(
            f"<span style='color:{color}; font-size:20px; font-weight:bold;'>{level}</span>",
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.metric("日柱", f"{fortune.day_gan}{fortune.day_zhi}")
        st.caption(f"五行: {fortune.day_wuxing}")

    with cols[2]:
        st.metric("财神方位", fortune.wealth_direction)
        st.caption(fortune.relation_to_day_master)

    with cols[3]:
        st.metric("幸运数字", " ".join(str(n) for n in fortune.lucky_numbers[:4]))

    # 建议
    st.info(fortune.advice)

    # 幸运颜色和方位
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**幸运颜色**")
        color_html = []
        for c in fortune.lucky_colors[:5]:
            color_html.append(
                f"<span style='display:inline-block; margin:2px 4px; "
                f"padding:4px 12px; border-radius:12px; "
                f"background:#f0f0f0; font-size:13px;'>{c}</span>"
            )
        st.markdown("".join(color_html), unsafe_allow_html=True)

    with col2:
        st.markdown("**幸运方位**")
        dir_html = []
        for d in fortune.lucky_directions[:5]:
            dir_html.append(
                f"<span style='display:inline-block; margin:2px 4px; "
                f"padding:4px 12px; border-radius:12px; "
                f"background:#e8f0fe; font-size:13px;'>{d}</span>"
            )
        st.markdown("".join(dir_html), unsafe_allow_html=True)

    # 幸运板块提示
    if fortune.lucky_stocks_hint:
        st.markdown("**幸运板块提示**")
        st.markdown(" | ".join(fortune.lucky_stocks_hint))

    logger.info("个人运势展示完成: score=%d, level=%s", score, level)


def _render_lucky_indicators(bazi: BaziResult):
    """渲染幸运数字、颜色、方位"""
    numbers = get_lucky_numbers(bazi)
    colors = get_lucky_colors(bazi)
    directions = get_lucky_directions(bazi)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 幸运数字")
        num_html = []
        for n in numbers[:6]:
            num_html.append(
                f"<span style='display:inline-flex; align-items:center; "
                f"justify-content:center; width:36px; height:36px; margin:3px; "
                f"border-radius:50%; background:#1a1a2e; color:#FFD700; "
                f"font-size:16px; font-weight:bold;'>{n}</span>"
            )
        st.markdown("".join(num_html), unsafe_allow_html=True)
        st.caption("基于河图洛书五行数字")

    with col2:
        st.markdown("#### 幸运颜色")
        color_html = []
        for c in colors[:6]:
            color_html.append(
                f"<span style='display:inline-block; margin:3px; "
                f"padding:6px 14px; border-radius:8px; "
                f"background:#f5f5f5; border:1px solid #ddd; "
                f"font-size:13px;'>{c}</span>"
            )
        st.markdown("".join(color_html), unsafe_allow_html=True)
        st.caption("基于喜用神五行色系")

    with col3:
        st.markdown("#### 幸运方位")
        dir_html = []
        for d in directions[:5]:
            dir_html.append(
                f"<span style='display:inline-block; margin:3px; "
                f"padding:6px 14px; border-radius:8px; "
                f"background:#e8f0fe; border:1px solid #b3d4fc; "
                f"font-size:13px;'>{d}</span>"
            )
        st.markdown("".join(dir_html), unsafe_allow_html=True)
        st.caption("基于喜用神五行方位")


def _render_lucky_days(bazi: BaziResult, scan_days: int, top_n: int):
    """渲染幸运日列表"""
    with st.spinner(f"正在扫描未来 {scan_days} 天的运势..."):
        lucky_days = get_lucky_days(bazi, days=scan_days, top_n=top_n)

    if not lucky_days:
        st.warning("无法计算幸运日，请检查八字数据")
        return

    for i, ld in enumerate(lucky_days, 1):
        level_color = _level_color(ld.level)

        with st.expander(
            f"#{i} {ld.date.strftime('%Y-%m-%d')} ({_weekday_cn(ld.date)}) "
            f"{ld.gan}{ld.zhi}({ld.wuxing}) "
            f"[{ld.level}] {ld.score}分"
            f"{' — 非交易日' if not ld.is_trading_day else ''}"
        ):
            cols = st.columns([1, 1, 2])

            with cols[0]:
                st.metric("运势评分", f"{ld.score} / 100")
                st.markdown(
                    f"<span style='color:{level_color}; font-size:18px; "
                    f"font-weight:bold;'>{ld.level}</span>",
                    unsafe_allow_html=True,
                )

            with cols[1]:
                st.metric("日柱", f"{ld.gan}{ld.zhi}")
                st.caption(f"五行: {ld.wuxing}")
                if not ld.is_trading_day:
                    st.warning(f"非交易日: {ld.non_trading_reason}")

            with cols[2]:
                st.markdown("**运势原因**")
                for r in ld.reasons:
                    st.markdown(f"- {r}")

            # 黄历
            if ld.yi or ld.ji:
                st.divider()
                col_y, col_j = st.columns(2)
                with col_y:
                    st.markdown("**宜**")
                    if ld.yi:
                        st.markdown("、".join(ld.yi[:8]))
                    else:
                        st.caption("无")
                with col_j:
                    st.markdown("**忌**")
                    if ld.ji:
                        st.markdown("、".join(ld.ji[:8]))
                    else:
                        st.caption("无")

    st.caption(f"共扫描 {scan_days} 天，展示运势最高的 {len(lucky_days)} 天")


def _render_reference_table():
    """五行数字颜色方位对照表"""
    import pandas as pd

    rows = []
    for wx in ["金", "木", "水", "火", "土"]:
        rows.append({
            "五行": wx,
            "幸运数字": "、".join(str(n) for n in WUXING_NUMBERS[wx]),
            "幸运颜色": "、".join(WUXING_COLORS[wx]),
            "幸运方位": "、".join(WUXING_DIRECTIONS[wx]),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("河图洛书：天一生水地六成之，地二生火天七成之，天三生木地八成之，地四生金天九成之，天五生土地十成之。")


def _level_color(level: str) -> str:
    """运势等级颜色"""
    return {
        "大吉": "#26a65b",
        "吉": "#2ecc71",
        "平": "#f39c12",
        "小凶": "#e67e22",
        "凶": "#e74c3c",
    }.get(level, "#888888")


def _weekday_cn(d: date) -> str:
    """中文星期"""
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[d.weekday()]


if __name__ == "__main__":
    lucky_page()
