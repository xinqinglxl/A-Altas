"""
顶部栏用户组件。
纯 HTML + JS 实现，点击展开/收起无需刷新页面：
- 默认收起：天气图标 + 用户名 + 运势分数 + 齿轮图标
- 点击主体 → 展开详情面板（纯前端 toggle，不触发 rerun）
- 再次点击主体 → 收起面板
- 点击齿轮 → 跳转用户管理
"""
from __future__ import annotations

import streamlit as st

from src.metaphysics.fortune import get_personal_fortune
from src.utils.logger import get_logger
from src.utils.user_guard import get_current_bazi, get_current_user

logger = get_logger(__name__)


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
    """纯前端卡片：HTML + CSS + JS，toggle 不触发 rerun。"""
    user = get_current_user()

    # ═══════════════════════════════════════════
    #  未登录
    # ═══════════════════════════════════════════
    if user is None:
        _render_guest_card()
        return False

    # ═══════════════════════════════════════════
    #  已登录
    # ═══════════════════════════════════════════
    bazi = get_current_bazi()

    try:
        fortune = get_personal_fortune(bazi)
        score = fortune.overall_score
        weather_icon, weather_text = _fortune_weather(score)
    except Exception:
        logger.warning("获取今日运势失败: user=%s", user.name, exc_info=True)
        score = 0
        weather_icon = "❓"
        weather_text = "未知"

    _render_user_card(user, bazi, score, weather_icon, weather_text)
    return True


def _render_guest_card():
    """未登录卡片"""
    st.html(f"""
<style>
.user-card-btn {{
    position: fixed !important;
    top: 64px !important;
    right: 52px !important;
    z-index: 99990 !important;
    font-size: 13px;
    padding: 5px 12px;
    border-radius: 16px 0 0 16px;
    border: 1px solid rgba(0,0,0,0.12);
    border-right: none;
    background: var(--background-color, #fff);
    color: inherit;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: -2px 1px 6px rgba(0,0,0,0.04), 0 1px 6px rgba(0,0,0,0.04);
    font-family: inherit;
}}
.user-card-gear {{
    position: fixed !important;
    top: 64px !important;
    right: 14px !important;
    z-index: 99990 !important;
    font-size: 14px;
    padding: 5px 10px;
    border-radius: 0 16px 16px 0;
    border: 1px solid rgba(0,0,0,0.12);
    border-left: 1px solid rgba(0,0,0,0.06);
    background: var(--background-color, #fff);
    color: inherit;
    text-decoration: none;
    cursor: pointer;
    box-shadow: 2px 1px 6px rgba(0,0,0,0.04), 0 1px 6px rgba(0,0,0,0.04);
    display: inline-flex;
    align-items: center;
    font-family: inherit;
    transition: transform 0.3s;
}}
.user-card-gear:hover {{ transform: rotate(60deg); }}
@media (prefers-color-scheme: dark) {{
    .user-card-btn, .user-card-gear {{
        background: #1e1e1e;
        border-color: rgba(255,255,255,0.1);
    }}
    .user-card-gear {{ border-left-color: rgba(255,255,255,0.08); }}
}}
</style>
<button class="user-card-btn" onclick="window.location.href='/home';">👤 未登录</button>
<a class="user-card-gear" href="/user_profile" title="用户管理">⚙</a>
""")
    return False


def _render_user_card(user, bazi, score: int, weather_icon: str, weather_text: str):
    """已登录卡片：纯 HTML + JS toggle"""

    day_master = user.day_master or "?"
    shengxiao = user.shengxiao or "?"

    # 八字四柱
    bazi_html = ""
    if bazi:
        pillar = (
            f"{bazi.year_gan}{bazi.year_zhi} "
            f"{bazi.month_gan}{bazi.month_zhi} "
            f"{bazi.day_gan}{bazi.day_zhi} "
            f"{bazi.hour_gan}{bazi.hour_zhi}"
        )
        xi = ", ".join(bazi.xi_shen) if bazi.xi_shen else "无"
        ji = ", ".join(bazi.ji_shen) if bazi.ji_shen else "无"
        bazi_html = f"""
        <div style="border-top:1px solid rgba(0,0,0,0.06);margin-top:10px;padding-top:10px;">
            <div style="font-weight:600;margin-bottom:6px;">八字命盘</div>
            <div><b>四柱</b>: {pillar}</div>
            <div><b>喜神</b>: {xi}</div>
            <div><b>忌神</b>: {ji}</div>
        </div>
        """

    label = f"{weather_icon} {user.name} · {score}分 {weather_text}"

    st.html(f"""
<style>
#user-card-btn {{
    position: fixed !important;
    top: 64px !important;
    right: 52px !important;
    z-index: 99990 !important;
    font-size: 13px;
    padding: 5px 12px;
    border-radius: 16px 0 0 16px;
    border: 1px solid rgba(0,0,0,0.12);
    border-right: none;
    background: var(--background-color, #fff);
    color: inherit;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: -2px 1px 6px rgba(0,0,0,0.04), 0 1px 6px rgba(0,0,0,0.04);
    font-family: inherit;
    transition: box-shadow 0.15s;
}}
#user-card-btn:hover {{ box-shadow: -2px 2px 12px rgba(0,0,0,0.08); }}
#user-card-gear {{
    position: fixed !important;
    top: 64px !important;
    right: 14px !important;
    z-index: 99990 !important;
    font-size: 14px;
    padding: 5px 10px;
    border-radius: 0 16px 16px 0;
    border: 1px solid rgba(0,0,0,0.12);
    border-left: 1px solid rgba(0,0,0,0.06);
    background: var(--background-color, #fff);
    color: inherit;
    text-decoration: none;
    cursor: pointer;
    box-shadow: 2px 1px 6px rgba(0,0,0,0.04);
    display: inline-flex;
    align-items: center;
    font-family: inherit;
    transition: transform 0.3s, box-shadow 0.15s;
}}
#user-card-gear:hover {{ transform: rotate(60deg); box-shadow: 2px 2px 12px rgba(0,0,0,0.08); }}
#user-card-panel {{
    display: none;
    position: fixed !important;
    top: 96px !important;
    right: 14px !important;
    z-index: 99991 !important;
    width: 280px;
    max-height: 70vh;
    overflow-y: auto;
    background: var(--background-color, #fff);
    color: inherit;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10);
    padding: 14px 16px;
    font-family: inherit;
    font-size: 14px;
}}
@media (prefers-color-scheme: dark) {{
    #user-card-btn, #user-card-gear, #user-card-panel {{
        background: #1e1e1e;
        border-color: rgba(255,255,255,0.1);
        color: #cdd6f4;
    }}
    #user-card-gear {{ border-left-color: rgba(255,255,255,0.08); }}
    #user-card-panel {{ box-shadow: 0 4px 24px rgba(0,0,0,0.30); }}
    #user-card-panel div[style*="border-top"] {{ border-top-color: rgba(255,255,255,0.08) !important; }}
}}
</style>
<button id="user-card-btn" onclick="var p=document.getElementById('user-card-panel');p.style.display=p.style.display==='none'?'block':'none';">{label}</button>
<a id="user-card-gear" href="/user_profile" title="用户管理">⚙</a>
<div id="user-card-panel">
    <div style="font-weight:600;font-size:16px;margin-bottom:8px;">今日运势</div>
    <div style="display:flex;gap:16px;align-items:center;margin-bottom:6px;">
        <div>
            <div style="font-size:24px;font-weight:700;">{score}分</div>
            <div style="color:#888;font-size:12px;">{weather_text}</div>
        </div>
        <div>
            <div style="line-height:1.8;"><b>日主</b>: {day_master}</div>
            <div style="line-height:1.8;"><b>生肖</b>: {shengxiao}</div>
        </div>
    </div>
    {bazi_html}
    <div style="border-top:1px solid rgba(0,0,0,0.06);margin-top:10px;padding-top:10px;display:flex;flex-direction:column;gap:6px;">
        <a href="/user_profile" style="color:inherit;text-decoration:none;font-size:13px;">⚙️ 完整用户管理</a>
        <a href="/lucky" style="color:inherit;text-decoration:none;font-size:13px;">🍀 查看幸运运势</a>
        <a href="/home" style="color:inherit;text-decoration:none;font-size:13px;">🔮 八字排盘</a>
    </div>
</div>
""")
