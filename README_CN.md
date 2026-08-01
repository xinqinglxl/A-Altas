# A-ALTAS ⚒️

> 打破周期限制，重铸K线。以星象为引，观股海沉浮。

**A-ALTAS** 是一个面向个人投资者的 A 股分析工具，将 **自定义周期K线重铸** 与 **玄学量化分析** 这两个看似不相关的世界融为一体。无论是 7 分钟K线还是用八字选股，这里都有。

🌐 [English Docs](README.md)

---

## ✨ 核心功能

### 🔥 自定义周期 K 线重铸
主流炒股软件只给你固定的周期线（1 分钟、5 分钟、15 分钟、日线……）。A-ALTAS 可以让你用日K线**重铸**出任意周期的 K 线——7 分钟、13 分钟、3 日线，你想验证什么策略就生成什么周期。

### 🧧 玄学量化引擎
一套完整的中国传统玄学工具，应用于股票分析：

| 模块 | 功能说明 |
|------|---------|
| **八字排盘** | 输入公历/农历生日和时辰，自动排出四柱八字、日主五行、喜用神、生肖星座 |
| **财神选股** | 八字合盘 + 五行匹配 + 天干择时 = 财神指数排行榜，TOP 50 排序展示 |
| **每日信号** | 天干地支日柱分析、黄历宜忌、财神方位、五行板块推荐、节气轮动信号 |
| **K线看盘** | 原始K线 + 美元计价（使用真实历史汇率转换）+ 运势日标注 |

### 📊 技术栈
- **Streamlit** — 交互式多页面 Web 界面
- **lunar-python** — 八字排盘、天干地支、节气、黄历
- **akshare / efinance** — A 股公开市场数据
- **Lightweight Charts** — 交互式 K 线图渲染
- **pandas / numpy** — 数据处理
- **SQLite + Peewee** — 轻量级本地数据库

---

## 🚀 快速开始

### 环境要求
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）

### 安装与运行

```bash
# 克隆仓库
git clone git@github.com:xinqinglxl/A-Altas.git
cd A-Altas

# 安装依赖
uv sync

# 初始化数据库并填充种子数据
.venv/bin/python3 -m src.data.seeder

# 启动应用
.venv/bin/python3 -m streamlit run app.py
```

浏览器打开 **http://localhost:8501** 即可使用。

---

## 📁 项目结构

```
A-Altas/
├── app.py                    # Streamlit 入口（多页面导航）
├── src/
│   ├── metaphysics/          # 玄学引擎
│   │   ├── bazi.py           #   八字排盘（四柱推命）
│   │   ├── ganzhi.py         #   天干地支转换
│   │   └── wuxing.py         #   五行映射
│   ├── data/                 # 数据层
│   │   ├── db.py             #   SQLite 表结构 & Peewee ORM
│   │   ├── exchange.py       #   美元/人民币汇率获取
│   │   ├── seeder.py         #   数据库初始化脚本
│   │   └── fetcher.py        #   A 股数据获取（旧版）
│   ├── strategy/             # 评分引擎
│   │   └── scorer.py         #   财神指数计算
│   ├── viz/                  # 可视化
│   │   └── chart_renderer.py #   K线图表渲染
│   ├── kline_builder.py      # K线重铸逻辑
│   └── pages/                # Streamlit 页面
│       ├── home.py           #   八字排盘页
│       ├── stock_picker.py   #   财神选股页
│       ├── daily_signal.py   #   每日信号页
│       └── kline_viewer.py   #   K线看盘页
├── data/                     # SQLite 数据库（gitignore 排除）
└── pyproject.toml
```

---

## 🔍 数据真实性说明

我们尽可能使用真实数据。以下是各类型数据的真实度说明：

| 数据 | 来源 | 真实度 |
|------|------|:---:|
| 股票代码与名称 | akshare（沪深300成分股） | ✅ 真实 |
| 美元/人民币汇率 | akshare 历史汇率 | ✅ 真实 |
| 每日干支、节气、黄历 | lunar-python 计算 | ✅ 真实 |
| IPO日期 / 成立日期 | **模拟生成**（akshare接口不可用） | ⚠️ 假数据 |
| 公司八字 | 基于模拟日期推算 | ⚠️ 假数据 |
| 板块五行映射 | 人工静态归类 | ⚠️ 主观分类 |

**所有假数据在界面中均标注 `[假]`，一目了然。**

---

## ⚠️ 免责声明

本项目仅供 **学习研究与娱乐** 使用，不构成任何投资建议，据此交易盈亏自负。玄学功能属于文化趣味探索，非金融模型——请勿基于八字合盘分数做出真实投资决策。

数据获取请确保符合相关法律法规及数据源使用协议。

---

## 🥇 赞助

- [ZMTO](https://console.zmto.com/?affid=1567)
- [ZMTO 测评](https://vps.jinqians.com/zmto/)

---

## License

[MIT](LICENSE)
