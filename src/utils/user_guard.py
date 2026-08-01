"""
用户信息守卫模块。
统一的用户档案检查逻辑：当页面需要用户八字数据但用户尚未输入时，
展示醒目提示引导用户前往首页输入生辰信息。
"""

from typing import Optional

import streamlit as st

from src.data.db import UserProfile, db
from src.metaphysics.bazi import BaziResult, calc_bazi
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_current_user() -> Optional[UserProfile]:
    """
    获取当前用户档案。

    优先从 session_state 读取，其次从数据库加载最新一条。
    若都不存在返回 None。

    Returns:
        UserProfile 或 None
    """
    # session_state 中已有
    if "user_id" in st.session_state:
        try:
            return UserProfile.get_by_id(st.session_state["user_id"])
        except Exception:
            logger.warning("session_state 中的 user_id=%s 无效，清除", st.session_state["user_id"])
            del st.session_state["user_id"]

    # 从数据库加载最新一条
    user = UserProfile.select().order_by(UserProfile.id.desc()).first()
    if user:
        st.session_state["user_id"] = user.id
        logger.info("自动加载数据库用户: %s (id=%s)", user.name, user.id)
        return user

    return None


def get_current_bazi() -> Optional[BaziResult]:
    """
    获取当前用户的 BaziResult。

    优先从 session_state 读取缓存，否则从 UserProfile 重建。
    若用户不存在返回 None。

    Returns:
        BaziResult 或 None
    """
    # session_state 中已有
    if "user_bazi" in st.session_state and st.session_state["user_bazi"] is not None:
        return st.session_state["user_bazi"]

    user = get_current_user()
    if user is None:
        return None

    try:
        bazi = calc_bazi(user.birth_date, user.birth_time, user.is_solar)
        st.session_state["user_bazi"] = bazi
        return bazi
    except Exception:
        logger.error("从 UserProfile 重建八字失败: user=%s", user.name, exc_info=True)
        return None


def require_user_profile(page_name: str = "本页面") -> Optional[UserProfile]:
    """
    页面级别守卫：检查用户是否已输入八字信息。

    若用户不存在，在页面上展示醒目提示并返回 None。
    页面函数应在调用后检查返回值，若为 None 则提前 return。

    用法:
        user = require_user_profile("幸运运势")
        if user is None:
            return

    Args:
        page_name: 当前页面名称，用于提示文案

    Returns:
        UserProfile 或 None
    """
    user = get_current_user()

    if user is None:
        logger.info("页面 %s 需要用户信息但未找到，展示提示", page_name)
        st.warning(
            f"⚠️ **{page_name}** 需要你的生辰八字信息\n\n"
            f"请先前往 **🔮 八字排盘** 页面输入你的出生日期和时辰，"
            f"完成排盘后即可使用{page_name}功能。"
        )
        st.info(
            "需要的信息：\n"
            "- 出生日期（公历或农历）\n"
            "- 出生时辰（子时至亥时）\n"
            "- 性别\n\n"
            "这些信息将用于计算你的幸运数字、幸运颜色、幸运方位、幸运日等玄学指标。"
        )
        return None

    return user


def require_user_bazi(page_name: str = "本页面") -> Optional[BaziResult]:
    """
    页面级别守卫：检查用户八字是否可用。

    与 require_user_profile 类似，但返回 BaziResult。
    适用于需要直接使用八字四柱数据的页面。

    Args:
        page_name: 当前页面名称

    Returns:
        BaziResult 或 None
    """
    user = require_user_profile(page_name)
    if user is None:
        return None

    bazi = get_current_bazi()
    if bazi is None:
        st.error("用户八字数据异常，请重新排盘")
        return None

    return bazi
