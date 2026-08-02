"""
顶部栏用户组件。
在 Streamlit 页面顶部栏下方右侧渲染用户浮动卡片：
- 默认收起：天气图标 + 用户名 + 运势分数 + 齿轮图标
- 点击主体 → 展开/收起详情面板
- 点击齿轮 → 跳转用户管理
"""
from __future__ import annotations

import streamlit as st

from src.metaphysics.fortune import get_personal_fortune
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_bazi, get_current_user

logger = get_logger(__name__)

# ── CSS：固定定位 + 展开面板 ──
_CARD_CSS = """
<style>
/* === 主按钮容器（固定到顶部栏下方右侧）=== */
.st-key-user-main {
    position: fixed !important;
    top: 64px !important;
    right: 52px !important;
    z-index: 99990 !important;
    width: auto !important;
}
.st-key-user-main button {
    font-size: 13px !important;
    padding: 5px 12px !important;
    border-radius: 16px 0 0 16px !important;
    border-right: none !important;
    white-space: nowrap !important;
    cursor: pointer !important;
    box-shadow: -2px 1px 6px rgba(0,0,0,0.04), 0 1px 6px rgba(0,0,0,0.04) !important;
    transition: box-shadow 0.15s !important;
}
.st-key-user-main button:hover {
    box-shadow: -2px 2px 12px rgba(0,0,0,0.08), 0 2px 12px rgba(0,0,0,0.08) !important;
}

/* === 齿轮容器 === */
.st-key-user-gear {
    position: fixed !important;
    top: 64px !important;
    right: 14px !important;
    z-index: 99990 !important;
    width: auto !important;
}
.st-key-user-gear a {
    border-radius: 0 16px 16px 0 !important;
    font-size: 14px !important;
    padding: 5px 10px !important;
    box-shadow: 2px 1px 6px rgba(0,0,0,0.04), 0 1px 6px rgba(0,0,0,0.04) !important;
    text-decoration: none !important;
    border-left: 1px solid rgba(0,0,0,0.06) !important;
    transition: box-shadow 0.15s, transform 0.3s !important;
    display: inline-flex !important;
    align-items: center !important;
}
.st-key-user-gear a:hover {
    box-shadow: 2px 2px 12px rgba(0,0,0,0.08), 0 2px 12px rgba(0,0,0,0.08) !important;
    transform: rotate(60deg) !important;
}

/* === 展开详情面板（固定定位浮层）=== */
.st-key-user-panel {
    position: fixed !important;
    top: 96px !important;
    right: 14px !important;
    z-index: 99991 !important;
    width: 300px !important;
    max-height: 70vh !important;
    overflow-y: auto !important;
    background: var(--background-color, #fff) !important;
    border: 1px solid rgba(0,0,0,0.08) !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10) !important;
    padding: 14px 16px !important;
}

/* === 深色模式 === */
@media (prefers-color-scheme: dark) {
    .st-key-user-main button {
        box-shadow: -2px 1px 6px rgba(255,255,255,0.02), 0 1px 6px rgba(255,255,255,0.02) !important;
    }
    .st-key-user-main button:hover {
        box-shadow: -2px 2px 12px rgba(255,255,255,0.06), 0 2px 12px rgba(255,255,255,0.06) !important;
    }
    .st-key-user-panel {
        background: #1e1e1e !important;
        border-color: rgba(255,255,255,0.08) !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.30) !important;
    }
    .st-key-user-gear a {
        box-shadow: 2px 1px 6px rgba(255,255,255,0.02), 0 1px 6px rgba(255,255,255,0.02) !important;
        border-left-color: rgba(255,255,255,0.08) !important;
    }
}
</style>
"""


def _fortune_weather(score: int) -> tuple[str, str]:
    """根据分数返回 (天气图标, 天气简述)"""
    if score >= 80:
        return "☀️", "大吉"
    elif score >= 65:
        return "🌤️", "吉"
    elif score >= 50:
        return "⛅", "平"
    elif score >= 35:
        return "🌧️", "小凶"
    else:
        return "⛈️", "凶"


def render_user_header():
    """
    在页面顶部栏下方右侧渲染用户浮动卡片。
    点击主体按钮展开/收起详情面板。

    返回 bool：True 表示用户已登录，False 表示无用户。
    """
    st.markdown(_CARD_CSS, unsafe_allow_html=True)

    # 初始化展开状态
    if "user_card_open" not in st.session_state:
        st.session_state["user_card_open"] = False

    user = get_current_user()

    # ═══════════════════════════════════════════
    #  未登录
    # ═══════════════════════════════════════════
    if user is None:
        with st.container(key="user-main"):
            if st.button("👤 未登录", key="user-btn-guest", use_container_width=False):
                st.switch_page("src/pages/home.py")
        with st.container(key="user-gear"):
            st.page_link("src/pages/user_profile.py", label="⚙", help="用户管理")
        return False

    # ═══════════════════════════════════════════
    #  已登录
    # ═══════════════════════════════════════════
    bazi = get_current_bazi()

    # 今日运势
    try:
        fortune = get_personal_fortune(bazi)
        score = fortune.overall_score
        weather_icon, weather_text = _fortune_weather(score)
    except Exception:
        logger.warning("获取今日运势失败: user=%s", user.name, exc_info=True)
        score = 0
        weather_icon = "❓"
        weather_text = "未知"

    day_master = user.day_master or "?"

    # 紧凑 label
    card_label = f"{weather_icon} {user.name} · {score}分 {weather_text}"

    # ── 主按钮：点击切换展开/收起 ──
    with st.container(key="user-main"):
        if st.button(card_label, key="user-btn", use_container_width=False):
            st.session_state["user_card_open"] = not st.session_state["user_card_open"]

    # ── 齿轮 ──
    with st.container(key="user-gear"):
        st.page_link("src/pages/user_profile.py", label="⚙", help="用户管理")

    # ── 展开详情面板 ──
    if st.session_state["user_card_open"]:
        with st.container(key="user-panel"):
            _render_panel_content(user, bazi, score, weather_text)

    return True


def _render_panel_content(user, bazi, score: int, weather_text: str):
    """渲染展开详情面板内容"""
    st.markdown("##### 今日运势")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.metric("运势指数", f"{score}分", delta=weather_text, delta_color="off")
    with col_b:
        st.markdown(f"**日主**: {user.day_master or '?'}")
        st.markdown(f"**生肖**: {user.shengxiao or '?'}")

    if bazi:
        st.divider()
        st.markdown("##### 八字命盘")
        pillar_text = (
            f"{bazi.year_gan}{bazi.year_zhi} "
            f"{bazi.month_gan}{bazi.month_zhi} "
            f"{bazi.day_gan}{bazi.day_zhi} "
            f"{bazi.hour_gan}{bazi.hour_zhi}"
        )
        st.markdown(f"**四柱**: {pillar_text}")
        st.markdown(
            f"**喜神**: {', '.join(bazi.xi_shen) if bazi.xi_shen else '无'}"
        )
        st.markdown(
            f"**忌神**: {', '.join(bazi.ji_shen) if bazi.ji_shen else '无'}"
        )

    st.divider()
    st.page_link("src/pages/user_profile.py", label="⚙️ 完整用户管理", icon="⚙️")
    st.page_link("src/pages/lucky.py", label="🍀 查看幸运运势", icon="🍀")
    st.page_link("src/pages/home.py", label="🔮 八字排盘", icon="🔮")
