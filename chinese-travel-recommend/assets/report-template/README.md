# 报告模板（report-template）

这是 `chinese-travel-recommend` skill 自带的 HTML 报告模板，可直接双击 `index.html` 打开。
**不要从零写页面，也不要依赖任何示例报告**——模板已包含全部前端代码。

```
report-template/
├─ index.html      结构（章节、锚点、灯箱容器）
├─ css/style.css   视觉系统（无外链字体、无 CDN、含打印样式）
├─ js/app.js       渲染：群评选 / 方案 tab / 行程 / 景点 / 费用计算器 / 灯箱
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
uv run --no-project scripts/package_report.py ./travel-report
```

## data.js 必填项

| 字段 | 说明 |
|---|---|
| `meta.title / subtitle / chips` | 页首标题、副标题、标签 |
| `meta.tripDays / tripStart / tripEnd` | 用来判断群的天数是否匹配 |
| `meta.budgetMode` | `shared` / `per_person` / `uniform`，多人预算口径 |
| `meta.mapMode` | `svg`（默认）或 `amap`；amap 必须填 `amapKey` |
| `meta.fareQueriedAt / fareRefDate / source` | 票价时效三件套，页面会显示 |
| `meta.presale` | 未开售时的说明，三段：实测 / 结论 / 风险 |
| `clusters[]` | 风格互斥的地点群，**数量按实际成立情况定（不固定 5 个）**，含用户提过的全部候选；`style` 不能重复，`cities` 不能跨群重复，群内城市同省或相邻省 |
| `plans{}` | **每个群一份完整方案**（行程 / 景点 / 交通 / 费用）；key 随意，页面默认打开第一个 |
| `plans[].pois[].intro` | 60–150 字介绍，说明「是什么 / 为什么值得 / 看什么」 |
| `plans[].pois[].status` | 每个景点必填：`open` / `off-season` / `closed` / `limited`；非 open 在卡片上出 badge |
| `plans[].pois[].statusNote` | `off-season` / `closed` 必填：原因与恢复时间 |
| `plans[].pois[].entry` | 每个景点必填：从哪个门进、哪个口近地铁/停车场 |
| `plans[].sources` | **必填**：`[{claim, source, date}]`，3–4 条覆盖关键结论（开放时间/预约/票价/限流）；为空则页面「本方案情报来源」整段不渲染 |
| `clusters[].seasonStatus / seasonNote` | 群级季节状态；`off`/`closed` 会在方案顶部出 alert |
| `credits{}` | 每张图片的作者、许可、文件名 |

## 图片

- 每个景点 4–6 张图、地标/世遗 6–10 张，**不设上限**；少于 4 张 `verify_report.py` 会警告。
- 文件名就是 `imgs` 里的 id；带扩展名（如 `kaiyuan-1.svg`）时按原样使用，不带则默认 `.jpg`。
- 模板里的 `placeholder-*.svg` 只用于占位，替换真实图片后删除。

## 两个保护

1. `meta.isTemplate: true` → 页面顶部显示红色横幅。
2. `verify_report.py` → 输出「仍是模板占位数据」警告。

**对外分享前，必须把 `isTemplate` 改为 `false`。**

## 自检会拦住什么

- 景点少于 2 张图、缺介绍、缺门票/时长
- 图片文件不存在、未署名、重复图
- 群风格重复、同一城市出现在两个群；群没有对应方案；方案对不上群
- 每个群缺 `seasonStatus`；`off` 没写原因；`closed` 群还留着方案
- 每个景点缺 `status` 或 `entry`；`off-season`/`closed` 缺 `statusNote`
- 方案缺 `geo.cities`，路线图无法显示
- `css` 里有外链资源（离线会挂）
- `data.js` 里仍有 TODO / 占位符

完整规则见上级目录的 `SKILL.md`。
