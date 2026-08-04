"""
星座算命 - 基于西方占星学的运势计算
展示：今日运势（综合/财运/事业/爱情）· 幸运指标 · 适配板块 · 星象详情 · 未来幸运日 · 星座档案 · 星座配对
"""

import streamlit as st
from datetime import date, timedelta

from src.data.db import db
from src.metaphysics.bazi import get_zodiac
from src.metaphysics.constellation import (
    ZODIAC_PROFILES,
    ZodiacProfile,
    ConstellationFortune,
    ConstellationDayScore,
    ELEMENT_DESC,
    ELEMENT_COMPAT,
    WEEKDAY_CN,
    WEEKDAY_PLANET,
    MODALITY_DESC,
    get_zodiac_profile,
    get_constellation_fortune,
    get_constellation_lucky_days,
    zodiac_compatibility,
    is_mercury_retrograde,
    get_moon_phase,
)
from src.utils.logger import get_logger
from src.utils.user_guard import require_user_profile, get_current_user
from src.components.user_header import render_user_header

logger = get_logger(__name__)


def constellation_page():
    st.title("星座算命")
    st.caption("西方占星 · 元素和谐 · 守护星 · 月相 · 水星逆行 · 幸运日预测")

    db.connect(reuse_if_open=True)

    # 顶部用户 header
    render_user_header()

    # 守卫：需要用户档案
    user = require_user_profile("星座算命")
    if user is None:
        db.close()
        return

    # 获取星座（优先用 DB 存储的，否则从生日计算）
    zodiac = user.zodiac
    if not zodiac and user.birth_date:
        zodiac = get_zodiac(user.birth_date.month, user.birth_date.day)

    if not zodiac:
        st.warning("无法确定你的星座，请检查出生日期是否正确")
        db.close()
        return

    profile = get_zodiac_profile(zodiac)
    if profile is None:
        st.error(f"未知星座: {zodiac}")
        db.close()
        return

    logger.info("星座算命页面加载: user=%s, zodiac=%s", user.name, zodiac)

    # ── 侧边栏：用户星座信息 ──
    with st.sidebar:
        st.header("你的星座")
        st.markdown(f"### {profile.symbol} {profile.name}")
        st.markdown(f"**{profile.name_en}**")
        st.caption(profile.traits)

        st.divider()
        st.markdown(f"**元素**: {profile.element}（{ELEMENT_DESC[profile.element]}）")
        st.markdown(f"**模式**: {profile.modality}")
        st.markdown(f"**守护星**: {profile.ruling_planet}")
        if profile.co_ruling_planet != profile.ruling_planet:
            st.markdown(f"**副守护星**: {profile.co_ruling_planet}")
        st.markdown(f"**幸运星期**: {WEEKDAY_CN[profile.lucky_weekday]}")
        st.markdown(f"**幸运方位**: {profile.lucky_direction}")

        st.divider()
        st.header("扫描设置")
        scan_days = st.slider("幸运日扫描天数", min_value=7, max_value=90, value=30, step=7)
        top_n = st.slider("展示前几名", min_value=3, max_value=15, value=5)

    # ── 主区域：Tab 切换 ──
    tab_fortune, tab_lucky_days, tab_profile, tab_compat = st.tabs([
        "今日运势", "未来幸运日", "星座档案", "星座配对",
    ])

    with tab_fortune:
        _render_today_fortune(zodiac, profile)

    with tab_lucky_days:
        _render_lucky_days(zodiac, scan_days, top_n)

    with tab_profile:
        _render_all_profiles(zodiac)

    with tab_compat:
        _render_compatibility(zodiac)

    db.close()


# ═══════════════════════════════════════════════════════════
#  今日运势
# ═══════════════════════════════════════════════════════════

def _render_today_fortune(zodiac: str, profile: ZodiacProfile):
    """渲染今日星座运势"""
    today = date.today()
    try:
        fortune = get_constellation_fortune(zodiac, today)
    except Exception as e:
        logger.error("星座运势计算失败: %s", e, exc_info=True)
        st.error(f"运势计算失败: {e}")
        return

    if fortune is None:
        st.error("无法计算运势")
        return

    # ── 运势评分卡片 ──
    st.subheader(f"{today.strftime('%Y-%m-%d')} ({WEEKDAY_CN[today.weekday()]}) 星座运势")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        score, level, color = fortune.overall_score, *_level_info(fortune.overall_score)
        st.metric("综合运势", f"{score} 分")
        st.markdown(
            f"<span style='color:{color}; font-size:20px; font-weight:bold;'>{level}</span>",
            unsafe_allow_html=True,
        )

    with col2:
        score, level, color = fortune.wealth_score, *_level_info(fortune.wealth_score)
        st.metric("💰 财运", f"{score} 分")
        st.markdown(
            f"<span style='color:{color}; font-size:14px;'>{level}</span>",
            unsafe_allow_html=True,
        )

    with col3:
        score, level, color = fortune.career_score, *_level_info(fortune.career_score)
        st.metric("📊 事业运", f"{score} 分")
        st.markdown(
            f"<span style='color:{color}; font-size:14px;'>{level}</span>",
            unsafe_allow_html=True,
        )

    with col4:
        score, level, color = fortune.love_score, *_level_info(fortune.love_score)
        st.metric("❤️ 爱情运", f"{score} 分")
        st.markdown(
            f"<span style='color:{color}; font-size:14px;'>{level}</span>",
            unsafe_allow_html=True,
        )

    # ── 交易建议 ──
    st.info(fortune.advice)

    # ── 幸运指标 ──
    st.divider()
    col_luck1, col_luck2, col_luck3 = st.columns(3)

    with col_luck1:
        st.markdown("#### 幸运数字")
        num_html = []
        for n in fortune.lucky_numbers:
            num_html.append(
                f"<span style='display:inline-flex; align-items:center; "
                f"justify-content:center; width:40px; height:40px; margin:3px; "
                f"border-radius:50%; background:#1a1a2e; color:#FFD700; "
                f"font-size:18px; font-weight:bold;'>{n}</span>"
            )
        st.markdown("".join(num_html), unsafe_allow_html=True)

    with col_luck2:
        st.markdown("#### 幸运颜色")
        color_html = []
        for c in fortune.lucky_colors:
            color_html.append(
                f"<span style='display:inline-block; margin:3px; "
                f"padding:6px 14px; border-radius:8px; "
                f"background:#f5f5f5; border:1px solid #ddd; "
                f"font-size:13px;'>{c}</span>"
            )
        st.markdown("".join(color_html), unsafe_allow_html=True)

    with col_luck3:
        st.markdown("#### 幸运方位")
        st.markdown(
            f"<span style='display:inline-block; margin:3px; "
            f"padding:8px 20px; border-radius:8px; "
            f"background:#e8f0fe; border:1px solid #b3d4fc; "
            f"font-size:16px; font-weight:bold;'>🧭 {fortune.lucky_direction}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"幸运星期: {fortune.lucky_weekday}")

    # ── 适配板块 ──
    st.divider()
    st.markdown("#### 适配A股板块")
    sector_html = []
    for s in fortune.favorable_sectors:
        sector_html.append(
            f"<span style='display:inline-block; margin:3px 6px; "
            f"padding:6px 16px; border-radius:16px; "
            f"background:#fff3e0; border:1px solid #ffb74d; "
            f"font-size:14px; font-weight:500;'>{s}</span>"
        )
    st.markdown("".join(sector_html), unsafe_allow_html=True)
    st.caption(f"交易风格: {fortune.trading_style}")

    # ── 星象详情 ──
    st.divider()
    st.markdown("#### 今日星象详情")

    detail_cols = st.columns(4)
    with detail_cols[0]:
        st.metric("太阳星座", fortune.sun_sign)
        st.caption(fortune.element_harmony)

    with detail_cols[1]:
        st.metric("月相", f"{fortune.moon_emoji} {fortune.moon_phase}")
        _, _, _, moon_desc = get_moon_phase(today)
        st.caption(moon_desc)

    with detail_cols[2]:
        st.metric("今日守护星", fortune.ruling_planet_today)
        if fortune.is_planet_day:
            st.markdown("⭐ **守护星日！能量加成**")
        else:
            st.caption(f"你的守护星: {profile.ruling_planet}")

    with detail_cols[3]:
        if fortune.mercury_retrograde:
            st.metric("水星状态", "⚠️ 逆行")
            st.caption(fortune.mercury_desc or "")
        else:
            st.metric("水星状态", "✅ 顺行")
            st.caption("沟通顺畅，决策清晰")

    # ── 评分理由 ──
    with st.expander("查看评分明细"):
        for r in fortune.reasons:
            st.markdown(f"- {r}")


# ═══════════════════════════════════════════════════════════
#  未来幸运日
# ═══════════════════════════════════════════════════════════

def _render_lucky_days(zodiac: str, scan_days: int, top_n: int):
    """渲染未来幸运日列表"""
    st.subheader(f"未来 {scan_days} 天幸运日 TOP {top_n}")

    with st.spinner(f"正在用占星学扫描未来 {scan_days} 天..."):
        lucky_days = get_constellation_lucky_days(zodiac, days=scan_days, top_n=top_n)

    if not lucky_days:
        st.warning("无法计算幸运日")
        return

    for i, ld in enumerate(lucky_days, 1):
        level_color = _level_color(ld.level)

        with st.expander(
            f"#{i} {ld.date.strftime('%Y-%m-%d')} ({WEEKDAY_CN[ld.date.weekday()]}) "
            f"[{ld.level}] {ld.score}分"
            f"  {ld.moon_emoji}{ld.moon_phase}"
            f"{'  ⚠️水逆' if ld.mercury_retrograde else ''}"
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
                st.metric("太阳星座", ld.sun_sign)
                st.caption(f"月相: {ld.moon_emoji} {ld.moon_phase}")
                st.caption(f"守护星: {ld.ruling_planet_today}")
                if not ld.is_trading_day:
                    st.warning(f"非交易日: {ld.non_trading_reason}")

            with cols[2]:
                st.markdown("**评分依据**")
                for r in ld.reasons:
                    st.markdown(f"- {r}")

    st.caption(f"共扫描 {scan_days} 天，展示运势最高的 {len(lucky_days)} 天")


# ═══════════════════════════════════════════════════════════
#  星座档案
# ═══════════════════════════════════════════════════════════

def _render_all_profiles(user_zodiac: str):
    """渲染12星座档案"""
    st.subheader("十二星座档案")

    for name, p in ZODIAC_PROFILES.items():
        is_user = (name == user_zodiac)

        with st.expander(
            f"{p.symbol} {p.name} ({p.name_en})"
            f"{'  ⬅️ 你的星座' if is_user else ''}"
            f"  [{p.element}/{p.modality}/{p.ruling_planet}]"
        ):
            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown(f"**元素**: {p.element}（{ELEMENT_DESC[p.element]}）")
                st.markdown(f"**模式**: {p.modality}")
                st.markdown(f"**守护星**: {p.ruling_planet}")
                if p.co_ruling_planet != p.ruling_planet:
                    st.markdown(f"**副守护星**: {p.co_ruling_planet}")
                st.markdown(f"**幸运数字**: {'、'.join(str(n) for n in p.lucky_numbers)}")
                st.markdown(f"**幸运颜色**: {'、'.join(p.lucky_colors)}")
                st.markdown(f"**幸运方位**: {p.lucky_direction}")
                st.markdown(f"**幸运星期**: {WEEKDAY_CN[p.lucky_weekday]}")

            with col2:
                st.markdown(f"**性格关键词**: {' · '.join(p.keywords)}")
                st.caption(p.traits)
                st.divider()
                st.markdown(f"**交易风格**: {p.trading_style}")
                st.markdown(f"**适配板块**: {' · '.join(p.favorable_sectors)}")


# ═══════════════════════════════════════════════════════════
#  星座配对
# ═══════════════════════════════════════════════════════════

def _render_compatibility(user_zodiac: str):
    """渲染星座配对兼容性"""
    st.subheader("星座配对")
    st.caption("选择另一个星座，查看与你的兼容性")

    other = st.selectbox(
        "选择配对星座",
        options=list(ZODIAC_PROFILES.keys()),
        index=0,
    )

    if other:
        score, desc = zodiac_compatibility(user_zodiac, other)

        # 评分展示
        col_s, col_d = st.columns([1, 2])
        with col_s:
            if score >= 80:
                color = "#26a65b"
                label = "天作之合"
            elif score >= 65:
                color = "#2ecc71"
                label = "十分契合"
            elif score >= 50:
                color = "#f39c12"
                label = "尚可相处"
            else:
                color = "#e74c3c"
                label = "需要磨合"

            st.metric("配对评分", f"{score} / 100")
            st.markdown(
                f"<span style='color:{color}; font-size:22px; "
                f"font-weight:bold;'>{label}</span>",
                unsafe_allow_html=True,
            )

        with col_d:
            st.markdown("**分析**")
            st.markdown(desc)

        # 12 星座配对总览
        st.divider()
        st.markdown("#### 与全部星座配对总览")

        compat_data = []
        for name, p in ZODIAC_PROFILES.items():
            s, d = zodiac_compatibility(user_zodiac, name)
            if s >= 80:
                emoji = "💕"
            elif s >= 65:
                emoji = "😊"
            elif s >= 50:
                emoji = "😐"
            else:
                emoji = "😅"

            compat_data.append({
                "星座": f"{p.symbol} {name}",
                "元素": p.element,
                "配对评分": f"{emoji} {s}",
                "分析": d,
            })

        import pandas as pd
        df = pd.DataFrame(compat_data)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════

def _level_info(score: int) -> tuple[str, str]:
    """评分 → (等级, 颜色)"""
    if score >= 80:
        return "大吉", "#26a65b"
    elif score >= 65:
        return "吉", "#2ecc71"
    elif score >= 50:
        return "平", "#f39c12"
    elif score >= 35:
        return "小凶", "#e67e22"
    else:
        return "凶", "#e74c3c"


def _level_color(level: str) -> str:
    return {
        "大吉": "#26a65b",
        "吉": "#2ecc71",
        "平": "#f39c12",
        "小凶": "#e67e22",
        "凶": "#e74c3c",
    }.get(level, "#888888")


if __name__ == "__main__":
    constellation_page()
