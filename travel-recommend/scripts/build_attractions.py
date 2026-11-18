#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""构建景点知识库：抓取公开榜单 → 解析名称/介绍 → 去重 → 打标签 → 输出 JSONL。

为什么要有这个库：用户说「我去过 XX」时，模型不该凭印象临时挑替代景点，
而应该有一个可检索的中国景点池（按省份/类型/标签/关键词），先查库再补网。

用法：
  uv run --no-project scripts/build_attractions.py              # 抓取 + 生成
  uv run --no-project scripts/build_attractions.py --enrich      # 额外用维基百科补缺失介绍
  uv run --no-project scripts/build_attractions.py --offline     # 只用本地缓存，不联网

产物：
  assets/attractions/attractions.jsonl   主库（每行一个景点）
  assets/attractions/sources.md          来源与可用性说明
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "attractions"
CURATED = OUT_DIR / "curated.jsonl"
CACHE = OUT_DIR / ".cache"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"}

# 已实测可访问的来源（2026-11-18）。知乎 403、百度百科反爬、头条空页 → 不列入。
SOURCES = [
    {"id": "ctrip50", "kind": "numbered", "url": "https://gs.ctrip.com/html5/you/travels/110000/4106445.html",
     "title": "《国家地理》一生必去的 50 个地方（国内篇）· 携程"},
    {"id": "sohu30", "kind": "numbered", "url": "https://www.sohu.com/a/857397725_121948408",
     "title": "中国必去的 30 处旅游名单 · 搜狐"},
    {"id": "sohu34", "kind": "province", "url": "https://www.sohu.com/a/794937702_121948408",
     "title": "中国 34 个省区的代表景点 · 搜狐"},
    {"id": "maigoo", "kind": "table", "url": "https://www.maigoo.com/top/425030.html",
     "title": "2026 中国景区百强榜 · 买购网"},
]

PROVINCES = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
             "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
             "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
             "新疆", "香港", "澳门", "台湾"]

CITY_HINTS = {
    "黄山市": "安徽", "泰安市": "山东", "上饶市": "江西", "张家界市": "湖南", "韶关市": "广东",
    "苏州市": "江苏", "北京市": "北京", "九江市": "江西", "杭州市": "浙江", "厦门市": "福建",
    "宜昌市": "湖北", "渭南市": "陕西", "阿坝藏族羌族自治州": "四川", "青岛市": "山东",
    "忻州市": "山西", "南平市": "福建", "延边朝鲜族自治州": "吉林", "昌吉州": "新疆",
    "丽江市": "云南", "西安市": "陕西", "乐山市": "四川", "温州市": "浙江", "舟山市": "浙江",
    "黑河市": "黑龙江", "甘孜藏族自治州": "四川", "拉萨市": "西藏", "焦作市": "河南",
    "铜仁市": "贵州", "牡丹江市": "黑龙江", "黔南布依族苗族自治州": "贵州", "池州市": "安徽",
    "承德市": "河北", "大连市": "辽宁", "广州市": "广东", "保定市": "河北", "十堰市": "湖北",
    "郑州市": "河南", "安庆市": "安徽", "三亚市": "海南", "成都市": "四川", "南京市": "江苏",
    "台州市": "浙江", "昆明市": "云南", "湖州市": "浙江", "兴安盟": "内蒙古", "宁德市": "福建",
    "南阳市": "河南", "大兴安岭地区": "黑龙江", "毕节市": "贵州", "黔西南布依族苗族自治州": "贵州",
    "巴中市": "四川", "楚雄彝族自治州": "云南", "阿克苏地区": "新疆", "蓟州区": "天津",
    "黄山市黄山区": "安徽", "灵川县": "广西", "仁化县": "广东", "黟县": "安徽", "玉山县": "江西",
    "五台县": "山西", "武夷山市": "福建", "安图县": "吉林", "阜康市": "新疆", "临潼区": "陕西",
    "峨眉山市": "四川", "乐清市": "浙江", "普陀区": "浙江", "五大连池市": "黑龙江",
    "稻城县": "四川", "修武县": "河南", "江口县": "贵州", "宁安市": "黑龙江", "荔波县": "贵州",
    "青阳县": "安徽", "双桥区": "河北", "金州区": "辽宁", "番禺区": "广东", "涞源县": "河北",
    "吴江区": "江苏", "丹江口市": "湖北", "登封市": "河南", "潜山市": "安徽", "吉阳区": "海南",
    "大邑县": "四川", "东城区": "北京", "涞水县": "河北", "滨湖区": "江苏", "雁塔区": "陕西",
    "镇宁布依族苗族自治县": "贵州", "松北区": "黑龙江", "中山区": "辽宁", "石林彝族自治县": "云南",
    "秦淮区": "江苏", "天台县": "浙江", "昆山市": "江苏", "富蕴县": "新疆", "平遥县": "山西",
    "洛龙区": "河南", "仙居县": "浙江", "延庆区": "北京", "南岳区": "湖南", "弋阳县": "江西",
    "蒙阴县": "山东", "芦溪县": "江西", "浦东新区": "上海", "恩施市": "湖北", "泸定县": "四川",
    "栾川县": "河南", "临泽县": "甘肃", "桐乡市": "浙江", "平山县": "河北", "泰宁县": "福建",
    "新宁县": "湖南", "阆中市": "四川", "宜川县": "陕西", "大新县": "广西", "贵溪市": "江西",
    "浑源县": "山西", "嵩县": "河南", "赞皇县": "河北", "敦煌市": "甘肃", "元阳县": "云南",
    "房山区": "北京", "南浔区": "浙江", "阿尔山市": "内蒙古", "屏南县": "福建", "西峡县": "河南",
    "漠河市": "黑龙江", "织金县": "贵州", "兴义市": "贵州", "南江县": "四川", "元谋县": "云南",
    "库车市": "新疆", "休宁县": "安徽", "福鼎市": "福建", "遵义市": "贵州",
}

TYPE_RULES = [
    ("长城", ["长城"]),
    ("石窟", ["石窟", "莫高窟", "云冈"]),
    ("园林", ["园林", "拙政园", "留园"]),
    ("冰川", ["冰川", "达古", "海螺沟"]),
    ("瀑布", ["瀑布", "壶口"]),
    ("草原", ["草原", "坝上", "呼伦贝尔"]),
    ("梯田", ["梯田", "龙脊", "元阳"]),
    ("海岛", ["岛", "湾", "滩", "蜈支洲", "鼓浪屿", "东极"]),
    ("峡谷", ["峡谷", "大峡谷", "恩施"]),
    ("溶洞", ["洞", "水洞", "芦笛"]),
    ("荒漠", ["沙漠", "戈壁", "魔鬼城", "雅丹", "土林", "丹霞", "七彩"]),
    ("湖泊", ["湖", "措", "纳木", "赛里木", "青海湖", "西湖", "洱海", "泸沽", "九寨"]),
    ("山岳", ["山", "峰", "岭", "雪山", "贡嘎", "梅里", "珠峰", "天门山"]),
    ("博物馆", ["博物馆", "博物院", "兵马俑"]),
    ("寺庙宫观", ["寺", "庙", "宫", "祠", "布达拉", "普陀", "五台", "九华", "武当", "梵净"]),
    ("古建筑", ["故宫", "天坛", "颐和园", "避暑山庄", "大雁塔", "塔", "桥", "楼阁", "牌坊"]),
    ("红色/纪念", ["西柏坡", "遗址", "纪念"]),
    ("城市地标", ["东方明珠", "天津之眼", "洪崖洞", "维多利亚", "大三巴"]),
    ("古村镇", ["古城", "古镇", "古村", "村", "寨", "宏村", "西递", "周庄", "乌镇", "西塘",
                "南浔", "同里", "凤凰", "阆中", "平遥", "丽江古城", "婺源"]),
]

TAG_RULES = {
    "秋色": ["喀纳斯", "额济纳", "坝上", "婺源", "米亚罗", "银杏", "腾冲", "香山"],
    "冰雪": ["长白山", "雪乡", "哈尔滨", "漠河", "北极村", "达古冰川", "海螺沟", "太阳岛"],
    "避寒": ["三亚", "西双版纳", "厦门", "鼓浪屿", "海口", "北海", "东极"],
    "赏花": ["婺源", "林芝", "杏花", "樱花", "油菜花", "桃花", "杜鹃"],
    "摄影": ["霞浦", "元阳", "小东江", "张掖", "额济纳", "牛背山", "东极", "坝上"],
    "徒步": ["武功山", "华山", "黄山", "泰山", "雨崩", "虎跳峡", "牛背山"],
    "人文": ["古城", "古镇", "石窟", "寺", "宫", "遗址", "博物馆", "长城", "故宫"],
    "亲子": ["熊猫", "卧龙", "迪士尼", "长隆", "海洋公园"],
    "自驾": ["草原", "沙漠", "公路", "独库", "318"],
}


def fetch(url: str, cache_name: str, offline: bool) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{cache_name}.html"
    if path.is_file() and (offline or path.stat().st_size > 5000):
        return path.read_text(encoding="utf-8", errors="replace")
    if offline:
        print(f"  跳过 {cache_name}：--offline 且本地无缓存", file=sys.stderr)
        return ""
    try:
        response = requests.get(url, headers=UA, timeout=30)
        response.raise_for_status()
        text = response.text
    except Exception as exc:
        print(f"  跳过 {cache_name}：{type(exc).__name__}", file=sys.stderr)
        return ""
    path.write_text(text, encoding="utf-8")
    return text


def html_to_lines(html: str) -> list[str]:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


# 来源自带的错字 / 带省市前缀的名字；右侧为规范名（原名会进 aliases，检索不受影响）
NAME_FIX = {
    "戈阳龟峰": "弋阳龟峰",
    # 省市前缀：城市信息在 city 字段里，名字只留景点名
    "云南石林": "石林",
    "北京颐和园": "颐和园",
    "天津盘山": "盘山",
    "安徽齐云山": "齐云山",
    "浙江天台山": "天台山",
    "青岛崂山": "崂山",
    "洛阳白云山": "白云山",
    "洛阳老君山": "老君山",
    "焦作云台山": "云台山",
    "保定白石山": "白石山",
    "涞水县野三坡": "野三坡",
    "新疆可可托海": "可可托海",
    "无锡太湖鼋头渚": "鼋头渚",
    "大连金石滩": "金石滩",
    # 「西递宏村皖南古村落」是 5A 的合并写法；宏村另有条目，这里保留西递
    "西递宏村皖南古村落": "西递",
}

# 同一景区/同一事物的重复条目：左侧并入右侧（左侧进 aliases，不丢检索能力）
DUP_TARGET = {
    "承德避暑山庄及周围寺庙": "承德避暑山庄",
    "昆明石林": "云南石林",
    "陕晋壶口瀑布": "黄河壶口瀑布",
    "长城": "万里长城",
    "神农架国家级自然保护区": "神农架",
    "苍山洱海": "洱海",
    "武陵源": "张家界",
}

# 关键词规则判错的类型，用人工纠偏覆盖（只覆盖明确的错判）
TYPE_OVERRIDE = {
    "洪崖洞": "城市地标",       # 规则命中「洞」→ 溶洞
    "东方明珠塔": "城市地标",   # 规则命中「塔」→ 古建筑
    "夫子庙-秦淮风光带": "古村镇",
    "承德避暑山庄": "园林",     # 规则命中「山」→ 山岳
    "阿尔山柴河": "综合",       # 5A 景区（火山/森林/温泉），不是一座山
    "房山世界地质公园": "综合",
    "三星堆": "博物馆",
    "日月潭": "湖泊",           # 规则未命中「湖」，落进「综合」
    "天山天池": "湖泊",         # 冰碛湖，规则命中「山」
    "桂林山水": "综合",
    "亚龙湾": "综合",           # 海湾，不是海岛
    "老虎滩海洋公园": "综合",
    "金石滩": "综合",           # 海滨，不是海岛
    "白哈巴": "古村镇",
    "扎尕那": "古村镇",
    "鼋头渚": "湖泊",           # 太湖边的半岛，规则改名后丢了「湖」字
}


def canonical_name(raw: str) -> tuple[str, str]:
    """清洗 + 纠错 + 合并，返回 (规范名, 需要并入 aliases 的原名)。"""
    clean = clean_name(raw)
    fixed = NAME_FIX.get(clean, clean)
    name = DUP_TARGET.get(fixed, fixed)
    name = NAME_FIX.get(name, name)  # 合并目标本身可能还带省市前缀（昆明石林 → 云南石林 → 石林）
    return name, (clean if clean != name else "")


def clean_name(raw: str) -> str:
    # 去掉【外号】、括号补充与编号；「长白山·天池」合并成一个名字
    name = re.sub(r"【[^】]*】|\[[^\]]*\]|（[^）]*）|\([^)]*\)", " ", raw)
    name = re.sub(r"^(中国)?\d+\s*[、.．]\s*", "", name)
    for _ in range(4):  # 「亚龙湾国家旅游度假区」这类要连剥两层后缀
        stripped = re.sub(r"(风景名胜区|旅游景区|旅游度假区|风景区|景区|旅游区|风景|国家级|国家)$", "", name.strip())
        if stripped == name:
            break
        name = stripped
    name = name.replace("·", "")
    return re.sub(r"\s+", "", name).strip("：:—－-")


def parse_numbered(lines: list[str]) -> list[dict]:
    """「1、黄山」或「**1、万里长城：副标题**」这类编号清单；「四川·九寨沟」保留省份前缀。"""
    items: list[dict] = []
    current: dict | None = None
    for line in lines:
        head = re.match(r"^(\d{1,2})\s*[、.．]\s*(.{2,80})$", line)
        if head and not re.search(r"[。！？]", head.group(2)):
            raw = head.group(2)
            title, _, subtitle = raw.partition("：")
            current = {"raw": title.strip(), "subtitle": subtitle.strip(), "body": []}
            items.append(current)
            continue
        if current is not None and len(line) > 20 and not line.startswith("http"):
            if len(current["body"]) < 3:
                current["body"].append(line)
    return items


def split_province(raw: str) -> tuple[str, str]:
    """把「四川·九寨沟」「安徽·黄山」拆成 (省, 名称)。"""
    match = re.match(r"^([^·]{2,6})·(.{2,40})$", raw)
    if not match:
        return "", raw
    prefix, name = match.group(1).strip(), match.group(2).strip()
    for prov in PROVINCES:
        if prefix == prov or prefix.startswith(prov) or prov in prefix:
            return prov, name
    return "", raw


def parse_province(lines: list[str]) -> list[dict]:
    """「1、新疆代表景点——喀纳斯景区【人间仙境】」这类省区代表清单。"""
    items: list[dict] = []
    current: dict | None = None
    for line in lines:
        head = re.match(r"^\d{1,2}\s*[、.．]\s*([^—]{1,12})代表景点——(.{2,40})$", line)
        if head:
            current = {"province": head.group(1).strip(), "raw": head.group(2).strip(), "body": []}
            items.append(current)
            continue
        if current is not None and len(line) > 20 and len(current["body"]) < 2:
            current["body"].append(line)
    return items


def parse_table_html(html: str) -> list[dict]:
    """maigoo 的榜单是 HTML 表格：名称是 <a> 文本，地址在下一列。"""
    items: list[dict] = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        link = re.search(r"(?is)<a[^>]+>(.{2,40}?)</a>", row)
        cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)
        if not link or len(cells) < 2:
            continue
        name = re.sub(r"(?s)<[^>]+>", " ", link.group(1))
        name = re.sub(r"\s+", "", name)
        address = re.sub(r"(?s)<[^>]+>", " ", cells[-1])
        address = re.sub(r"\s+", "", address)
        if not name or not address:
            continue
        items.append({"raw": name, "address": address, "body": []})
    return items


def _norm_title(text: str) -> str:
    return re.sub(r"[\s_\-—－()（）]|维基百科|Wikipedia", "", text)


GENERIC_TAIL = re.compile(
    r"(国家地质公园|世界地质公园|地质公园|国家森林公园|森林公园|国家自然保护区|自然保护区"
    r"|旅游度假区|度假区|旅游景区|风景区|景区|国家级|国家|乐园|公园|古镇|古城|瀑布|大峡谷|峡谷)$"
)


def _core(text: str) -> str:
    text = _norm_title(text)
    for _ in range(2):
        stripped = GENERIC_TAIL.sub("", text)
        if stripped == text:
            break
        text = stripped
    return text


DISAMBIG = re.compile(r"^.{2,14}(可以指|可能指|常指|是指不同的)")
# 影视/书籍条目：西柏坡曾配到「《走出西柏坡》」这部 2001 年的电影
CREATIVE = re.compile(r"^《|^.{0,8}(电影|影片|电视剧|小说|歌曲|专辑)")


def is_creative_work(extract: str) -> bool:
    return bool(CREATIVE.match(extract[:30]))


def intro_conflicts(intro: str, province: str) -> bool:
    """只检查「位于/地处」后面的地点短语，避免把「北距温州市 150 公里」当成省份冲突。"""
    if not province:
        return False
    match = re.search(r"(?:位于|地处|坐落于|座落于)([^。；;，,、]{0,24})", intro[:90])
    if not match:
        return False
    span = match.group(1)
    for prov in PROVINCES:
        if prov != province and prov in span:
            return True
    for city, prov in CITY_HINTS.items():
        if prov != province and city in span:
            return True
    return False


def wiki_title_ok(name: str, title: str) -> bool:
    """只接受与景点同一实体的页面标题。

    三种放行：核心名相同（天坛公园/天坛）、一方包含另一方且占比≥0.5（南岳衡山/衡山）、
    相似度≥0.75（德天跨国瀑布/德天瀑布）。像「阿尔山柴河」拿到「柴河（辽宁河流）」
    占比 0.4、相似度 0.57，会被挡住。
    """
    n, t = _core(name), _core(title)
    if not n or not t:
        return False
    # 交通/行政条目不是景点：同里站、广州长隆站、XX 机场
    if re.search(r"(站|车站|机场|地铁|港口|码头|线路|铁路)$", title):
        return False
    # 行政级别条目：光雾山镇、嶂石岩镇、泰宁县（记录名本身带这个字则放行，如南浔古镇）
    admin = re.search(r"(县|镇|乡|街道|社区|区)$", title)
    if admin and not re.search(re.escape(admin.group(1)) + "$", name):
        return False
    # 历史政权条目：大理曾配到「大理国」（937—1094 年的政权），不是古城
    if re.search(r"(国|王朝|帝国)$", title) and not re.search(r"(国|王朝|帝国)$", name):
        return False
    # 古镇/古城配到行政镇或市政府条目：南浔古镇 ← 南浔镇、阆中古城 ← 阆中市
    if name.endswith(("古镇", "古城", "古村")) and title.endswith(("镇", "市", "县", "区")) \
            and not title.endswith(("古镇", "古城", "古村")):
        return False
    if n == t:
        return True
    short, long = sorted((n, t), key=len)
    if short in long and (len(short) / len(long) >= 0.5 or len(short) >= 3):
        return True
    return SequenceMatcher(None, n, t).ratio() >= 0.75


def wiki_title_from_url(url: str) -> str:
    tail = url.rsplit("/", 1)[-1]
    return unquote(tail).replace("_", " ")


def wiki_intro(name: str, province: str = "") -> tuple[str, str, str] | None:
    """维基补介绍：标题精确查 + 搜索候选，取与景点名最接近且通过校验的那条。"""
    queries = [
        {"action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
         "titles": name, "format": "json", "redirects": "1"},
        {"action": "query", "generator": "search", "gsrsearch": name, "gsrlimit": "5",
         "prop": "extracts", "exintro": "1", "explaintext": "1", "format": "json"},
    ]
    best: tuple[float, str, str, str] | None = None
    for params in queries:
        try:
            payload = requests.get("https://zh.wikipedia.org/w/api.php", params=params,
                                   headers=UA, timeout=25).json()
        except Exception:
            continue
        for page in ((payload.get("query") or {}).get("pages") or {}).values():
            extract = re.sub(r"\s+", "", (page.get("extract") or "").strip())
            title = page.get("title", name)
            if len(extract) <= 40 or not wiki_title_ok(name, title):
                continue
            if DISAMBIG.match(extract) or is_creative_work(extract) or intro_conflicts(extract, province):
                continue
            score = 2.0 if _core(title) == _core(name) else SequenceMatcher(None, _core(name), _core(title)).ratio()
            if best is None or score > best[0]:
                best = (score, extract, title, "https://zh.wikipedia.org/wiki/" + title.replace(" ", "_"))
    return best[1:] if best else None


NAME_PROVINCE = {
    "万里长城": "北京", "长城": "北京", "大兴安岭": "黑龙江", "坝上草原": "河北", "坝上": "河北",
    "呼伦贝尔": "内蒙古", "额济纳": "内蒙古", "阿尔山": "内蒙古", "纳木措": "西藏", "纳木错": "西藏",
    "色达": "四川", "稻城亚丁": "四川", "贡嘎山": "四川", "牛背山": "四川", "蜀南竹海": "四川",
    "丹巴藏寨": "四川", "海螺沟": "四川", "卧龙": "四川", "阆中": "四川", "都江堰": "四川",
    "黄龙": "四川", "九寨沟": "四川", "达古冰川": "四川", "峨眉山": "四川", "锦里": "四川",
    "泸沽湖": "云南", "西双版纳": "云南", "元阳梯田": "云南", "腾冲": "云南", "丽江": "云南",
    "大理": "云南", "苍山洱海": "云南", "洱海": "云南", "石林": "云南", "梅里雪山": "云南",
    "喀纳斯": "新疆", "天鹅泉": "新疆", "白哈巴": "新疆", "乌尔禾魔鬼城": "新疆",
    "天山天池": "新疆", "可可托海": "新疆", "赛里木湖": "新疆", "杏花沟": "新疆",
    "霞浦": "福建", "武夷山": "福建", "鼓浪屿": "福建", "泰宁": "福建", "太姥山": "福建",
    "东极岛": "浙江", "南浔": "浙江", "西塘": "浙江", "乌镇": "浙江", "雁荡山": "浙江",
    "普陀山": "浙江", "神仙居": "浙江", "天台山": "浙江", "西湖": "浙江", "千岛湖": "浙江",
    "婺源": "江西", "三清山": "江西", "武功山": "江西", "庐山": "江西", "龙虎山": "江西",
    "龟峰": "江西", "滕王阁": "江西", "井冈山": "江西",
    "龙脊梯田": "广西", "阳朔": "广西", "漓江": "广西", "桂林": "广西", "德天瀑布": "广西",
    "恩施": "湖北", "恩施大峡谷": "湖北", "神农架": "湖北", "武当山": "湖北", "三峡": "湖北",
    "张家界": "湖南", "武陵源": "湖南", "凤凰古城": "湖南", "衡山": "湖南", "小东江": "湖南",
    "崀山": "湖南", "洞庭湖": "湖南",
    "华山": "陕西", "兵马俑": "陕西", "壶口瀑布": "陕西", "大雁塔": "陕西", "华清池": "陕西",
    "张掖": "甘肃", "七彩丹霞": "甘肃", "莫高窟": "甘肃", "鸣沙山": "甘肃", "嘉峪关": "甘肃",
    "扎尕那": "甘肃", "麦积山": "甘肃",
    "五大连池": "黑龙江", "镜泊湖": "黑龙江", "北极村": "黑龙江", "太阳岛": "黑龙江",
    "长白山": "吉林", "净月潭": "吉林", "松花湖": "吉林",
    "本溪水洞": "辽宁", "金石滩": "辽宁", "老虎滩": "辽宁", "千山": "辽宁",
    "承德避暑山庄": "河北", "白石山": "河北", "野三坡": "河北", "嶂石岩": "河北", "西柏坡": "河北",
    "五台山": "山西", "平遥古城": "山西", "云冈石窟": "山西", "恒山": "山西", "壶口": "山西",
    "泰山": "山东", "崂山": "山东", "沂蒙山": "山东", "蓬莱阁": "山东", "曲阜": "山东",
    "嵩山": "河南", "少林寺": "河南", "龙门石窟": "河南", "云台山": "河南", "老君山": "河南",
    "白云山": "河南", "西峡": "河南", "清明上河园": "河南",
    "黄山": "安徽", "九华山": "安徽", "天柱山": "安徽", "齐云山": "安徽", "宏村": "安徽",
    "西递": "安徽", "巢湖": "安徽",
    "苏州园林": "江苏", "周庄": "江苏", "同里": "江苏", "鼋头渚": "江苏", "夫子庙": "江苏",
    "中山陵": "江苏", "瘦西湖": "江苏", "拙政园": "江苏",
    "广州长隆": "广东", "丹霞山": "广东", "开平碉楼": "广东", "罗浮山": "广东",
    "蜈支洲岛": "海南", "亚龙湾": "海南", "天涯海角": "海南", "分界洲岛": "海南",
    "黄果树": "贵州", "荔波": "贵州", "梵净山": "贵州", "织金洞": "贵州", "万峰林": "贵州",
    "西江千户苗寨": "贵州", "镇远": "贵州",
    "青海湖": "青海", "茶卡盐湖": "青海", "东台吉乃尔湖": "青海", "塔尔寺": "青海",
    "沙湖": "宁夏", "沙坡头": "宁夏", "镇北堡": "宁夏",
    "布达拉宫": "西藏", "大昭寺": "西藏", "林芝": "西藏", "阿里": "西藏", "珠峰": "西藏",
    "洪崖洞": "重庆", "大足石刻": "重庆", "武隆": "重庆", "长江三峡": "重庆",
    "天津之眼": "天津", "盘山": "天津",
    "东方明珠": "上海", "外滩": "上海", "迪士尼": "上海",
    "故宫": "北京", "八达岭长城": "北京", "颐和园": "北京", "天坛": "北京", "香山": "北京",
    "禾木村": "新疆", "肇兴侗寨": "贵州", "三星堆": "四川",
    "维多利亚港": "香港", "大三巴牌坊": "澳门", "日月潭": "台湾", "阿里山": "台湾",
}

NAME_PROVINCE_KEYS = sorted(NAME_PROVINCE, key=len, reverse=True)


def province_of(name: str, address: str = "", hinted: str = "") -> str:
    if name in NAME_PROVINCE:  # 先精确命中，避免「华山」被「九华山」吞掉
        return NAME_PROVINCE[name]
    for key in NAME_PROVINCE_KEYS:
        if len(key) >= 2 and key in name:
            return NAME_PROVINCE[key]
    if hinted:
        for prov in PROVINCES:
            if hinted.startswith(prov) or prov in hinted:
                return prov
    for prov in PROVINCES:
        if address.startswith(prov + "省") or address.startswith(prov) or f"{prov}市" in address:
            return prov
    for city, prov in CITY_HINTS.items():
        if city in address:
            return prov
    for prov in PROVINCES:
        if name.startswith(prov):
            return prov
    return ""


def city_of(address: str, province: str) -> str:
    """从地址里取地级市（有地址才有值；没有就留空，不猜）。"""
    if province in {"北京", "上海", "天津", "重庆", "香港", "澳门"}:
        return province  # 直辖市/特区没有地级市这一层
    if not address:
        return ""
    rest = address
    if province and rest.startswith(province):
        rest = rest[len(province):]
    rest = re.sub(r"^(省|市|自治区|特别行政区|壮族自治区|回族自治区|维吾尔自治区)+", "", rest)
    match = re.match(r"([\u4e00-\u9fa5]{2,10}?(?:市|自治州|州|盟|地区|县|区))", rest)
    return match.group(1) if match else ""


def type_of(name: str) -> str:
    # 先看「山/峰/岭」后缀，避免「青岛崂山」被「岛」抢走、「丹霞山」被「丹霞」抢走
    if re.search(r"(山|峰|岭)$", name) and "火山" not in name:
        return "山岳"
    for label, keys in TYPE_RULES:
        if any(key in name for key in keys):
            return label
    return "综合"


def tags_of(name: str, text: str) -> list[str]:
    tags = [tag for tag, keys in TAG_RULES.items() if any(k in name or k in text for k in keys)]
    return tags[:4]


def clean_intro(text: str) -> str:
    """去掉榜单页的尾巴（发布时间/阅读量/平台声明）与外语括注，最多留三句。"""
    text = re.sub(r"（[^）]{0,80}(語|语|轉寫|转写|罗马字|拼音)[^）]*）", "", text)
    text = re.sub(r"\([^)]{0,60}(language|translit)[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}发布.*$", "", text)
    text = re.sub(r"阅读量[^。]*。?$", "", text)
    text = re.sub(r"(点击|返回搜狐|平台声明|声明：).*$", "", text)
    parts = re.split(r"(?<=[。！？])", text)
    return "".join(parts[:3])[:260].strip()


def norm_key(name: str) -> str:
    return re.sub(r"[·\s\-—－()（）]|景区|风景区|风景名胜区|旅游区|旅游度假区|古镇|古城|博物馆|博物院", "", name)


def apply_curated(records: list[dict]) -> tuple[int, int]:
    """把用户提供的外部名单（curated.jsonl）并进来。

    规则：名单里的名字按 name 或 alias 精确匹配（不做模糊匹配，避免「北京」吃掉「北京环球影城」）；
    命中就补 highlight（核心亮点）并登记 alias，没命中就新增一条（介绍留空，等 --enrich 补）。
    """
    if not CURATED.is_file():
        return 0, 0
    index: dict[str, dict] = {}
    for record in records:
        for name in [record["name"]] + record["aliases"]:
            index.setdefault(norm_key(name), record)
    added = filled = 0
    for line in CURATED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        record = index.get(norm_key(item["name"]))
        if record is None:
            record = {
                "name": item["name"], "aliases": [], "province": item.get("province", ""),
                "city": "", "type": item.get("type") or type_of(item["name"]),
                "tags": tags_of(item["name"], item.get("highlight", "")),
                "intro": "", "highlight": item.get("highlight", ""),
                "highlightSource": item.get("source", ""),
                "sources": [{"title": item.get("source", "外部名单"), "url": ""}],
            }
            records.append(record)
            index[norm_key(record["name"])] = record
            added += 1
        else:
            if item.get("highlight") and not record.get("highlight"):
                record["highlight"] = item["highlight"]
                record["highlightSource"] = item.get("source", "")
                filled += 1
            if item.get("province") and not record.get("province"):
                record["province"] = item["province"]
        # 名单里的写法与库内规范名不同（如「黄山风景区」对「黄山」），一律登记成别名
        for alias in {item.get("alias"), item["name"]}:
            if alias and alias != record["name"] and alias not in record["aliases"]:
                record["aliases"].append(alias)
                index.setdefault(norm_key(alias), record)
    return added, filled


def main() -> int:
    parser = argparse.ArgumentParser(description="构建景点知识库")
    parser.add_argument("--offline", action="store_true", help="只用本地缓存")
    parser.add_argument("--enrich", action="store_true", help="用维基百科补缺失介绍")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "attractions.jsonl"

    # 上一版里由维基补出来的介绍是「增量资产」，重建时不能丢（否则每次都要重新联网）
    previous: dict[str, dict] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            old = json.loads(line)
            previous[norm_key(old["name"])] = old
            previous.setdefault(norm_key(canonical_name(old["name"])[0]), old)

    collected: dict[str, dict] = {}
    used_sources: list[dict] = []
    for source in SOURCES:
        html = fetch(source["url"], source["id"], args.offline)
        if not html:
            continue
        lines = html_to_lines(html)
        if source["kind"] == "numbered":
            parsed = parse_numbered(lines)
        elif source["kind"] == "province":
            parsed = parse_province(lines)
        else:
            parsed = parse_table_html(html)
        kept = 0
        for item in parsed:
            prov_hint, raw_name = split_province(item["raw"])
            name, alias_name = canonical_name(raw_name)
            if not name or len(name) < 2:
                continue
            key = norm_key(name)
            body = "".join(item["body"]).strip()
            province = province_of(name, item.get("address", ""), prov_hint or item.get("province", ""))
            city = city_of(item.get("address", ""), province)
            record = collected.setdefault(key, {
                "name": name, "aliases": [], "province": province, "city": city,
                "type": TYPE_OVERRIDE.get(name) or type_of(name), "tags": tags_of(name, body),
                "intro": "", "sources": [],
            })
            if alias_name and alias_name != name and alias_name not in record["aliases"]:
                record["aliases"].append(alias_name)
            if city and not record["city"]:
                record["city"] = city
            if body and len(body) > len(record["intro"]):
                record["intro"] = body
            if province and not record["province"]:
                record["province"] = province
            if source["url"] not in [s["url"] for s in record["sources"]]:
                record["sources"].append({"title": source["title"], "url": source["url"]})
            if item.get("address") and not record.get("address"):
                record["address"] = item["address"]
            kept += 1
        print(f"  {source['id']}: 解析 {len(parsed)} 条，入库 {kept}", file=sys.stderr)
        used_sources.append({**source, "parsed": len(parsed)})

    # 去重 + 清洗介绍
    records: list[dict] = []
    for key, record in collected.items():
        record["intro"] = clean_intro(record["intro"])
        record["tags"] = tags_of(record["name"], record["intro"])
        record["_key"] = key
        records.append(record)

    # 「长白山」与「长白山天池」这类前缀包含关系：合并成一条，短名保留、长名进 aliases
    absorbed: set[str] = set()
    by_key = {r["_key"]: r for r in records}
    for short_key in sorted(by_key):
        if short_key in absorbed:
            continue
        for long_key in sorted(by_key):
            if long_key == short_key or long_key in absorbed:
                continue
            if (long_key.startswith(short_key) and len(long_key) - len(short_key) <= 3
                    and by_key[short_key]["province"] == by_key[long_key]["province"]):
                keep, drop = by_key[short_key], by_key[long_key]
                if len(drop["intro"]) > len(keep["intro"]):
                    keep["intro"] = drop["intro"]
                    keep["introSource"] = drop.get("introSource", keep.get("introSource"))
                if drop["name"] not in keep["aliases"]:
                    keep["aliases"].append(drop["name"])
                keep["aliases"].extend(a for a in drop["aliases"] if a not in keep["aliases"])
                for src in drop["sources"]:
                    if src not in keep["sources"]:
                        keep["sources"].append(src)
                absorbed.add(long_key)
    records = [r for r in records if r["_key"] not in absorbed]
    for record in records:
        record.pop("_key", None)
    records.sort(key=lambda r: (r["province"] or "zz", r["type"], r["name"]))

    added, filled = apply_curated(records)
    if added or filled:
        print(f"  外部名单：新增 {added} 条、补核心亮点 {filled} 条", file=sys.stderr)
        records.sort(key=lambda r: (r["province"] or "zz", r["type"], r["name"]))

    merged = 0
    for record in records:
        if len(record["intro"]) >= 20:
            continue
        old = previous.get(norm_key(record["name"]))
        if not (old and old.get("introSource") == "zh.wikipedia" and len(old.get("intro") or "") >= 20):
            continue
        # 上一版可能补错了页面（如「阿尔山柴河」拿到「柴河」），沿用前先核对标题
        wiki_title = next((wiki_title_from_url(s["url"]) for s in old.get("sources") or []
                           if "wikipedia.org" in s["url"]), "")
        if wiki_title and not wiki_title_ok(record["name"], wiki_title):
            print(f"  丢弃错配的维基介绍：{record['name']} ← {wiki_title}", file=sys.stderr)
            continue
        reused = clean_intro(old["intro"])
        if DISAMBIG.match(reused) or is_creative_work(reused) or intro_conflicts(reused, record["province"]):
            print(f"  丢弃错配的维基介绍：{record['name']} ← {wiki_title}（消歧义/省份冲突）",
                  file=sys.stderr)
            continue
        record["intro"] = reused
        record["introSource"] = "zh.wikipedia"
        for src in (old.get("sources") or [])[:2]:
            if src not in record["sources"]:
                record["sources"].append(src)
        merged += 1
    if merged:
        print(f"  沿用上一版维基介绍 {merged} 条", file=sys.stderr)

    missing = [r for r in records if len(r["intro"]) < 20]
    if args.enrich and missing:
        print(f"  用维基百科补 {len(missing)} 条介绍…", file=sys.stderr)
        filled = 0
        for record in missing:
            found = wiki_intro(record["name"], record["province"])
            if found:
                intro, title, url = found
                record["intro"] = clean_intro(intro)
                record["introSource"] = "zh.wikipedia"
                record["sources"].append({"title": f"维基百科 · {title}", "url": url})
                filled += 1
            time.sleep(0.4)
        print(f"  维基补全 {filled}/{len(missing)} 条", file=sys.stderr)

    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    with_intro = sum(1 for r in records if len(r["intro"]) >= 20)
    print(f"\n入库 {len(records)} 个景点，其中 {with_intro} 条有介绍；"
          f"分布：" + "、".join(f"{p}{sum(1 for r in records if r['province'] == p)}"
                              for p in PROVINCES if any(r["province"] == p for r in records))[:400],
          file=sys.stderr)
    (OUT_DIR / "sources.md").write_text(
        "# 景点库来源\n\n"
        f"生成时间：{date.today().isoformat()}　记录数：{len(records)}　有介绍：{with_intro}\n\n"
        "| 来源 | 链接 | 解析条数 |\n|---|---|---|\n" +
        "".join(f"| {s['title']} | {s['url']} | {s.get('parsed', '—')} |\n" for s in used_sources) +
        "\n已实测**不可用**，不要重试：知乎专栏（403）、百度百科（反爬挑战页）、今日头条（正文需 JS）。\n"
        "\n介绍字段为「从公开榜单提炼的客观描述」，不含原文修辞；每条都带来源链接，"
        "写报告时仍需按 SKILL 用官方公告复核门票与开放时间。\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
