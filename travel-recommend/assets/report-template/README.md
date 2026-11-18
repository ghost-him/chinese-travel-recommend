# 报告模板（report-template）

这是 `travel-recommend` skill 自带的 HTML 报告模板，可直接双击 `index.html` 打开。
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
bash scripts/fetch_images.sh ./travel-report/images manifest.tsv
bash scripts/verify_report.sh ./travel-report
bash scripts/package_report.sh ./travel-report
```

## data.js 必填项

| 字段 | 说明 |
|---|---|
| `meta.title / subtitle / chips` | 页首标题、副标题、标签 |
| `meta.tripDays / tripStart / tripEnd` | 用来判断群的天数是否匹配 |
| `meta.fareQueriedAt / fareRefDate / source` | 票价时效三件套，页面会显示 |
| `meta.presale` | 未开售时的说明，三段：实测 / 结论 / 风险 |
| `clusters[]` | 风格互斥的地点群，**数量按实际成立情况定（不固定 5 个）**，含用户提过的全部候选；`style` 不能重复，`cities` 不能跨群重复，群内城市同省或相邻省 |
| `plans{}` | **每个群一份完整方案**（行程 / 景点 / 交通 / 费用）；key 随意，页面默认打开第一个 |
| `plans[].pois[].intro` | 60–150 字介绍，说明「是什么 / 为什么值得 / 看什么」 |
| `credits{}` | 每张图片的作者、许可、文件名 |

## 图片

- 每个景点下限 2 张、**越多越好、不设上限**；世遗/地标/5A 有几个角度就上几张。
- 文件名就是 `imgs` 里的 id；带扩展名（如 `kaiyuan-1.svg`）时按原样使用，不带则默认 `.jpg`。
- 模板里的 `placeholder-*.svg` 只用于占位，替换真实图片后删除。

## 两个保护

1. `meta.isTemplate: true` → 页面顶部显示红色横幅。
2. `verify_report.sh` → 输出「仍是模板占位数据」警告。

**对外分享前，必须把 `isTemplate` 改为 `false`。**

## 自检会拦住什么

- 景点少于 2 张图、缺介绍、缺门票/时长
- 图片文件不存在、未署名、重复图
- 群风格重复、同一城市出现在两个群
- `css` 里有外链资源（离线会挂）
- `data.js` 里仍有 TODO / 占位符

完整规则见上级目录的 `SKILL.md`。
