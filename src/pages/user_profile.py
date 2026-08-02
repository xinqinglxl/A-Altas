"""
用户管理 — 查看和编辑用户八字档案
"""

import streamlit as st
from datetime import date, datetime

from src.data.db import db, UserProfile
from src.metaphysics.bazi import calc_bazi, BaziResult
from src.metaphysics.wuxing import wuxing_color
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_bazi, get_current_user

logger = get_logger(__name__)


def user_profile_page():
    st.title("用户管理")
    st.caption("查看和编辑你的八字档案")

    db.connect(reuse_if_open=True)

    user = get_current_user()
    if user is None:
        st.warning("尚未创建用户档案，请先前往 **八字排盘** 页面输入生辰信息。")
        st.page_link("src/pages/home.py", label="前往八字排盘 →")
        db.close()
        return

    bazi = get_current_bazi()

    # ── 当前八字命盘 ──
    st.subheader("八字命盘")
    if bazi:
        _show_bazi_card(bazi)
    else:
        st.warning("八字数据异常，请重新排盘")

    # ── 用户档案信息 ──
    st.divider()
    st.subheader("档案信息")
    _show_profile_info(user)

    # ── 编辑表单 ──
    st.divider()
    st.subheader("编辑档案")

    with st.form("edit_user_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_name = st.text_input("昵称", value=user.name)
        with col2:
            new_sex = st.selectbox(
                "性别",
                ["男", "女"],
                index=0 if user.sex == 1 else 1,
            )
        with col3:
            new_is_solar = st.selectbox(
                "历法",
                ["公历", "农历"],
                index=0 if user.is_solar else 1,
            )

        new_birth_date = st.date_input(
            "出生日期",
            value=user.birth_date,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
        )

        all_hours = [
            "00:00 (子时)", "01:00 (丑时)", "03:00 (寅时)", "05:00 (卯时)",
            "07:00 (辰时)", "09:00 (巳时)", "11:00 (午时)", "13:00 (未时)",
            "15:00 (申时)", "17:00 (酉时)", "19:00 (戌时)", "21:00 (亥时)",
        ]
        current_hour_idx = _find_hour_index(user.birth_time, all_hours)
        new_birth_time = st.selectbox("出生时辰", all_hours, index=current_hour_idx)

        submitted = st.form_submit_button("保存修改", type="primary", use_container_width=True)

        if submitted:
            hour = int(new_birth_time.split(":")[0])
            birth_time_str = f"{hour:02d}:00"
            is_solar_bool = new_is_solar == "公历"

            try:
                new_bazi = calc_bazi(
                    new_birth_date,
                    birth_time_str,
                    is_solar=is_solar_bool,
                )

                xi_str = ",".join(new_bazi.xi_shen)
                ji_str = ",".join(new_bazi.ji_shen)

                user.name = new_name
                user.sex = 1 if new_sex == "男" else 0
                user.birth_date = new_birth_date
                user.birth_time = birth_time_str
                user.is_solar = is_solar_bool
                user.year_gan = new_bazi.year_gan
                user.year_zhi = new_bazi.year_zhi
                user.month_gan = new_bazi.month_gan
                user.month_zhi = new_bazi.month_zhi
                user.day_gan = new_bazi.day_gan
                user.day_zhi = new_bazi.day_zhi
                user.hour_gan = new_bazi.hour_gan
                user.hour_zhi = new_bazi.hour_zhi
                user.day_master = new_bazi.day_master
                user.xi_shen = xi_str
                user.ji_shen = ji_str
                user.shengxiao = new_bazi.shengxiao
                user.zodiac = new_bazi.zodiac
                user.save()

                # 更新 session_state，让其他页面即时生效
                st.session_state["user_id"] = user.id
                st.session_state["user_bazi"] = new_bazi

                logger.info("用户档案已更新: %s", new_name)
                st.success(f"档案已更新！日主: {new_bazi.day_master}，喜用神: {', '.join(new_bazi.xi_shen)}")
                st.rerun()

            except Exception as e:
                logger.error("更新用户档案失败: %s", e, exc_info=True)
                st.error(f"保存失败：{e}")

    # ── 危险操作区 ──
    st.divider()
    with st.expander("⚠️ 危险操作"):
        st.markdown("**删除当前用户档案**")
        st.caption("这将清除你的所有用户数据和评分缓存。此操作不可撤销。")
        if st.button("删除用户档案", type="secondary"):
            if st.session_state.get("_confirm_delete_user"):
                try:
                    user.delete_instance()
                    st.session_state.pop("user_id", None)
                    st.session_state.pop("user_bazi", None)
                    st.session_state.pop("_confirm_delete_user", None)
                    logger.warning("用户档案已删除: %s", user.name)
                    st.success("用户档案已删除")
                    st.rerun()
                except Exception as e:
                    logger.error("删除用户失败: %s", e, exc_info=True)
                    st.error(f"删除失败：{e}")
            else:
                st.session_state["_confirm_delete_user"] = True
                st.warning("再次点击确认删除")
                st.rerun()

    db.close()


def _show_bazi_card(bazi: BaziResult):
    """展示八字命盘卡片"""
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

    st.markdown(
        f"**日主五行**: {bazi.day_master} | **生肖**: {bazi.shengxiao} | **星座**: {bazi.zodiac}"
    )
    st.markdown(
        f"**喜用神**: {', '.join(bazi.xi_shen) if bazi.xi_shen else '无'} "
        f"| **忌神**: {', '.join(bazi.ji_shen) if bazi.ji_shen else '无'}"
    )


def _show_profile_info(user: UserProfile):
    """展示用户档案信息"""
    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**昵称**: {user.name}")
        st.markdown(f"**性别**: {'男' if user.sex == 1 else '女'}")
        st.markdown(f"**历法**: {'公历' if user.is_solar else '农历'}")
    with cols[1]:
        st.markdown(f"**出生日期**: {user.birth_date}")
        st.markdown(f"**出生时辰**: {user.birth_time}")
        st.markdown(f"**日主五行**: {user.day_master}")
        st.markdown(f"**生肖**: {user.shengxiao or '未知'} | **星座**: {user.zodiac or '未知'}")
        if user.xi_shen:
            st.markdown(f"**喜用神**: {user.xi_shen}")
        if user.ji_shen:
            st.markdown(f"**忌神**: {user.ji_shen}")


def _find_hour_index(birth_time: str, all_hours: list[str]) -> int:
    """找到当前出生时辰在选项列表中的索引"""
    for i, h in enumerate(all_hours):
        if h.startswith(birth_time.split(":")[0]):
            return i
    return 6  # 默认午时


if __name__ == "__main__":
    user_profile_page()
