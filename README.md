# A-ALTAS ⚒️

> Break the limits. Reforge your K-lines. Trade with the stars.

**A-ALTAS** is a personal A-share (China stock market) analysis toolkit that blends two unlikely worlds: **custom-period K-line reforging** and **Chinese metaphysics quantitative analysis**. It helps you see the market in ways mainstream trading software won't let you — whether that's a 7-minute candlestick or a stock pick guided by your Bazi (八字).

🌐 [中文文档](README_CN.md)

---

## ✨ Features

### 🔥 Custom-Period K-Line Reforging
Standard platforms lock you into fixed intervals (1m, 5m, 15m, daily...). A-ALTAS lets you **reforge** daily K-lines into any custom period — 7 minutes, 13 minutes, 3 days, whatever your strategy demands.

### 🧧 Metaphysics Quantitative Engine
A full stack of traditional Chinese metaphysical tools applied to stock analysis:

| Module | What It Does |
|--------|-------------|
| **Bazi Chart** (八字排盘) | Input your birth date & time, get your Four Pillars, Day Master element, and XiYong Shen (喜用神) |
| **Fortune Stock Picker** (财神选股) | Scores stocks by Bazi compatibility, Five Elements matching, and Ganzhi timing — ranks the top 50 |
| **Daily Signal** (每日信号) | Heavenly Stems & Earthly Branches analysis, Huangli (almanac) dos & don'ts, sector-element recommendations, solar-term rotation signals |
| **USD K-Line Viewer** (K线看盘) | Original + USD-denominated candlestick charts using real historical exchange rates, with fortune-day annotations |

### 📊 Tech Stack
- **Streamlit** — interactive multi-page web UI
- **lunar-python** — Bazi, Ganzhi, solar terms, Chinese almanac
- **akshare / efinance** — A-share public market data
- **Lightweight Charts** — interactive candlestick rendering
- **pandas / numpy** — data processing
- **SQLite + Peewee** — lightweight local database

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Install & Run

```bash
# Clone the repo
git clone git@github.com:xinqinglxl/A-Altas.git
cd A-Altas

# Install dependencies
uv sync

# Initialize database & seed data
.venv/bin/python3 -m src.data.seeder

# Launch the app
.venv/bin/python3 -m streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

---

## 📁 Project Structure

```
A-Altas/
├── app.py                    # Streamlit entry point (multi-page navigation)
├── src/
│   ├── metaphysics/          # Metaphysics engine
│   │   ├── bazi.py           #   Bazi (Four Pillars of Destiny)
│   │   ├── ganzhi.py         #   Heavenly Stems & Earthly Branches
│   │   └── wuxing.py         #   Five Elements mapping
│   ├── data/                 # Data layer
│   │   ├── db.py             #   SQLite schema & Peewee models
│   │   ├── exchange.py       #   USD/CNY exchange rate fetcher
│   │   ├── seeder.py         #   Database initializer
│   │   └── fetcher.py        #   A-share data (legacy)
│   ├── strategy/             # Scoring engine
│   │   └── scorer.py         #   Fortune Index (财神指数) calculation
│   ├── viz/                  # Visualization
│   │   └── chart_renderer.py #   K-line chart rendering
│   ├── kline_builder.py      # K-line reforging logic
│   └── pages/                # Streamlit pages
│       ├── home.py           #   Bazi chart input
│       ├── stock_picker.py   #   Fortune stock ranking
│       ├── daily_signal.py   #   Daily metaphysics signals
│       └── kline_viewer.py   #   K-line viewer with USD mode
├── data/                     # SQLite database (gitignored)
└── pyproject.toml
```

---

## 🔍 Data Authenticity

We strive to use real data wherever possible. Here's what's real and what's simulated:

| Data | Source | Authenticity |
|------|--------|:---:|
| Stock codes & names | akshare (CSI 300 constituents) | ✅ Real |
| USD/CNY exchange rates | akshare historical FX | ✅ Real |
| Daily Ganzhi, solar terms, Huangli | lunar-python calculation | ✅ Real |
| IPO / founding dates | **Simulated** (akshare API unavailable) | ⚠️ Fake |
| Company Bazi | Derived from simulated dates | ⚠️ Fake |
| Sector Five-Element mapping | Manual static classification | ⚠️ Subjective |

**All simulated data is explicitly labeled `[假]` in the UI.**

---

## ⚠️ Disclaimer

This project is for **educational and entertainment purposes only**. It does NOT constitute investment advice. Trade at your own risk. The metaphysics features are cultural curiosities, not financial models — please do not make real investment decisions based on Bazi compatibility scores.

Ensure your data collection methods comply with applicable laws and data source terms of service.

---

## License

[MIT](LICENSE)
