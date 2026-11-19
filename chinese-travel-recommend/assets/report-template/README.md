# 报告模板（report-template）

这是 `chinese-travel-recommend` skill 自带的 HTML 报告模板，可直接双击 `index.html` 打开。
**不要从零写页面，也不要依赖任何示例报告**——模板已包含全部前端代码。

```
report-template/
├─ index.html      结构（章节、锚点、灯箱容器）
├─ css/style.css   视觉系统（无外链字体、无 CDN、含打印样式）
├─ js/app.js       渲染：地点评选 / 方案 tab / 行程 / 景点 / 费用计算器 / 灯箱
├─ js/data.js      ★ 唯一需要改的文件（当前是占位数据）
└─ images/         4 张 SVG 占位图，替换后删除
```

## 三步开箱

```bash
# 1. 复制到输出目录
cp -r assets/report-template ./travel-report

# 2. 改 data.js（先改 meta，再 clusters，最后 plans）
#    把 meta.isTemplate 改成 false

# 3. 抓图 + 自检 + 打包
uv run --no-project scripts/fetch_images.py ./travel-report/images manifest.tsv
uv run --no-project scripts/verify_report.py ./travel-report

# 3b. 自检/审核报出「图片少于目标」时：生成补抓清单 → 补抓 → 看图 → 写回 imgs
uv run --no-project scripts/verify_report.py ./travel-report --topup-tsv topup.tsv
uv run --no-project scripts/fetch_images_search.py ./travel-report/images topup.tsv --sources web,bing,commons

# 4. 复查通过后打包
uv run --no-project scripts/package_report.py ./travel-report
```

## data.js 必填项

| 字段 | 说明 |
|---|---|
| `meta.title / subtitle / chips` | 页首标题、副标题、标签 |
| `meta.tripDays / tripStart / tripEnd` | `tripDays` 由 `tripStart` / `tripEnd` 自动计算；用来判断群的天数是否匹配 |
| `meta.budgetMode` | `shared` / `per_person` / `uniform`，多人预算口径 |
| `meta.budgetCap / budgetCaps` | `shared` 用 `budgetCap`；`per_person` / `uniform` 用 `budgetCaps`（按人数逐人给） |
| `meta.mapMode` | `svg`（默认）或 `amap`；amap 必须填 `amapKey` |
| `meta.fareQueriedAt / fareRefDate / source` | 票价时效三件套，页面会显示 |
| `meta.presale` | 未开售时的说明，三段：实测 / 结论 / 风险 |
| `clusters[]` | 风格互斥的地点群，**数量按 `用户点名数 + max(3, 5 − 点名数)` 计算，且至少 5 个**；`name` 是页面展示名，写成「地点 · 一句话」，**不能以「群」结尾**；内部群名放 `internalName`；含用户提过的全部候选；`style` 不能重复，`cities` 不能跨群重复，群内城市同省或相邻省 |
| `clusters[].userConfirmedPlan / planRequest / visited` | 用户点名且闭园/已去过的二次确认结果：`planRequest` 为 `requested` / `declined` / `no_reply`；只有 `userConfirmedPlan: true` 才允许给 `closed` 群建方案 |
| `plans{}` | **每个推荐地点一份完整方案**（行程 / 景点 / 交通 / 费用）；用户明确不要方案的闭园/已去过候选除外；key 随意，页面默认打开第一个 |
| `plans[].costs.travelers[]` | 每个人的 `label` / `rail`（仅出发地到组合开始位置的往返路费，不含组合内交通）/ `tag`（`real` 或 `est`）/ 可选 `cap`；人数按用户给定，路费可以不同 |
| `plans[].costs` 共同开销 | `onSite = stayPerNight × nights × rooms ÷ 人数 + foodPerDay × days + localPerDay × days + tickets + experiences + groupTransport`；`total_i = (travelers[i].rail + onSite) × (1 + bufferPct/100)`；页面与 `calc_budget.py` 必须用同一条公式 |
| `plans[].pois[].intro` | 60–150 字介绍，说明「是什么 / 为什么值得 / 看什么」 |
| `plans[].pois[].status` | 每个景点必填：`open` / `off-season` / `closed` / `limited`；非 open 在卡片上出 badge |
| `plans[].pois[].statusNote` | `off-season` / `closed` 必填：原因与恢复时间 |
| `plans[].pois[].entry` | 每个景点必填：从哪个门进、哪个口近地铁/停车场 |
| `plans[].sources` | **必填**：`[{claim, source, date}]`，至少 3 条覆盖关键结论（开放时间/预约/票价/限流）；每条 `source` 写两个独立来源，用「 + 」连接；为空则页面「本方案情报来源」整段不渲染 |
| `clusters[].seasonStatus / seasonNote` | 地点级季节状态；`off`/`closed` 会在方案顶部出 alert；`closed` 有方案时必须 `userConfirmedPlan: true` |

## 图片

- 每个景点目标 4–6 张图、地标/世遗/5A 6–10 张，不设上限；**低于目标必须按 `--topup-tsv` 补抓，交付前补齐**；只有公开来源确实没有实景时，才允许保留实际张数并写清缺口、让用户确认（`imgs: []` + `noImageNote`，页面显示占位块）。
- 不需要署名：没有 `credits` 字段，图片直接用。
- 文件名就是 `imgs` 里的 id；带扩展名（如 `kaiyuan-1.svg`）时按原样使用，不带则默认 `.jpg`。
- 模板里的 `placeholder-*.svg` 只用于占位，替换真实图片后删除。

## 两个保护

1. `meta.isTemplate: true` → 页面顶部显示红色横幅。
2. `verify_report.py` → 输出「仍是模板占位数据」警告。

**交付前必须把 `isTemplate` 改为 `false`；带图片的报告不可公开发布。**

## 自检会拦住什么

- 景点缺介绍、缺门票/时长
- 图片文件不存在、重复图（同内容不同文件名）
- **同一张图被两个景点卡片引用**（同一个 `images/xxx` 出现在两个 `pois[].imgs` 里）——会直接判错，必须各点位用各自的实景图
- 群数少于 5；`clusters[].name` 以「群」结尾；风格重复、同一城市出现在两个群
- 地点没有对应方案（用户明确不要方案的 `closed` / 已去过候选除外）；方案对不上地点
- 每个群缺 `seasonStatus`；`off` 没写原因；`closed` 有方案但没有 `userConfirmedPlan: true`
- 每个景点缺 `status` 或 `entry`；`off-season`/`closed` 缺 `statusNote`
- 方案缺 `geo.cities`，路线图无法显示
- `css` 里有外链资源（离线会挂）
- `data.js` 里仍有 TODO / 占位符

完整规则见上级目录的 `SKILL.md`。
