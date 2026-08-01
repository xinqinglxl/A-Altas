import json

import pandas as pd


def render_kline_html(df: pd.DataFrame, height: int = 800) -> str:
    """将 DataFrame 转为内嵌 TradingView Lightweight Charts v4 的 HTML"""

    candles = []
    volumes = []
    for _, row in df.iterrows():
        t = str(row["time"])
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        v = float(row["volume"])

        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        color = "rgba(38,166,91,0.5)" if c >= o else "rgba(239,83,80,0.5)"
        volumes.append({"time": t, "value": v, "color": color})

    candles_json = json.dumps(candles)
    volumes_json = json.dumps(volumes)

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
  timeScale: {{
    borderColor: '#313244',
    timeVisible: false,
    secondsVisible: false,
  }},
}});

// 【v4 API】使用 addSeries 替代旧版 addCandlestickSeries
const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {{
  upColor: '#26a65b',
  downColor: '#ef5350',
  borderDownColor: '#ef5350',
  borderUpColor: '#26a65b',
  wickDownColor: '#ef5350',
  wickUpColor: '#26a65b',
}});
candleSeries.setData({candles_json});

// 【v4 API】使用 addSeries 替代旧版 addHistogramSeries
const volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {{
  color: '#26a65b',
  priceFormat: {{ type: 'volume' }},
  priceScaleId: 'volume',
}});
volumeSeries.setData({volumes_json});

// v4 中 volume 的 scaleMargins 需要在 priceScale 上设置
chart.priceScale('volume').applyOptions({{
  scaleMargins: {{ top: 0.8, bottom: 0 }},
}});

chart.timeScale().fitContent();

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
