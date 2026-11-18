#!/usr/bin/env node
/**
 * verify_report.mjs — 静态自检一个旅行报告包。
 *
 * 用法：node verify_report.mjs <report-dir>     （或 bun verify_report.mjs ...）
 *
 * 检查：文件完整 / 数据可加载 / 每景点 ≥2 图 / 图片存在且已署名 / 无孤儿图 /
 *       无重复图 / 无外链资源 / 无占位符 / 车次价格结构完整 / 体积统计。
 * 退出码：0 全过（可有 warning），1 有 error。
 */
import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const dir = resolve(process.argv[2] || ".");
const errors = [];
const warns = [];
const oks = [];
const err = (m) => errors.push(m);
const warn = (m) => warns.push(m);
const ok = (m) => oks.push(m);

/* ---------- 1. 文件结构 ---------- */
const required = ["index.html", "css/style.css", "js/data.js", "js/app.js"];
for (const f of required) {
  if (existsSync(join(dir, f))) ok(`存在 ${f}`);
  else err(`缺少 ${f}`);
}
if (!existsSync(join(dir, "images"))) err("缺少 images/ 目录");

/* ---------- 2. 数据加载 ---------- */
let T = null;
try {
  globalThis.window = {};
  await import(pathToFileURL(join(dir, "js/data.js")).href);
  T = globalThis.window.TRIP;
  if (!T) err("data.js 未导出 window.TRIP");
  else ok(`data.js 可加载：${Object.keys(T.plans || {}).length} 套方案`);
} catch (e) {
  err(`data.js 加载失败：${e.message}`);
}

/* ---------- 3. 元信息 ---------- */
if (T) {
  const m = T.meta || {};
  if (!m.fareQueriedAt) err("meta.fareQueriedAt 缺失（必须标注票价查询时间）");
  else ok(`票价查询时间：${m.fareQueriedAt}`);
  if (!m.fareRefDate) err("meta.fareRefDate 缺失（必须标注参考乘车日）");
  if (!m.presale || !m.presale.observed) warn("meta.presale 缺失：远期出行未说明预售期/价格可变");
  if (!m.source) warn("meta.source 缺失：未写明票价来源");
  if (m.isTemplate) warn("meta.isTemplate = true：仍是模板占位数据，对外分享前请替换并把该字段改为 false");

  const clusters = T.clusters || [];
  if (!clusters.length) warn("没有 clusters：仍是按城市推荐，未按「地点群」组群");
  else {
    if (clusters.length < 5) warn(`只有 ${clusters.length} 个地点群（默认应为 5 个风格互斥的群）`);
    const styles = new Set();
    const cities = new Set();
    for (const c of clusters) {
      if (!c.style || !c.link) err(`群「${c.name}」缺风格标签或群内串联说明`);
      if (styles.has(c.style)) err(`风格重复：${c.style}（同风格应合并成一个群，不能并列）`);
      styles.add(c.style);
      for (const city of c.cities || []) {
        if (cities.has(city)) err(`城市「${city}」出现在多个群里（邻近同质应合并）`);
        cities.add(city);
      }
    }
    ok(`${clusters.length} 个地点群 / ${styles.size} 种风格 / ${cities.size} 座城市`);
  }
}

/* ---------- 4. 图片引用完整性 ---------- */
const imageDir = join(dir, "images");
const filesOnDisk = existsSync(imageDir)
  ? readdirSync(imageDir).filter((f) => /\.(jpe?g|png|webp|svg|avif)$/i.test(f))
  : [];
const stemOf = (f) => f.replace(/\.[^.]+$/, "");
const byStem = new Map(filesOnDisk.map((f) => [stemOf(f), f]));

if (T) {
  const referenced = new Set();
  let poiCount = 0;
  for (const [key, plan] of Object.entries(T.plans || {})) {
    if (plan.hero) referenced.add(plan.hero);
    for (const poi of plan.pois || []) {
      poiCount++;
      const imgs = poi.imgs || [];
      if (imgs.length < 2) err(`[${key}] 景点「${poi.name}」只有 ${imgs.length} 张图（底线 2 张，大景点应更多）`);
      if (!poi.intro || poi.intro.length < 30) err(`[${key}] 景点「${poi.name}」缺介绍或过短（需说明是什么/为什么值得/看什么）`);
      imgs.forEach((id) => referenced.add(id));
      if (!poi.ticket || !poi.dur) err(`[${key}] 景点「${poi.name}」缺门票或时长`);
      if (!poi.tip) warn(`[${key}] 景点「${poi.name}」没有提示（错峰/入口/排号等可执行细节）`);
    }
    for (const leg of ["out", "back"]) {
      for (const row of plan.transport?.[leg] || []) {
        if (!(row.price > 0)) err(`[${key}/${leg}] ${row.train} 票价异常：${row.price}`);
        if (!row.train || !row.route) err(`[${key}/${leg}] 存在缺车次或区间的行`);
      }
    }
  }
  ok(`共 ${poiCount} 个景点，引用 ${referenced.size} 张图`);

  for (const id of referenced) {
    if (!byStem.has(stemOf(id))) err(`引用了不存在的图片：images/${id}`);
    const c = (T.credits || {})[id];
    if (!c) err(`图片未署名：${id}`);
    else if (!c.author || !c.license || !c.file) err(`署名不完整：${id}`);
  }

  const refStems = new Set([...referenced].map(stemOf));
  const orphans = filesOnDisk.filter((f) => !refStems.has(stemOf(f)));
  if (orphans.length) warn(`有 ${orphans.length} 张未引用的图片：${orphans.join(", ")}`);
  if (orphans.length || referenced.size === 0) {
    const total = referenced.size + orphans.length;
    if (total > 0) ok(`图片目录 ${total} 张（引用 ${referenced.size}）`);
  }
}

/* ---------- 5. 重复图 ---------- */
const hashMap = new Map();
for (const f of filesOnDisk) {
  const p = join(imageDir, f);
  const h = createHash("sha256").update(readFileSync(p)).digest("hex");
  if (hashMap.has(h)) err(`重复图片：${f} 与 ${hashMap.get(h)} 内容相同`);
  else hashMap.set(h, f);
}
ok("重复图检查完成");

/* ---------- 6. 外链资源 ---------- */
const html = existsSync(join(dir, "index.html")) ? readFileSync(join(dir, "index.html"), "utf8") : "";
const css = existsSync(join(dir, "css/style.css")) ? readFileSync(join(dir, "css/style.css"), "utf8") : "";
const external = [
  ...html.matchAll(/(?:src|href)\s*=\s*["'](https?:\/\/[^"']+)["']/g)
].map((m) => m[1]);
const cssExternal = [...css.matchAll(/url\(\s*["']?(https?:\/\/[^)"']+)/g)].map((m) => m[1]);
if (external.length) warn(`index.html 引用了外链资源：${external.slice(0, 3).join(", ")}`);
if (cssExternal.length) err(`css 引用了外链资源（离线会挂）：${cssExternal.slice(0, 3).join(", ")}`);
if (!external.length && !cssExternal.length) ok("无外链资源，可离线打开");

/* ---------- 7. 占位符 ---------- */
const dataSrc = existsSync(join(dir, "js/data.js")) ? readFileSync(join(dir, "js/data.js"), "utf8") : "";
const placeholders = ["TODO", "FIXME", "lorem ipsum", "这里填"].filter((p) =>
  dataSrc.toLowerCase().includes(p.toLowerCase())
);
if (placeholders.length) err(`data.js 仍有占位符：${placeholders.join(", ")}`);
else ok("无占位符残留");

/* ---------- 8. 体积 ---------- */
function dirSize(p) {
  let s = 0;
  for (const e of readdirSync(p, { withFileTypes: true })) {
    const q = join(p, e.name);
    s += e.isDirectory() ? dirSize(q) : statSync(q).size;
  }
  return s;
}
const sizeMB = existsSync(dir) ? (dirSize(dir) / 1048576).toFixed(1) : "0";
ok(`包体积约 ${sizeMB} MB，图片 ${filesOnDisk.length} 张`);

/* ---------- 输出 ---------- */
console.log("\n=== 结构检查 ===");
oks.forEach((m) => console.log("  ok   " + m));
if (warns.length) {
  console.log("\n=== 警告（不阻塞） ===");
  warns.forEach((m) => console.log("  warn " + m));
}
if (errors.length) {
  console.log("\n=== 错误 ===");
  errors.forEach((m) => console.log("  FAIL " + m));
  console.log(`\n结果：${errors.length} 个错误，${warns.length} 个警告`);
  process.exit(1);
}
console.log(`\n结果：通过（${warns.length} 个警告）`);
