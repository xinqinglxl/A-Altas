"""
首页 - 用户八字档案输入
"""

import streamlit as st
from datetime import date, datetime

from src.data.db import db, UserProfile
from src.metaphysics.bazi import calc_bazi, BaziResult
from src.strategy.scorer import get_caishen_ranking
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_user
from src.components.user_header import render_user_header

logger = get_logger(__name__)


def show_bazi_card(bazi: BaziResult):
    """展示八字结果卡片"""
    cols = st.columns(4)
    pillars = [
        ("年柱", bazi.year_gan, bazi.year_zhi),
        ("月柱", bazi.month_gan, bazi.month_zhi),
        ("日柱", bazi.day_gan, bazi.day_zhi),
        ("时柱", bazi.hour_gan, bazi.hour_zhi),
    ]
    for col, (label, gan, zhi) in zip(cols, pillars):
        with col:
            st.markdown(f"**{label}**")
            st.markdown(f"### {gan}{zhi}")

    st.markdown(f"**日主五行**: {bazi.day_master} | **生肖**: {bazi.shengxiao} | **星座**: {bazi.zodiac}")
    st.markdown(f"**喜用神**: {', '.join(bazi.xi_shen) if bazi.xi_shen else '无'} | **忌神**: {', '.join(bazi.ji_shen) if bazi.ji_shen else '无'}")


def home_page():
    st.title("A-ALTAS 玄学量化")
    st.caption("输入你的生辰，开始玄学选股之旅")

    db.connect()

    # 顶部用户 header — 展示已登录用户信息和运势
    render_user_header()

    # ---- 侧边栏 ----
    with st.sidebar:
        st.header("用户档案")
        name = st.text_input("昵称", value="默认用户")
        col1, col2 = st.columns(2)
        with col1:
            sex = st.selectbox("性别", ["男", "女"], index=0)
        with col2:
            is_solar = st.selectbox("历法", ["公历", "农历"], index=0)

        birth_date = st.date_input(
            "出生日期",
            value=date(1990, 1, 1),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
        )

        birth_time = st.selectbox(
            "出生时辰",
            ["00:00 (子时)", "01:00 (丑时)", "03:00 (寅时)", "05:00 (卯时)",
             "07:00 (辰时)", "09:00 (巳时)", "11:00 (午时)", "13:00 (未时)",
             "15:00 (申时)", "17:00 (酉时)", "19:00 (戌时)", "21:00 (亥时)"],
            index=6,
        )

        submit = st.button("排盘并保存", type="primary", use_container_width=True)

        st.divider()
        st.markdown("---")
        st.caption("数据说明：股票成立日期为估算数据，八字合盘仅供参考娱乐。")

    # ---- 主区域 ----
    if submit:
        hour = int(birth_time.split(":")[0])
        logger.info("用户提交排盘: name=%s, date=%s, time=%02d:00, solar=%s",
                     name, birth_date.isoformat(), hour, is_solar)
        try:
            bazi = calc_bazi(
                birth_date,
                f"{hour:02d}:00",
                is_solar=(is_solar == "公历"),
            )

            # 保存到数据库
            xi_str = ",".join(bazi.xi_shen)
            ji_str = ",".join(bazi.ji_shen)
            user, created = UserProfile.get_or_create(
                birth_date=birth_date,
                defaults={
                    "name": name,
                    "sex": 1 if sex == "男" else 0,
                    "birth_time": f"{hour:02d}:00",
                    "is_solar": is_solar == "公历",
                    "year_gan": bazi.year_gan,
                    "year_zhi": bazi.year_zhi,
                    "month_gan": bazi.month_gan,
                    "month_zhi": bazi.month_zhi,
                    "day_gan": bazi.day_gan,
                    "day_zhi": bazi.day_zhi,
                    "hour_gan": bazi.hour_gan,
                    "hour_zhi": bazi.hour_zhi,
                    "day_master": bazi.day_master,
                    "shengxiao": bazi.shengxiao,
                    "zodiac": bazi.zodiac,
                    "xi_shen": xi_str,
                    "ji_shen": ji_str,
                },
            )

            st.session_state["user_id"] = user.id
            st.session_state["user_bazi"] = bazi

            if created:
                st.success(f"八字排盘已保存 ({name})")
                logger.info("新用户已创建: %s", name)
            else:
                st.info(f"档案已存在，已加载 ({name})")
                logger.info("用户已存在，加载档案: %s", name)

            st.subheader("你的八字命盘")
            show_bazi_card(bazi)

        except Exception as e:
            logger.error("排盘失败: %s", e, exc_info=True)
            st.error(f"排盘失败：{e}")

    # 如果已有用户，显示八字信息
    elif "user_id" in st.session_state and st.session_state.get("user_bazi"):
        st.subheader("你的八字命盘")
        show_bazi_card(st.session_state["user_bazi"])

    # 加载已有用户
    else:
        user = get_current_user()
        if user:
            bazi = calc_bazi(user.birth_date, user.birth_time, user.is_solar)
            st.session_state["user_id"] = user.id
            st.session_state["user_bazi"] = bazi
            st.success(f"已加载用户: {user.name}")

            st.subheader("你的八字命盘")
            show_bazi_card(bazi)

    db.close()


if __name__ == "__main__":
    home_page()
