# chinese-travel-recommend

[English](README.md) · **简体中文**

把一个「放假去哪玩」的模糊念头，变成一份**能直接照着订票**的离线图文报告。

不是列十个网红城市，而是：问清条件 → 排除不可行的 → 按你的权重打分 → 只报实查价格 → 输出双击就能打开的 HTML 文件夹（行程、景点实景图、车次票价、费用表、路线地图）。

专为国内出行设计：懂 12306 预售期、懂节假日溢价，自带 163 条可查询的国内景点库。

- 版本：**1.8.3**｜许可：MIT
- 方法论在 [`chinese-travel-recommend/SKILL.md`](chinese-travel-recommend/SKILL.md)，本文只讲**怎么用、产出什么、边界在哪**

---

## 什么时候用它

| 你会这样说 | 它做什么 |
|---|---|
| 「国庆 5 天，从杭州出发，能去哪？」 | 按假期长度圈定半径，给出若干互斥的地点群 + 每个群的完整方案 |
| 「我和朋友从不同城市出发，去哪会合？」 | 先问预算怎么算：共同 / 各自 / 统一；不默认把某人的上限强加给其他人 |
| 「人均预算 4000，够去哪？」 | 先砍预算不可行的目的地；**你点名的地方不砍**，写清会超多少 |
| 「我们之前聊过想去敦煌」 | 敦煌必须进候选，并单独出一份完整方案 |
| 「这些地方我去过一半了」 | 深挖前先给你过目，确认去过/不想去的**整群换掉** |
| 「7 月想去哈尔滨」 | 过季节门槛；冰雪大世界非当季会显著提示，而不是硬排进行程 |

不适用的场景：只想要一张景点清单（太重）、已经在目的地只想排市内路线（用地图 App 更快）、需要代订票（本 skill 只查价不代购）。

---

## 一分钟上手

```text
用 chinese-travel-recommend 帮我规划：国庆 5 天，我从杭州东出发，朋友从广州南出发，人均 4000
```

Agent 会先问几轮（不是一次性甩 12 个问题）：

1. **第 0 问**：你们之前聊过想去哪？有没有备选？——有的话必须进候选；闭园或已去过的会再确认。
2. **5 个硬字段**：出发地（车站/机场）、同行者与各自出发地、出发日期、返程日期、人均预算上限；天数由日期自动算。
3. **预算口径**：共同总预算 / 各自上限 / 统一上限——每个人的距离和收入不同，不能默认按最差者算。
4. **地图模式**：离线 SVG（默认，双击即开）/ 高德 key（需联网，用户自己申请）。

问清后复述 7 项（含地图模式）给你确认，然后才开始干活。**缺任何一项都会停下来问，不会拿示例数据糊一份给你。**

环境要求：`uv` + Python 3.11+。脚本依赖写在 PEP 723 头里，`uv` 会自动安装，不需要 `pip install`，也不需要 Node / curl / jq。

---

## 流程

```mermaid
flowchart TD
  A[第 0 问<br/>有没有备选] --> B[5 个硬字段<br/>+ 预算口径 + 地图模式]
  B --> C[季节门槛<br/>反季 / 闭园先排除]
  C --> R[复述确认<br/>7 项含地图]
  R --> D[硬筛<br/>在途 / 预算 / 气候]
  D --> E[组群<br/>同省或相邻省]
  E --> F[子 agent 预审<br/>景点级：开放/入口/预约/季节]
  F --> G[候选回看<br/>确认去过/不想去 → 换；未回复 = 未确认]
  G --> H[按权重打分<br/>按预算口径算超支]
  H --> I[本地一手资料<br/>避坑 / 时段 / 老字号]
  I --> J[排行程 + 景点卡片]
  J --> K[12306 实查票价]
  K --> L[生成 HTML + 地图]
  L --> M[verify_report.py]
  M --> N[子 agent 终审]
  N --> O[打包 zip]
```

写死的几个硬步骤：

- **季节门槛**：每个群有 `seasonStatus`（ok/off/closed）；反季标 `off`；未点名的闭园淘汰，用户点名的闭园先二次确认，明确要方案才保留，否则只出原因卡。
- **预审**：提示词在 `chinese-travel-recommend/prompts/season-factcheck.md`，必须核到**每个景点**：当前是否开放、从哪个门进、停止入场时间、预约方式、季节错配。
- **候选回看**：先把群清单给你看，问「哪些去过、哪些不想去」。确认去过且不要方案的整群替换；未回复则保留并标「未确认」。
- **终审**：提示词在 `chinese-travel-recommend/prompts/final-review.md`，`FAIL` 必须修完再打包。

---

## 产出物

```
travel-report/
├─ index.html          # 双击就开，不联网（amap 模式除外）
├─ css/style.css
├─ js/data.js          # ★ 只有这个要改：画像 / 群 / 行程 / 票价
├─ js/app.js           # 渲染逻辑
├─ images/             # 实景图（每景点 4–6 张，地标 6–10 张），交付前补齐，不需要署名
└─ README.md           # 数据来源、假设清单、怎么改
```

报告里有什么：

- **地点群评分表**：7 个维度加权；标出季节状态、是否你点名、超预算多少
- **每个群一套完整方案**：逐日行程、景点卡片（介绍 + 门票 + 时长 + 开放时间 + **状态 + 入口** + 怎么去 + 一条实用提示）、往返车次与票价、费用计算器
- **景点级季节警示**：闭园/非当季的景点有 badge，方案顶部有 alert；反季不会只藏在提示里
- **票价三件套**：查询时间 + 参考乘车日 + 「实查 / 估算」；未开售明确写「尚未开售」，不会伪装成「无车」
- **路线地图**：默认按真实经纬度投影的 SVG；有高德 key 可切在线地图，失败自动回退
- **费用计算器**：改人数 / 房价即时重算；按 `shared / per_person / uniform` 分别判断超支

---

## 目录

以下路径相对本 README 所在目录（skill 本体在 `chinese-travel-recommend/` 里）：

| 路径 | 作用 |
|---|---|
| `chinese-travel-recommend/SKILL.md` | 方法论：输入契约、季节门槛、组群、评分、票价纪律、验证清单、反模式 |
| `chinese-travel-recommend/prompts/season-factcheck.md` | 给用户看名单前的景点级事实核查提示词 |
| `chinese-travel-recommend/prompts/final-review.md` | 交付前的整体审核提示词 |
| `chinese-travel-recommend/assets/report-template/` | 报告模板，空数据也能打开；含 4 张 SVG 占位图 |
| `chinese-travel-recommend/assets/attractions/` | 景点库：163 条主库、外部名单、来源与字段说明 |
| `chinese-travel-recommend/scripts/` | Python 工具链（见下） |

### 脚本

| 脚本 | 作用 |
|---|---|
| `build_attractions.py` | 抓公开榜单 → 解析 → 去重 → 打标签 → 维基补介绍，生成景点库 |
| `attractions.py` | 查库：按省/类型/标签/关键词；排除去过、找同类替代；`--all --format compact` 输出整表 |
| `fetch_rail_fares.py` | 12306 车次 + 各席别实价（自动 cookie、核对实际上车站） |
| `fetch_images.py` | Commons 批量抓图；限速、重试、md5 去重 |
| `fetch_images_search.py` | 多源检索抓图（百度 / 必应 / Commons / Commons 分类 / Openverse / 维基条目首图），公开搜索引擎优先；不做题材判断，由 AI 逐张看图 |
| `fetch_geo.py` | 按名称查经纬度（维基坐标 + Wikidata 兜底） |
| `optimize_images.py` | 压图控体积，长边与质量可调 |
| `verify_report.py` | 静态自检：图片/重复图/外链/占位符/价格结构/季节与预算口径 |
| `package_report.py` | 先自检再打 zip，保留顶层目录 |
| `calc_budget.py` | 与页面同公式的预算复算 |
| `lib.py` | 公共函数（HTTP 会话、重试、md5） |

---

## 手动跑脚本

```bash
cd chinese-travel-recommend

# 车次票价（超出约 14 天预售期会提示「未开售」，不是「无车」）
uv run --no-project scripts/fetch_rail_fares.py 上海虹桥 黄山北 2026-11-25

# 抓图：清单每行 slug|Commons 文件名|宽度
uv run --no-project scripts/fetch_images.py ../travel-report/images manifest.tsv --sleep 4

# 增量补图（已有文件保留，编号续写）
uv run --no-project scripts/fetch_images_search.py ../travel-report/images more.tsv

# 景点库
uv run --no-project scripts/attractions.py --province 浙江 --type 山岳
uv run --no-project scripts/attractions.py --exclude 丽江,平遥 --province 云南
uv run --no-project scripts/attractions.py --all --format compact

# 自检 → 打包
uv run --no-project scripts/verify_report.py ../travel-report
uv run --no-project scripts/package_report.py ../travel-report out.zip
```

---

## 这份 skill 的取舍

| 它坚持 | 为什么 |
|---|---|
| 缺字段就问，不问清不产出 | 用示例数据填出来的方案，订票时全废 |
| 每个价格带查询时间与来源 | 「大概 500 块」是最没用的一句话 |
| 先问预算口径，不默认取最差者 | 每个人的距离和收入不同，某人的上限不该强加给其他人 |
| 先过季节门槛 | 夏天推冰雪大世界、雨季推峡谷，攻略写得再好也是错 |
| 景点级核验开放/入口/停止入场 | 「到了发现关门」「走错门多绕 1 小时」是最高频的踩坑 |
| 一个群内的城市同省或相邻省 | 跨半个中国拼出来的「群」，车上时间比玩的时间长 |
| 每个群都给完整方案 | 只给首选写详情，等于替用户做了选择 |
| 每景点 4–6 张图，地标 6–10 张 | 只放两张，读起来像目录不像报告 |
| 地图默认内嵌 SVG | 瓦片地图要联网或几十 MB；高德 key 作为可选增强 |

---

## 已知边界

- **SVG 地图是示意投影**，不是瓦片底图：能看清「谁在谁东北、几段路怎么连」，看不到街道。要真实底图用 `mapMode: "amap"` + 自己的 key，但需联网，且 `file://` 可能被 key 的域名白名单限制。
- **12306 预售期约 14 天**：远期价格取同车次最近可售日实价，报告写明参考乘车日；铁路票价通常稳定，开售后确认余票即可。机票/酒店/门票仍可能变动。
- **机票、住宿、部分门票是估算**：标 `estimated` 并给区间，不编造精确数字。
- **景点开放状态会临时变**：大风封天池、临时闭馆、索道检修都可能发生；报告给的是核对时点的状态，出发前再看一眼官方公告。
- **行程是骨架，不是精确到分钟的排程**：开放时间、交通、排队都会变；建议出行前在小红书、大众点评等平台再看近期笔记，二次核对。
- **单城深度游**：支持北京、西安、成都、杭州这类底蕴厚的城市，但 skill 的主场景仍是多个候选地点之间的比较，单城行程同样只能给大概。

---

## 用之前

报告是决策参考，不是预订承诺。票价、门票、开放时间都会变；下单前以官方渠道为准，尤其节假日。
