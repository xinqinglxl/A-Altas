"""
五行映射与生克分析模块
包含板块五行映射表和五行匹配计算
"""

from typing import Optional

# 五行生克关系
WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
WUXING_BEI_SHENG = {v: k for k, v in WUXING_SHENG.items()}  # 被谁生
WUXING_BEI_KE = {v: k for k, v in WUXING_KE.items()}  # 被谁克

# 板块五行映射表
# 基于申万行业分类与五行属性的对应关系
SECTOR_WUXING_MAP = {
    # 金：金融、机械、金属
    "银行": "金",
    "证券": "金",
    "保险": "金",
    "多元金融": "金",
    "贵金属": "金",
    "工业金属": "金",
    "小金属": "金",
    "通用设备": "金",
    "专用设备": "金",
    "工程机械": "金",
    "自动化设备": "金",
    "汽车零部件": "金",
    "钢铁": "金",
    "非银金融": "金",

    # 木：农业、林业、造纸、中药、纺织
    "种植业": "木",
    "林业": "木",
    "农产品加工": "木",
    "造纸": "木",
    "中药": "木",
    "化学制药": "木",
    "生物制品": "木",
    "纺织制造": "木",
    "服装家纺": "木",
    "包装印刷": "木",

    # 水：航运、水务、饮料、旅游
    "航运港口": "水",
    "物流": "水",
    "铁路公路": "水",
    "水务": "水",
    "环保": "水",
    "饮料制造": "水",
    "旅游及景区": "水",
    "酒店餐饮": "水",
    "渔业": "水",
    "机场航运": "水",
    "贸易": "水",

    # 火：电力、能源、军工、传媒、半导体
    "电力": "火",
    "电网设备": "火",
    "光伏设备": "火",
    "风电设备": "火",
    "军工电子": "火",
    "军工装备": "火",
    "能源金属": "火",
    "石油石化": "火",
    "煤炭开采": "火",
    "半导体": "火",
    "电子元件": "火",
    "消费电子": "火",
    "影视院线": "火",
    "广告营销": "火",
    "游戏": "火",
    "数字媒体": "火",
    "计算机设备": "火",
    "通信设备": "火",
    "通信服务": "火",

    # 土：房地产、建材、煤炭、基建、矿业
    "房地产开发": "土",
    "房地产服务": "土",
    "建筑材料": "土",
    "建筑装饰": "土",
    "装修建材": "土",
    "水泥": "土",
    "玻璃玻纤": "土",
    "基础建设": "土",
    "工程咨询服务": "土",
    "非金属材料": "土",
    "煤炭": "土",
    "焦炭": "土",
    "农化制品": "土",
    "化学制品": "土",
}


def get_sector_wuxing(sector_name: str) -> Optional[str]:
    """获取板块的五行属性"""
    return SECTOR_WUXING_MAP.get(sector_name)


def get_wuxing_relation(mine: str, theirs: str) -> str:
    """
    五行关系判断
    Returns: '生我'(被生), '我生'(我去生), '克我'(被克), '我克'(我去克), '比和'(相同)
    """
    if mine == theirs:
        return "比和"
    if WUXING_SHENG.get(mine) == theirs:
        return "我生"  # 我生对方
    if WUXING_SHENG.get(theirs) == mine:
        return "生我"  # 对方生我
    if WUXING_KE.get(mine) == theirs:
        return "我克"
    if WUXING_KE.get(theirs) == mine:
        return "克我"
    return "未知"


def wuxing_match_score(my_wuxing: str, target_wuxing: str) -> float:
    """
    五行匹配评分 0-100
    以我的五行为基准，评对方五行对我的影响
    """
    relation = get_wuxing_relation(my_wuxing, target_wuxing)
    scores = {
        "生我": 85,
        "比和": 75,
        "我生": 60,
        "我克": 45,
        "克我": 25,
    }
    return float(scores.get(relation, 50))


def get_wuxing_compatible_sectors(favorable_wuxing: list[str]) -> list[str]:
    """
    根据喜用神获取匹配的板块列表
    """
    sectors = []
    for sector, wx in SECTOR_WUXING_MAP.items():
        if wx in favorable_wuxing:
            sectors.append(sector)
    return sectors


def get_wuxing_avoid_sectors(unfavorable_wuxing: list[str]) -> list[str]:
    """
    根据忌神获取应回避的板块列表
    """
    sectors = []
    for sector, wx in SECTOR_WUXING_MAP.items():
        if wx in unfavorable_wuxing:
            sectors.append(sector)
    return sectors


def wuxing_color(wx: str) -> str:
    """五行对应颜色"""
    colors = {
        "金": "#FFD700",  # 金白/金色
        "木": "#228B22",  # 青绿
        "水": "#1E90FF",  # 黑蓝
        "火": "#FF4500",  # 红
        "土": "#8B7355",  # 黄棕
    }
    return colors.get(wx, "#888888")


WUXING_LIST = ["金", "木", "水", "火", "土"]


if __name__ == "__main__":
    # 测试
    print("板块五行映射示例:")
    for k, v in list(SECTOR_WUXING_MAP.items())[:5]:
        print(f"  {k} → {v}")

    print(f"\n喜用神[金, 水]匹配的板块: {get_wuxing_compatible_sectors(['金', '水'])}")
    print(f"忌神[火]应回避的板块: {get_wuxing_avoid_sectors(['火'])}")
    print(f"五行金对木的关系: {get_wuxing_relation('金', '木')} (金克木)")
    print(f"匹配分数: {wuxing_match_score('金', '木')}")
