"""
K线看盘 - 原始K线 + 美元计价 + 运势叠加
"""

import json

import pandas as pd
import streamlit as st
from datetime import date

from src.data.db import db, ExchangeRate, StockBasic, Watchlist
from src.data.kline_real import get_kline
from src.data.exchange import get_usd_cny_latest
from src.utils.logger import get_logger
from src.utils.trading_calendar import get_non_trading_reason, get_recent_trading_day, is_trading_day
from src.utils.user_guard import get_current_user
from src.components.user_header import render_user_header
from src.metaphysics.stock_recommend import evaluate_stock

logger = get_logger(__name__)


def convert_kline_to_usd(df: pd.DataFrame) -> pd.DataFrame:
    """将K线的 OHLC 从 CNY 转为 USD"""
    df = df.copy()
    rates = {}

    # 从数据库获取汇率
    exchange_rates = ExchangeRate.select()
    for er in exchange_rates:
        rates[str(er.date)] = er.usd_cny

    # 转换
    for col in ["open", "high", "low", "close"]:
        df[col + "_usd"] = df.apply(
            lambda row: round(row[col] / rates.get(str(row["time"]), 7.2), 4)
            if rates.get(str(row["time"]), 0) > 0
            else row[col],
            axis=1,
        )

    return df


def render_kline_html(
    df: pd.DataFrame,
    use_usd: bool = False,
    height: int = 700,
) -> str:
    """渲染 K 线图 HTML（支持 USD 计价）"""

    price_col = "close" if not use_usd else "close_usd"
    open_col = "open" if not use_usd else "open_usd"
    high_col = "high" if not use_usd else "high_usd"
    low_col = "low" if not use_usd else "low_usd"

    candles = []
    volumes = []
    for _, row in df.iterrows():
        t = str(row["time"])
        o = float(row[open_col])
        h = float(row[high_col])
        l = float(row[low_col])
        c = float(row[price_col])
        v = float(row["volume"])

        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        color = "rgba(38,166,91,0.5)" if c >= o else "rgba(239,83,80,0.5)"
        volumes.append({"time": t, "value": v, "color": color})

    candles_json = json.dumps(candles)
    volumes_json = json.dumps(volumes)

    currency_label = "USD" if use_usd else "CNY"

    html = f"""<!DOCTYPE html>
<html style="height: 100%; width: 100%;">
<head>
<meta charset="utf-8">
<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
<style>
  body {{ margin: 0; padding: 0; background: #1e1e2e; height: 100%; width: 100%; }}
  #chart {{ width: 100%; height: 100%; }}
</style>
</head>
<body>
<div id="chart"></div>
<script>
try {{
const chartContainer = document.getElementById('chart');
const width = chartContainer.clientWidth || window.innerWidth;
const height = chartContainer.clientHeight || window.innerHeight || {height};

const chart = LightweightCharts.createChart(chartContainer, {{
  width: width,
  height: height,
  layout: {{
    background: {{ type: 'solid', color: '#1e1e2e' }},
    textColor: '#cdd6f4',
  }},
  grid: {{
    vertLines: {{ color: '#313244' }},
    horzLines: {{ color: '#313244' }},
  }},
  crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
  rightPriceScale: {{ borderColor: '#313244' }},
  timeScale: {{ borderColor: '#313244', timeVisible: false }},
}});

const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {{
  upColor: '#26a65b',
  downColor: '#ef5350',
  borderDownColor: '#ef5350',
  borderUpColor: '#26a65b',
  wickDownColor: '#ef5350',
  wickUpColor: '#26a65b',
  priceFormat: {{ type: 'price', minMove: 0.01, precision: 2 }},
}});
candleSeries.setData({candles_json});

const volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {{
  color: '#26a65b',
  priceFormat: {{ type: 'volume' }},
  priceScaleId: 'volume',
}});
volumeSeries.setData({volumes_json});

chart.priceScale('volume').applyOptions({{
  scaleMargins: {{ top: 0.8, bottom: 0 }},
}});

chart.timeScale().fitContent();

const currencyLabel = document.createElement('div');
currencyLabel.style.cssText = 'position:absolute;top:10px;left:12px;color:#cdd6f4;font-size:13px;pointer-events:none;';
currencyLabel.textContent = '(计价单位: {currency_label})';
chartContainer.appendChild(currencyLabel);

window.addEventListener('resize', () => {{
  chart.applyOptions({{ width: chartContainer.clientWidth || window.innerWidth }});
}});
}} catch(e) {{
  document.body.innerHTML = '<h2 style="color:red">JS Error: ' + e.message + '</h2>';
}}
</script>
</body>
</html>"""
    return html


def _compute_kline_signals(df: pd.DataFrame) -> tuple[list[str], float | None, int | None]:
    """从K线数据中提取技术信号，用于推荐评估。
    返回 (matched_conditions, change_pct, volume)"""
    close_col = "close" if "close" in df.columns else "close_usd"
    open_col = "open" if "open" in df.columns else "open_usd"
    high_col = "high" if "high" in df.columns else "high_usd"

    close = df[close_col].values
    open_vals = df[open_col].values
    high_vals = df[high_col].values
    vol_vals = df["volume"].values

    signals: list[str] = []
    change_pct: float | None = None
    volume: int | None = None

    if len(close) < 5:
        return signals, change_pct, volume

    # 涨跌幅（最新 vs 前一交易日）
    change_pct = round((float(close[-1]) - float(close[-2])) / float(close[-2]) * 100, 2)

    # 最新成交量
    volume = int(vol_vals[-1])

    # 连阳：最近3根K线收盘>开盘
    yang_count = sum(1 for i in range(-min(3, len(close)), 0) if float(close[i]) > float(open_vals[i]))
    if yang_count >= 3:
        signals.append(f"{yang_count}连阳")

    # 均线
    if len(close) >= 30:
        ser_close = pd.Series(close, dtype=float)
        ma5 = float(ser_close.rolling(5).mean().iloc[-1])
        ma10 = float(ser_close.rolling(10).mean().iloc[-1])
        ma30 = float(ser_close.rolling(30).mean().iloc[-1])
        if close[-1] > ma5 > ma10 > ma30:
            signals.append("均线多头排列")

        # 金叉 MA5 上穿 MA15
        if len(close) >= 16:
            ma5_prev = float(ser_close.rolling(5).mean().iloc[-2])
            ma15_prev = float(ser_close.rolling(15).mean().iloc[-2])
            ma5_curr = ma5
            ma15_curr = float(ser_close.rolling(15).mean().iloc[-1])
            if ma5_prev <= ma15_prev and ma5_curr > ma15_curr:
                signals.append("均线金叉")

    # 放量：最新量 > 20日均量 × 1.5
    if len(vol_vals) >= 20:
        ser_vol = pd.Series(vol_vals, dtype=float)
        avg_vol = float(ser_vol.rolling(20).mean().iloc[-2])
        if float(vol_vals[-1]) > 1.5 * avg_vol:
            signals.append("放量上涨")

    # 新高：最新最高价是近30日最高
    if len(high_vals) >= 30:
        if float(high_vals[-1]) >= max(float(h) for h in high_vals[-30:-1]):
            signals.append("创30日新高")

    return signals, change_pct, volume


def kline_viewer_page():
    st.title("K线看盘")
    st.caption("原始K线 · 美元计价 · 运势标注")

    db.connect(reuse_if_open=True)

    # 顶部用户 header
    render_user_header()

    # ── 初始化持久化状态 ──
    if "kline_loaded" not in st.session_state:
        st.session_state["kline_loaded"] = None  # {symbol, df, label, use_usd, show_fortune, period}

    # ── 读取从其他页面传入的股票代码 ──
    auto_stock = st.session_state.pop("kline_stock", None)
    if auto_stock:
        auto_load = True
        default_symbol = auto_stock
    else:
        auto_load = False
        loaded = st.session_state.get("kline_loaded")
        default_symbol = loaded["symbol"] if loaded else "000001"

    # 顶部交易日状态提示
    today = date.today()
    today_reason = get_non_trading_reason(today)
    if today_reason:
        last_td = get_recent_trading_day(today)
        st.warning(
            f"⚠️ 今天 {today.strftime('%Y-%m-%d')} {today_reason}，"
            f"最近交易日为 **{last_td.strftime('%Y-%m-%d')}**"
        )
    else:
        st.success(f"✅ 今天 {today.strftime('%Y-%m-%d')} 为交易日，正常开市")

    # ═══════════════════════════════════════════
    #  主区域 — 图表配置表单
    # ═══════════════════════════════════════════
    with st.form("kline_config"):
        col_sym, col_period, col_days, col_btn = st.columns([3, 1, 1, 2])
        with col_sym:
            symbol = st.text_input("股票代码", value=default_symbol, key="kline-symbol",
                                   placeholder="输入代码，如 000001")
        with col_period:
            period = st.number_input("重铸周期(日)", min_value=1, max_value=30, value=1, key="kline-period")
        with col_days:
            days = st.number_input("数据天数", min_value=30, max_value=730, value=180, key="kline-days")
        with col_btn:
            search = st.form_submit_button("🔍 加载K线", type="primary", use_container_width=True)

        col_opts1, col_opts2, _ = st.columns([1, 1, 2])
        with col_opts1:
            use_usd = st.checkbox("美元计价 (USD)", value=False, key="kline-usd")
        with col_opts2:
            show_fortune = st.checkbox("显示运势日", value=True, key="kline-fortune")

    if show_fortune:
        user_f = get_current_user()
        if user_f is None:
            st.caption("⚠️ 运势预测需要八字信息，请先在【八字排盘】页面输入生辰")

    # 汇率
    rate = get_usd_cny_latest()
    if rate:
        st.caption(f"当前汇率: 1 USD = {rate:.4f} CNY")

    # ═══════════════════════════════════════════
    #  判断是否加载新数据
    # ═══════════════════════════════════════════
    should_load = search or auto_load

    if should_load:
        with st.spinner(f"正在获取 {symbol} K线数据..."):
            try:
                logger.info("K线加载: symbol=%s, period=%d, days=%d, usd=%s", symbol, period, days, use_usd)

                from datetime import date as dt_date, timedelta

                end_d = dt_date.today()
                start_d = end_d - timedelta(days=days)
                start_str = start_d.strftime("%Y%m%d")
                end_str = end_d.strftime("%Y%m%d")

                df, data_label = get_kline(
                    symbol=symbol,
                    start_date=start_str,
                    end_date=end_str,
                    days=days,
                )

                if df.empty:
                    logger.warning("K线获取失败: symbol=%s", symbol)
                    st.error(f"无法获取 {symbol} 的K线数据")
                    db.close()
                    return

                from src.kline_builder import resample_kline

                df = resample_kline(df, period) if period > 1 else df

                logger.info("K线加载成功: %s, %d 条, period=%d, 来源=%s", symbol, len(df), period, data_label)

                # 美元转换
                if use_usd:
                    df = convert_kline_to_usd(df)

                # 持久化到 session_state
                st.session_state["kline_loaded"] = {
                    "symbol": symbol,
                    "df": df,
                    "label": data_label,
                    "use_usd": use_usd,
                    "show_fortune": show_fortune,
                    "period": period,
                }

            except Exception as e:
                logger.error("K线加载失败: symbol=%s, error=%s", symbol, e, exc_info=True)
                st.error(f"加载失败: {e}")
                db.close()
                return

    # ═══════════════════════════════════════════
    #  渲染已加载的 K 线（从 session_state 恢复）
    # ═══════════════════════════════════════════
    loaded = st.session_state.get("kline_loaded")

    if loaded is None:
        st.info("输入股票代码，点击【加载K线】开始")
        db.close()
        return

    # 恢复数据
    df = loaded["df"]
    data_label = loaded["label"]
    loaded_symbol = loaded["symbol"]
    loaded_use_usd = loaded["use_usd"]
    loaded_show_fortune = loaded["show_fortune"]
    loaded_period = loaded["period"]

    # 从K线数据实时计算技术信号
    kline_signals, kline_pct, kline_vol = _compute_kline_signals(df)

    st.info(f"📡 {data_label} · {loaded_symbol} · 共 {len(df)} 根K线 (周期: {loaded_period}日)")

    if loaded_use_usd:
        st.info("已转换为美元计价 (基于真实历史汇率)")

    # ═══════════════════════════════════════════
    #  自选股 加入/移除 按钮（fragment 隔离，只改 DB，不重渲染整页）
    # ═══════════════════════════════════════════
    @st.fragment()
    def _watchlist_toggle():
        user = get_current_user()
        if not user:
            return
        try:
            stock_obj = StockBasic.get_or_none(StockBasic.code == loaded_symbol)
            if not stock_obj:
                return

            # 直接读 DB 判断自选状态（不用 session_state）
            watched = Watchlist.get_or_none(
                Watchlist.user == user,
                Watchlist.stock == stock_obj,
            )

            col_wl_btn, col_wl_info = st.columns([1, 5])
            with col_wl_btn:
                if watched is not None:
                    if st.button("⭐ 移除自选", key=f"kline-wl-remove", type="secondary",
                                 help=f"将 {loaded_symbol} 从自选移除", use_container_width=True):
                        watched.delete_instance()
                        # fragment 自动重渲染：下次 watched=None → 显示「加入自选」
                else:
                    if st.button("☆ 加入自选", key=f"kline-wl-add", type="primary",
                                 help=f"将 {loaded_symbol} 加入自选", use_container_width=True):
                        Watchlist.create(user=user, stock=stock_obj)
                        # fragment 自动重渲染：下次 watched 不为 None → 显示「移除自选」
            with col_wl_info:
                st.caption(f"{loaded_symbol} {stock_obj.name} | {stock_obj.sector or '-'} | 五行: {stock_obj.wuxing or '-'}")
        except Exception:
            pass

    _watchlist_toggle()

    # ═══════════════════════════════════════════
    #  买入推荐评估（综合技术面+玄学面，直接展示详情）
    # ═══════════════════════════════════════════
    stock_obj_rec = StockBasic.get_or_none(StockBasic.code == loaded_symbol)
    stock_name = stock_obj_rec.name if stock_obj_rec else loaded_symbol
    stock_wx = stock_obj_rec.wuxing if stock_obj_rec else None
    stock_sector = stock_obj_rec.sector if stock_obj_rec else None

    user_rec = get_current_user()
    user_bazi = None
    if user_rec and user_rec.birth_date and user_rec.birth_time:
        try:
            from src.metaphysics.bazi import calc_bazi
            user_bazi = calc_bazi(user_rec.birth_date, user_rec.birth_time)
        except Exception:
            pass

    rec = evaluate_stock(
        stock_code=loaded_symbol,
        stock_name=stock_name,
        stock_wuxing=stock_wx,
        stock_sector=stock_sector,
        matched_conditions=kline_signals,
        change_pct=kline_pct,
        volume=kline_vol,
        user_bazi=user_bazi,
    )

    st.divider()
    st.subheader(f"{rec.emoji}  {rec.level}  ·  综合评分 {rec.total_score}/100  ({loaded_symbol} {stock_name})")

    # 分维度展示
    col_tech, col_meta = st.columns(2)
    with col_tech:
        st.caption(f"**技术面** {rec.tech_score}/40 分")
        if rec.tech_reasons:
            for r in rec.tech_reasons:
                st.caption(f"• {r}")
        else:
            st.caption("• 暂无显著技术信号")
    with col_meta:
        st.caption(f"**玄学面** {rec.meta_score}/60 分")
        if rec.meta_reasons:
            for r in rec.meta_reasons:
                st.caption(f"• {r}")
        else:
            st.caption("• 请先设置八字信息以获取玄学评估")

    # ═══════════════════════════════════════════
    #  未来一周运势预测（默认显示）
    # ═══════════════════════════════════════════
    if loaded_show_fortune:
        user_f = get_current_user()
        if user_f is None:
            st.caption("⚠️ 运势预测需要八字信息，请先在【八字排盘】页面输入生辰")
        else:
            if user_f.birth_date and user_f.birth_time:
                stock_obj = StockBasic.get_or_none(StockBasic.code == loaded_symbol)
                stock_wx = stock_obj.wuxing if stock_obj else ""
                weekly = _get_weekly_fortune_for_stock(
                    str(user_f.birth_date), user_f.birth_time, stock_wx
                )

                st.divider()
                st.subheader(f"🔮 未来一周买入 {loaded_symbol} 运势预测")
                st.caption(f"用户: {user_f.name} (日主: {user_f.day_master}) | 股票五行: {stock_wx or '未知'}")

                # 表格展示
                row_data = []
                for w in weekly:
                    combined = w["combined"]
                    if combined >= 75:
                        icon = "🟢"
                    elif combined >= 55:
                        icon = "🟡"
                    elif combined >= 40:
                        icon = "🟠"
                    else:
                        icon = "🔴"

                    if not w["is_trading"]:
                        icon = "⚫"

                    action = ""
                    if w["is_trading"]:
                        if combined >= 75:
                            action = "✅ 强烈推荐"
                        elif combined >= 55:
                            action = "👍 可考虑"
                        elif combined >= 40:
                            action = "⚠️ 谨慎"
                        else:
                            action = "❌ 不建议"
                    else:
                        action = f"休市({w['nt_reason']})"

                    reasons_str = " · ".join(w["reasons"][:3]) if w["reasons"] else "—"

                    row_data.append({
                        "日期": w["date"],
                        "星期": w["weekday"],
                        "日柱": f"{w['gan']}{w['zhi']}",
                        "五行": w["wuxing"],
                        "综合评分": f"{icon} {combined}分",
                        "建议": action,
                        "关键因素": reasons_str,
                        "_score": combined,
                    })

                df_fortune = pd.DataFrame(row_data)
                st.dataframe(
                    df_fortune,
                    column_order=["日期", "星期", "日柱", "五行", "综合评分", "建议", "关键因素"],
                    hide_index=True,
                    use_container_width=True,
                    height=38 * (len(row_data) + 1),
                )

                # 在K线数据上标注推荐日（可选展示）
                rec_dates = {w["date"] for w in weekly if w["is_trading"] and w["combined"] >= 55}
                if rec_dates:
                    st.caption(f"📌 K线图上标注了 {len(rec_dates)} 个「推荐关注」日期（评分≥55的交易日）")
            else:
                st.caption("⚠️ 八字信息不完整，无法生成运势预测")

    # ═══════════════════════════════════════════
    #  K 线图表
    # ═══════════════════════════════════════════
    html = render_kline_html(df, use_usd=loaded_use_usd, height=750)
    st.iframe(html, height=800)

    # 数据预览
    with st.expander("数据预览"):
        show_cols = (
            ["time", "open_usd", "high_usd", "low_usd", "close_usd", "volume"]
            if loaded_use_usd
            else ["time", "open", "high", "low", "close", "volume"]
        )
        avail_cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[avail_cols].tail(20), use_container_width=True)
        st.caption(f"数据来源: {data_label}")

    db.close()


@st.cache_data(ttl=3600, show_spinner=False)
def _get_weekly_fortune_for_stock(birth_date_str: str, birth_time_str: str, stock_wuxing: str) -> list[dict]:
    """评估未来7天该股票是否适合买入。

    综合两个维度：
    - 用户个人当日运势（八字 vs 日柱）
    - 股票五行与当日五行的生克关系
    返回按推荐度排序的日期列表。
    """
    from datetime import timedelta
    from src.metaphysics.bazi import calc_bazi
    from src.metaphysics.fortune import _score_day
    from src.metaphysics.bazi import GAN_WUXING, WUXING_SHENG, WUXING_KE
    from src.utils.trading_calendar import is_trading_day, get_non_trading_reason

    bazi = calc_bazi(
        date.fromisoformat(birth_date_str),
        birth_time_str,
    )

    results = []
    today = date.today()
    for i in range(7):
        d = today + timedelta(days=i)
        try:
            lucky = _score_day(d, bazi)

            # 股票五行与当日五行匹配度
            day_wx = lucky.wuxing
            stock_wx = stock_wuxing

            stock_bonus = 0
            stock_reason = ""
            if stock_wx and day_wx:
                if day_wx == stock_wx:
                    stock_bonus = 15
                    stock_reason = f"日干{day_wx}与股票五行{stock_wx}比和"
                elif WUXING_SHENG.get(stock_wx) == day_wx:
                    stock_bonus = 25
                    stock_reason = f"股票五行{stock_wx}生日干{day_wx}"
                elif WUXING_SHENG.get(day_wx) == stock_wx:
                    stock_bonus = -10
                    stock_reason = f"日干{day_wx}生股票{stock_wx}(泄气)"
                elif WUXING_KE.get(stock_wx) == day_wx:
                    stock_bonus = -20
                    stock_reason = f"股票五行{stock_wx}克日干{day_wx}"
                elif WUXING_KE.get(day_wx) == stock_wx:
                    stock_bonus = 10
                    stock_reason = f"日干{day_wx}克股票{stock_wx}(制财)"

            combined = max(0, min(100, lucky.score + stock_bonus + 5))

            if stock_reason:
                lucky.reasons.insert(0, stock_reason)

            trading = is_trading_day(d)
            nt_reason = get_non_trading_reason(d)

            level = "大吉" if combined >= 80 else ("吉" if combined >= 65 else ("平" if combined >= 50 else ("小凶" if combined >= 35 else "凶")))
            if not trading:
                level = "休市"

            results.append({
                "date": d.isoformat(),
                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()],
                "gan": lucky.gan,
                "zhi": lucky.zhi,
                "wuxing": day_wx,
                "user_score": lucky.score,
                "stock_bonus": stock_bonus,
                "combined": combined,
                "level": level,
                "reasons": lucky.reasons,
                "is_trading": trading,
                "nt_reason": nt_reason,
                "yi": lucky.yi,
                "ji": lucky.ji,
            })
        except Exception:
            results.append(None)

    # 排序：交易日优先，然后按综合分降序
    valid = [r for r in results if r is not None]
    valid.sort(key=lambda x: (not x["is_trading"], -x["combined"]))
    return valid


if __name__ == "__main__":
    kline_viewer_page()
