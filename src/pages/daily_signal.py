"""
每日择时信号 - 天干地支 + 黄历 + 节气
"""

import streamlit as st
from datetime import date, timedelta

from src.data.db import db, DailySignal, UserProfile
from src.metaphysics.ganzhi import get_daily_signal, get_jieqi_rotation
from src.metaphysics.wuxing import (
    get_wuxing_compatible_sectors,
    get_wuxing_avoid_sectors,
    wuxing_color,
)
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_user
from src.components.user_header import render_user_header

logger = get_logger(__name__)


def daily_signal_page():
    st.title("每日玄学信号")
    st.caption("天干地支择时 · 黄历宜忌 · 节气轮动")

    db.connect(reuse_if_open=True)

    # 顶部用户 header
    render_user_header()

    # 获取当前用户（每日信号页用户信息为可选，但用户专属建议需要）
    user = get_current_user()
    user_xi_shen = []
    if user:
        user_xi_shen = user.xi_shen.split(",") if user.xi_shen else []
        logger.info("每日信号页面加载: user=%s", user.name)

    # ---- 侧边栏 ----
    with st.sidebar:
        st.header("日期选择")
        selected_date = st.date_input(
            "选择日期",
            value=date.today(),
            min_value=date(2020, 1, 1),
            max_value=date.today() + timedelta(days=30),
        )

        if user:
            st.divider()
            st.subheader("用户信息")
            st.markdown(f"**{user.name}**")
            st.markdown(f"日主: **{user.day_master}**")
            if user_xi_shen:
                xi_display = " ".join([
                    f"<span style='color:{wuxing_color(x)}'>{x}</span>"
                    for x in user_xi_shen
                ])
                st.markdown(f"喜用神: {', '.join(user_xi_shen)}", unsafe_allow_html=True)

    # ---- 主区域 ----
    try:
        logger.info("获取每日信号: date=%s", selected_date.isoformat())
        signal = get_daily_signal(selected_date)
    except Exception as e:
        logger.error("获取每日信号失败: date=%s, error=%s", selected_date.isoformat(), e, exc_info=True)
        st.error(f"获取信号失败: {e}")
        db.close()
        return

    # 非交易日提示
    if not signal.get("is_trading_day", True):
        reason = signal.get("non_trading_reason") or "非交易日"
        st.warning(f"⚠️ **{selected_date} 非交易日** — {reason}，A股休市，无交易信号")

    # 日柱卡片
    st.subheader(f"{selected_date} 日柱信息")

    cols = st.columns(3)
    with cols[0]:
        st.metric("日柱", f"{signal['day_gan']}{signal['day_zhi']}")
    with cols[1]:
        st.metric("五行", signal["day_wuxing"])
    with cols[2]:
        st.metric("交易信号", signal["trade_signal"])

    if signal.get("caishen"):
        st.caption(f"财神方位: {signal['caishen']}")

    if signal.get("jieqi"):
        st.info(f"**节气日: {signal['jieqi']}**")
        jieqi_info = get_jieqi_rotation(selected_date)
        if jieqi_info:
            st.markdown(f"节气推荐板块: {', '.join(jieqi_info['sectors'][:8])}")

    # 黄历
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("宜")
        yi_list = signal.get("yi", [])
        if yi_list:
            for item in yi_list[:10]:
                st.markdown(f"- {item}")
        else:
            st.caption("无")

    with col2:
        st.subheader("忌")
        ji_list = signal.get("ji", [])
        if ji_list:
            for item in ji_list[:10]:
                st.markdown(f"- {item}")
        else:
            st.caption("无")

    # 五行推荐
    st.divider()
    st.subheader("五行板块建议")

    rec = signal.get("recommended_wuxing", [])
    avoid = signal.get("avoid_wuxing", [])

    col1, col2 = st.columns(2)
    rec_sectors = []
    with col1:
        st.markdown("**推荐关注**")
        if rec:
            for wx in rec:
                rec_sectors.extend(get_wuxing_compatible_sectors([wx]))
            rec_sectors = list(set(rec_sectors))
            for s in rec_sectors[:8]:
                st.markdown(f"- {s}")
        else:
            st.caption("无")

    with col2:
        st.markdown("**建议回避**")
        if avoid:
            avoid_sectors = []
            for wx in avoid:
                avoid_sectors.extend(get_wuxing_avoid_sectors([wx]))
            avoid_sectors = list(set(avoid_sectors) - set(rec_sectors))
            for s in avoid_sectors[:8]:
                st.markdown(f"- {s}")
        else:
            st.caption("无")

    # 用户专属建议
    if user_xi_shen:
        st.divider()
        st.subheader("你的专属建议")
        user_rec = []
        for wx in user_xi_shen:
            if wx in rec:
                user_rec.append(wx)

        if user_rec:
            st.success(f"今日五行 {', '.join(user_rec)} 与你的喜用神契合，建议关注相关板块")
            user_sectors = get_wuxing_compatible_sectors(user_rec)
            for s in user_sectors[:6]:
                st.markdown(f"- {s}")
        else:
            st.info("今日五行与你的喜用神无直接契合，建议观望为主")

    # 最近7天信号概览
    st.divider()
    st.subheader("最近一周信号概览")

    week_signals = []
    for i in range(7, 0, -1):
        d = date.today() - timedelta(days=i)
        try:
            ds = DailySignal.select().where(DailySignal.date == d).first()
            if ds:
                week_signals.append(ds)
            else:
                s = get_daily_signal(d)
                week_signals.append(s)
        except Exception:
            continue

    if week_signals:
        cols = st.columns(len(week_signals))
        for idx, ws in enumerate(week_signals):
            with cols[idx]:
                if isinstance(ws, DailySignal):
                    s_date = ws.date.strftime("%m/%d")
                    s_gan_zhi = f"{ws.day_gan}{ws.day_zhi}"
                    s_signal = ws.trade_signal
                else:
                    s_date = ws["date"][5:]
                    s_gan_zhi = f"{ws['day_gan']}{ws['day_zhi']}"
                    s_signal = ws["trade_signal"]

                signal_emoji = {
                    "宜买入": "🟢", "忌交易": "🔴", "宜观望": "⚪", "休市": "🟫",
                }
                emoji = signal_emoji.get(s_signal, "⚪")
                st.markdown(f"**{s_date}**")
                st.markdown(f"*{s_gan_zhi}*")
                st.markdown(f"{emoji} {s_signal}")

    db.close()


if __name__ == "__main__":
    daily_signal_page()
