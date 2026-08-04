"""
A-ALTAS 主入口
玄学量化 A 股分析工具
"""

import streamlit as st

# 设置页面配置（必须在任何 streamlit 调用之前）
st.set_page_config(
    page_title="A-ALTAS 玄学量化",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 页面定义（第一个分组的第一页为默认首页）
pages = {
    "自选": [
        st.Page("src/pages/watchlist.py", title="自选股", icon="⭐"),
    ],
    "行情": [
        st.Page("src/pages/market.py", title="行情扫描", icon="🔎"),
    ],
    "玄学量化": [
        st.Page("src/pages/home.py", title="八字排盘", icon="🔮"),
        st.Page("src/pages/lucky.py", title="幸运运势", icon="🍀"),
        st.Page("src/pages/constellation.py", title="星座算命", icon="♈"),
        st.Page("src/pages/stock_picker.py", title="财神选股", icon="📊"),
        st.Page("src/pages/daily_signal.py", title="每日信号", icon="📅"),
    ],
    "K线工具": [
        st.Page("src/pages/kline_viewer.py", title="K线看盘", icon="📈"),
    ],
    "系统": [
        st.Page("src/pages/user_profile.py", title="用户管理", icon="👤"),
    ],
}

# 初始化导航
pg = st.navigation(pages)
pg.run()
