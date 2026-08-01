"""
K线看盘 - 原始K线 + 美元计价 + 运势叠加
"""

import json

import pandas as pd
import streamlit as st
from datetime import date

from src.data.db import db, ExchangeRate, UserProfile, DailySignal
from src.metaphysics.ganzhi import get_daily_signal
from src.data.exchange import get_usd_cny_latest
from src.utils.logger import get_logger

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


def kline_viewer_page():
    st.title("K线看盘")
    st.caption("原始K线 · 美元计价 · 运势标注")

    db.connect()

    # 侧边栏
    with st.sidebar:
        st.header("图表配置")
        symbol = st.text_input("股票代码", value="000001")

        use_usd = st.checkbox("美元计价 (USD)", value=False)

        col1, col2 = st.columns(2)
        with col1:
            period = st.number_input("重铸周期(日)", min_value=1, max_value=30, value=1)
        with col2:
            days = st.number_input("数据天数", min_value=30, max_value=730, value=180)

        st.divider()

        # 运势叠加
        st.subheader("运势标注")
        show_fortune = st.checkbox("显示运势日", value=False)

        # 汇率信息
        rate = get_usd_cny_latest()
        if rate:
            st.caption(f"当前汇率: 1 USD = {rate:.4f} CNY")

        search = st.button("加载K线", type="primary", use_container_width=True)

        st.divider()
        st.caption("提示：美元计价的汇率来自真实汇率数据（akshare），K线数据来源见标注。")

    # ---- 主区域 ----
    if not search:
        st.info("在左侧面板输入股票代码，点击【加载K线】开始")
        db.close()
        return

    with st.spinner(f"正在加载 {symbol} K线数据..."):
        try:
            logger.info("K线加载: symbol=%s, period=%d, days=%d, usd=%s", symbol, period, days, use_usd)
            from src.data_fetcher import get_a_share_daily_kline, default_date_range

            start_date, end_date = default_date_range(days)
            df = get_a_share_daily_kline(symbol, start_date=start_date, end_date=end_date)

            if df.empty:
                logger.warning("K线数据为空: symbol=%s", symbol)
                st.error(f"无法获取 {symbol} 的数据，请检查股票代码或网络")
                db.close()
                return

            from src.kline_builder import resample_kline

            df = resample_kline(df, period) if period > 1 else df

            st.success(f"获取到 {len(df)} 根K线 (周期: {period}日)")
            logger.info("K线加载成功: %s, %d 条, period=%d", symbol, len(df), period)

            # 美元转换
            if use_usd:
                df = convert_kline_to_usd(df)
                st.info("已转换为美元计价 (基于真实历史汇率)")

            # 运势叠加标注
            if show_fortune:
                try:
                    fortune_dates = _get_fortune_dates()
                    if fortune_dates:
                        st.caption(f"运势标注了 {len(fortune_dates)} 个特殊日期")

                        # 在数据上加标记
                        df["fortune"] = df["time"].apply(
                            lambda x: "宜交易" if x in fortune_dates else ""
                        )
                except Exception:
                    st.caption("运势数据加载失败")

            # 渲染K线
            html = render_kline_html(df, use_usd=use_usd, height=750)
            st.iframe(html, height=800)

            # 数据预览
            with st.expander("数据预览"):
                show_cols = (
                    ["time", "open_usd", "high_usd", "low_usd", "close_usd", "volume"]
                    if use_usd
                    else ["time", "open", "high", "low", "close", "volume"]
                )
                avail_cols = [c for c in show_cols if c in df.columns]
                st.dataframe(df[avail_cols].tail(20), use_container_width=True)
                st.caption("数据来源: efinance (公开数据)")

            # 显示当日信号
            if show_fortune:
                with st.expander("今日玄学信号"):
                    signal = get_daily_signal(date.today())
                    st.markdown(f"日柱: **{signal['day_gan']}{signal['day_zhi']}** (五行: {signal['day_wuxing']})")
                    st.markdown(f"交易信号: **{signal['trade_signal']}**")

        except Exception as e:
            logger.error("K线加载失败: symbol=%s, error=%s", symbol, e, exc_info=True)
            st.error(f"加载失败: {e}")

    db.close()


def _get_fortune_dates() -> set:
    """获取运势宜交易的日期集合"""
    signals = DailySignal.select().where(
        DailySignal.trade_signal == "宜买入"
    )
    return {str(s.date) for s in signals}


if __name__ == "__main__":
    kline_viewer_page()
