# 景点库（attractions）

一个可查询、可复现的中国景点池，用来避免「让模型凭印象临时挑景点」。

- 主库：`attractions.jsonl`，每行一个景点
- 来源与可用性：`sources.md`（由构建脚本自动生成）
- 缓存：`.cache/`（原始页面，便于离线重建；不进报告包）

## 字段

| 字段 | 说明 |
|---|---|
| `name` | 景点名（去掉了「景区/风景区/古镇」等后缀与标题里的省份前缀） |
| `aliases` | 别名（如「周庄古镇」→ 周庄），用于「用户说去过」时的匹配 |
| `province` / `city` | 省份（34 个省级单位）、城市；由地址或标题前缀推断 |
| `type` | 类型：山岳 / 湖泊 / 瀑布 / 草原 / 梯田 / 海岛 / 峡谷 / 溶洞 / 荒漠 / 冰川 / 石窟 / 园林 / 长城 / 古村镇 / 古建筑 / 寺庙宫观 / 博物馆 / 城市地标 / 红色/纪念 / 综合 |
| `tags` | 场景标签：秋色 / 冰雪 / 避寒 / 赏花 / 摄影 / 徒步 / 人文 / 亲子 / 自驾 |
| `intro` | 客观介绍：是什么、在哪、为什么值得看；几十到两百多字，长短取决于来源 |
| `introSource` | `zh.wikipedia` 表示介绍由维基百科补全（原榜单文章没有） |
| `sources[]` | 该条目的出处链接（榜单 / 维基条目） |
| `address` | 详细地址（有则填） |

## 怎么用

```bash
# 概览
uv run --no-project scripts/attractions.py

# 按省份 / 类型 / 标签筛选
uv run --no-project scripts/attractions.py --province 浙江 --type 山岳
uv run --no-project scripts/attractions.py --tag 摄影 --tag 秋色

# 用户说「去过丽江和平遥」→ 直接排除
uv run --no-project scripts/attractions.py --exclude 丽江,平遥 --province 云南

# 用户去过泸沽湖 → 找同省同类型的替代
uv run --no-project scripts/attractions.py --similar 泸沽湖

# 完全没有目标时：整表入上下文（154 行 ≈ 8.9k 字符），自己横向比
uv run --no-project scripts/attractions.py --all --format compact

# 只想每类抽一个做提示
uv run --no-project scripts/attractions.py --suggest 8 --seed 7
```

## 怎么更新

```bash
uv run --no-project scripts/build_attractions.py            # 优先用 .cache，缺了才联网
uv run --no-project scripts/build_attractions.py --offline   # 只读缓存，绝不联网
uv run --no-project scripts/build_attractions.py --enrich    # 额外用维基补缺失介绍（有标题校验，错配宁可留空）
uv run --no-project scripts/attractions.py --missing-intro    # 看还缺哪些介绍
```

新增来源：在 `build_attractions.py` 的 `SOURCES` 里加一条（`kind` 选 `numbered` / `province` / `table`），
先确认页面能直出正文；被反爬拦下的站点（知乎、百度百科、今日头条）不要加。

## 版权与准确性

- 介绍文字为**从公开榜单与维基百科提炼的客观描述**，不照搬原文修辞；每条都保留来源链接。
- 库只解决「有哪些地方、大概是什么」，**门票、开放时间、预约规则、限流**仍须按 SKILL 第 5 节实查官方公告。
- 引用本库内容时注明来源（`sources[]`），不要把榜单当官方公告。
