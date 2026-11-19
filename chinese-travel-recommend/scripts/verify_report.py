#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["json5>=0.9"]
# ///
"""静态自检一个旅行报告包。

用法：uv run --no-project scripts/verify_report.py <report-dir> [--topup-tsv <清单.tsv>]

检查：文件完整 / 数据可加载 / 图片存在 / 无孤儿图 / 无重复图 /
      同一张图不得被两个点位引用 / 无外链资源 / 无占位符 / 车次价格结构 / 季节与预算口径。
--topup-tsv：把「图片数量低于目标」的点位写成 fetch_images_search.py 可直接吃的清单
      （普通点位目标 4 张，世遗/5A/地标/博物馆/必看 目标 6 张）。
退出码：0 全过（可有 warning），1 有 error。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import json5

from lib import sha256_of

IMAGE_RE = re.compile(r"\.(jpe?g|png|webp|svg|avif)$", re.I)
PLACEHOLDERS = ("TODO", "FIXME", "lorem ipsum", "这里填")


def parse_js_object(text: str, marker: str = "window.TRIP") -> dict:
    """data.js 是 JS 对象字面量，用 json5 处理未加引号的 key、注释和尾逗号。"""
    match = re.search(rf"{re.escape(marker)}\s*=\s*(\{{.*\}})\s*;", text, re.S)
    if not match:
        raise ValueError("找不到 window.TRIP = { ... };")
    return json5.loads(match.group(1))


def stem(name: str) -> str:
    return IMAGE_RE.sub("", name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_dir", nargs="?", default=".")
    parser.add_argument("--topup-tsv", default="", help="把图片不足的点位写成补抓清单（TSV）")
    args = parser.parse_args()
    directory = Path(args.report_dir).resolve()

    errors: list[str] = []
    warns: list[str] = []
    oks: list[str] = []

    def err(message: str) -> None:
        errors.append(message)

    def warn(message: str) -> None:
        warns.append(message)

    def ok(message: str) -> None:
        oks.append(message)

    # 1. 文件结构
    for name in ("index.html", "css/style.css", "js/data.js", "js/app.js"):
        if (directory / name).is_file():
            ok(f"存在 {name}")
        else:
            err(f"缺少 {name}")
    if not (directory / "images").is_dir():
        err("缺少 images/ 目录")

    # 2. 数据加载
    trip: dict | None = None
    data_path = directory / "js/data.js"
    data_src = data_path.read_text(encoding="utf-8") if data_path.is_file() else ""
    try:
        trip = parse_js_object(data_src)
        ok(f"data.js 可加载：{len(trip.get('plans') or {})} 套方案")
    except Exception as exc:
        err(f"data.js 加载失败：{exc}")

    # 3. 元信息
    if trip:
        meta = trip.get("meta") or {}
        if meta.get("fareQueriedAt"):
            ok(f"票价查询时间：{meta['fareQueriedAt']}")
        else:
            err("meta.fareQueriedAt 缺失（必须标注票价查询时间）")
        if not meta.get("fareRefDate"):
            err("meta.fareRefDate 缺失（必须标注参考乘车日）")
        if not (meta.get("presale") or {}).get("observed"):
            warn("meta.presale 缺失：远期出行未说明预售期/价格可变")
        if not meta.get("source"):
            warn("meta.source 缺失：未写明票价来源")
        if meta.get("isTemplate"):
            warn("meta.isTemplate = true：仍是模板占位数据，交付前请替换")
        if meta.get("budgetMode") not in ("shared", "per_person", "uniform"):
            warn("meta.budgetMode 未记录：应写 shared / per_person / uniform")
        if meta.get("mapMode") == "amap" and not meta.get("amapKey"):
            warn("mapMode=amap 但没填 amapKey：会退回 SVG 地图")

        clusters = trip.get("clusters") or []
        if not clusters:
            warn("没有 clusters：仍是按城市推荐，未按「地点群」组群")
        else:
            picked = sum(1 for cluster in clusters if cluster.get("userPicked"))
            required = picked + max(3, 5 - picked)
            if len(clusters) < required:
                err(f"只有 {len(clusters)} 个地点群（用户点名 {picked} 个，按公式要求 ≥{required}，少于要求直接不合格）")
            styles: set[str] = set()
            cities: set[str] = set()
            for cluster in clusters:
                name = cluster.get("name", "?")
                if str(name).endswith("群"):
                    err(f"页面展示名「{name}」以「群」结尾；内部群名请放 internalName")
                if not cluster.get("style") or not cluster.get("link"):
                    err(f"群「{name}」缺风格标签或群内串联说明")
                style = cluster.get("style")
                if style in styles:
                    err(f"风格重复：{style}（同风格应合并成一个群，不能并列）")
                styles.add(style)
                for city in cluster.get("cities") or []:
                    if city in cities:
                        err(f"城市「{city}」出现在多个群里")
                    cities.add(city)
                if not cluster.get("seasonStatus"):
                    err(f"群「{name}」缺 seasonStatus（必须标 ok/off/closed）")
                elif cluster.get("seasonStatus") not in ("ok", "off", "closed"):
                    err(f"群「{name}」seasonStatus 非法：{cluster.get('seasonStatus')}")
                if cluster.get("seasonStatus") == "off" and not cluster.get("seasonNote"):
                    err(f"群「{name}」标了非当季但没写原因")
                if cluster.get("seasonStatus") == "closed" and not cluster.get("seasonNote"):
                    err(f"群「{name}」标了闭园/停运但没写恢复时间")
                if cluster.get("userPicked") and cluster.get("overBudget") is None:
                    warn(f"群「{name}」是用户提过的候选，但没有记录 overBudget（超预算金额）")
            ok(f"{len(clusters)} 个地点群 / {len(styles)} 种风格 / {len(cities)} 座城市")

        plans = trip.get("plans") or {}
        if not meta.get("isTemplate"):
            labels = {key: plan.get("clusterLabel", "") for key, plan in plans.items()}
            for cluster in clusters:
                name = cluster.get("name", "")
                matched = [key for key, label in labels.items() if label.startswith(name)]
                closed = cluster.get("seasonStatus") == "closed"
                visited = cluster.get("visited") is True
                confirmed = cluster.get("userConfirmedPlan") is True
                plan_request = cluster.get("planRequest")
                if plan_request not in (None, "requested", "declined", "no_reply"):
                    err(f"群「{name}」planRequest 非法：{plan_request}")
                if closed:
                    if matched and not confirmed:
                        err(f"群「{name}」标了闭园/停航，有方案但没有 userConfirmedPlan: true")
                    # closed + 无方案：允许，作为原因卡
                elif not matched:
                    err(f"群「{name}」没有对应的完整方案（plans 里缺 clusterLabel 以它开头的条目）")
                if plan_request == "declined" and matched and not visited:
                    err(f"群「{name}」planRequest=declined，却仍有方案；应只保留原因卡，或整群替换")
                if visited:
                    if plan_request == "declined":
                        err(f"群「{name}」已确认去过且不要方案，但仍在地点列表里；应整群替换并写入「已替你排除」")
                    if plan_request == "requested" and not confirmed:
                        err(f"群「{name}」visited + planRequest=requested，但没有 userConfirmedPlan: true")
                    if plan_request == "no_reply" and not matched:
                        err(f"群「{name}」visited 未确认（no_reply），但缺完整方案；应保留清单并出方案")
                    if plan_request is None:
                        warn(f"群「{name}」visited=true 但没有记录二次确认结果（planRequest）")
            for key, label in labels.items():
                if label and not any(label.startswith(cluster.get("name", "")) for cluster in clusters):
                    err(f"方案「{key}」的 clusterLabel「{label}」对不上任何地点群")
        for key, plan in plans.items():
            for poi in plan.get("pois") or []:
                name = poi.get("name")
                status = poi.get("status")
                if not status:
                    err(f"[{key}] 景点「{name}」缺 status（open/off-season/closed/limited）")
                elif status not in ("open", "off-season", "closed", "limited"):
                    err(f"[{key}] 景点「{name}」status 非法：{status}")
                if not poi.get("entry"):
                    err(f"[{key}] 景点「{name}」缺 entry（从哪个门进）")
                if status in ("off-season", "closed") and not poi.get("statusNote"):
                    err(f"[{key}] 景点「{name}」标了 {status} 但没写 statusNote")

        mode = meta.get("budgetMode")
        if mode == "shared" and plans and not meta.get("budgetCap"):
            err("budgetMode=shared 但没有 meta.budgetCap：无法判断共同预算")
        for key, plan in plans.items():
            costs = plan.get("costs") or {}
            travelers = costs.get("travelers") or []
            if not travelers:
                warn(f"[{key}] costs.travelers 为空：费用表无法按人计算")
            else:
                for idx, t in enumerate(travelers):
                    if t.get("rail") is None:
                        warn(f"[{key}] costs.travelers[{idx}] 缺 rail（出发地到组合开始位置的往返路费）")
                if mode in ("per_person", "uniform"):
                    meta_caps = meta.get("budgetCaps")
                    for idx, t in enumerate(travelers):
                        cap = t.get("cap")
                        if cap is None and isinstance(meta_caps, list) and idx < len(meta_caps):
                            cap = meta_caps[idx]
                        if cap is None:
                            err(f"[{key}] costs.travelers[{idx}] 缺 cap，且 meta.budgetCaps 未提供；{mode} 无法逐人判断超支")
            required_cost_fields = ("stayPerNight", "nights", "rooms", "foodPerDay", "days",
                                    "localPerDay", "groupTransport", "tickets", "experiences", "bufferPct")
            missing_cost = [field for field in required_cost_fields if costs.get(field) is None]
            if missing_cost:
                warn(f"[{key}] costs 缺字段：{', '.join(missing_cost)}；页面与 calc_budget.py 无法用同一公式复算")

        for key, plan in plans.items():
            if not ((plan.get("geo") or {}).get("cities")):
                err(f"[{key}] 没有 geo.cities，路线图无法显示")
            if meta.get("mapMode", "svg") == "svg":
                for poi in plan.get("pois") or []:
                    if not poi.get("geo"):
                        warn(f"[{key}] 景点「{poi.get('name')}」缺 geo，地图上不会有点位")

    # 4. 图片引用完整性
    image_dir = directory / "images"
    files = [path.name for path in image_dir.iterdir()] if image_dir.is_dir() else []
    files = [name for name in files if IMAGE_RE.search(name)]
    by_stem = {stem(name): name for name in files}

    if trip:
        referenced: set[str] = set()
        poi_count = 0
        img_owner: dict[str, str] = {}
        hero_of: dict[str, str] = {}
        gaps: list[tuple[str, str, int]] = []
        for key, plan in (trip.get("plans") or {}).items():
            if plan.get("hero"):
                referenced.add(plan["hero"])
                hero_of.setdefault(plan["hero"], key)
            for poi in plan.get("pois") or []:
                poi_count += 1
                imgs = poi.get("imgs") or []
                poi_tags = poi.get("tags") or []
                landmark = any(t in ("世遗", "5A", "地标", "博物馆", "必看") for t in poi_tags)
                target = 6 if landmark else 4
                if not imgs:
                    warn(f"[{key}] 景点「{poi.get('name')}」没有实景图：必须补抓；确实无公开来源时才保留占位说明并让用户确认")
                elif len(imgs) < target:
                    label = "，地标/世遗/5A 目标 6–10" if landmark else ""
                    warn(f"[{key}] 景点「{poi.get('name')}」只有 {len(imgs)} 张图（目标 {target} 张{label}；低于目标需补抓）")
                if len(imgs) < target:
                    slug = stem(imgs[0]).rsplit("-", 1)[0] if imgs else f"topup-{key}-{poi_count}"
                    gaps.append((slug, poi.get("name", ""), target - len(imgs)))
                if not poi.get("intro") or len(poi["intro"]) < 30:
                    err(f"[{key}] 景点「{poi.get('name')}」缺介绍或过短")
                if not poi.get("ticket") or not poi.get("dur"):
                    err(f"[{key}] 景点「{poi.get('name')}」缺门票或时长")
                if not poi.get("tip"):
                    warn(f"[{key}] 景点「{poi.get('name')}」没有提示")
                owner = f"{key}/{poi.get('name')}"
                seen_here: set[str] = set()
                for image_id in imgs:
                    if image_id in seen_here:
                        err(f"同一景点内重复引用图片：{owner} 的 images/{image_id} 出现两次")
                        continue
                    seen_here.add(image_id)
                    if image_id in img_owner:
                        err(f"图片跨点位复用：images/{image_id} 同时用于「{img_owner[image_id]}」与「{owner}」")
                    else:
                        img_owner[image_id] = owner
                        if image_id in hero_of:
                            warn(f"images/{image_id} 既是方案 hero 又出现在「{owner}」的图廊里（建议换一张）")
                referenced.update(imgs)
            for day in plan.get("days") or []:
                items = day.get("items") or []
                if len(items) > 3:
                    err(f"[{key}] 第 {day.get('n')} 天有 {len(items)} 个时间块（上限 3）")
                if day.get("n") == 1 and sum(1 for i in items if i.get("kind") == "sight") > 1:
                    warn(f"[{key}] 抵达日排了多个游览项：抵达日只留 1 个轻项目")
            for leg in ("out", "back"):
                for row in (plan.get("transport") or {}).get(leg) or []:
                    if not (row.get("price", 0) > 0):
                        err(f"[{key}/{leg}] {row.get('train')} 票价异常：{row.get('price')}")
                    if not row.get("train") or not row.get("route"):
                        err(f"[{key}/{leg}] 存在缺车次或区间的行")
            sources = plan.get("sources") or []
            if not sources:
                warn(f"[{key}] 没有 sources：页面「本方案情报来源」整段不会渲染")
            else:
                incomplete = [s for s in sources
                              if not all(s.get(field) for field in ("claim", "source", "date"))]
                if incomplete:
                    warn(f"[{key}] sources 有 {len(incomplete)} 条缺 claim/source/date")
                if len(sources) < 3:
                    warn(f"[{key}] sources 只有 {len(sources)} 条（建议 ≥3，覆盖预约/票价/限流）")
        ok(f"共 {poi_count} 个景点，引用 {len(referenced)} 张图")

        if args.topup_tsv:
            dest = Path(args.topup_tsv)
            body = "\n".join(f"{slug}|{name} 实景|{need}|1200" for slug, name, need in gaps)
            dest.write_text(
                "# 图片不足的点位：slug|检索词|要几张|最小宽度（fetch_images_search.py 可直接用）\n" + body + "\n",
                encoding="utf-8",
            )
            ok(f"补抓清单已写入 {dest}（{len(gaps)} 个点位，共缺 {sum(g[2] for g in gaps)} 张）")

        for image_id in referenced:
            if stem(image_id) not in by_stem:
                err(f"引用了不存在的图片：images/{image_id}")

        ref_stems = {stem(image_id) for image_id in referenced}
        orphans = [name for name in files if stem(name) not in ref_stems]
        if orphans:
            warn(f"有 {len(orphans)} 张未引用的图片：{', '.join(orphans)}")
        if files:
            ok(f"图片目录 {len(files)} 张（引用 {len(referenced)}）")

    # 5. 重复图
    hashes: dict[str, str] = {}
    for name in files:
        digest = sha256_of(str(image_dir / name))
        if digest in hashes:
            err(f"重复图片：{name} 与 {hashes[digest]} 内容相同")
        else:
            hashes[digest] = name
    ok("重复图检查完成")

    # 6. 外链资源（CSS 外链会直接导致离线打开失败）
    html = (directory / "index.html").read_text(encoding="utf-8") if (directory / "index.html").is_file() else ""
    css = (directory / "css/style.css").read_text(encoding="utf-8") if (directory / "css/style.css").is_file() else ""
    if trip:
        meta = trip.get("meta") or {}
        title_tag = re.search(r"<title>\s*(.*?)\s*</title>", html, re.S)
        if title_tag and meta.get("title") and meta["title"] not in title_tag.group(1):
            err(f"index.html <title> 与 meta.title 不一致：「{title_tag.group(1)}」")
        hero = re.search(r'id="hero-title"[^>]*>\s*(.*?)\s*<', html, re.S)
        if hero and meta.get("title") and meta["title"] not in hero.group(1):
            err(f"index.html 首屏标题与 meta.title 不一致：「{hero.group(1)}」")
        if meta.get("tripDays"):
            head = " ".join(filter(None, [
                title_tag.group(1) if title_tag else "",
                hero.group(1) if hero else "",
                (re.search(r'<meta name="description" content="([^"]*)"', html) or [None, ""])[1],
            ]))
            bad = sorted({n for n in re.findall(r"(\d+)\s*天", head) if abs(int(n) - meta["tripDays"]) >= 2})
            if bad:
                warn(f"标题/描述里出现与 tripDays={meta['tripDays']} 不符的天数：{', '.join(bad)} 天")
    external = re.findall(r"(?:src|href)\s*=\s*[\"'](https?://[^\"']+)[\"']", html)
    css_external = re.findall(r"url\(\s*[\"']?(https?://[^)\"']+)", css)
    if external:
        warn(f"index.html 引用了外链资源：{', '.join(external[:3])}")
    if css_external:
        err(f"css 引用了外链资源（离线会挂）：{', '.join(css_external[:3])}")
    if not external and not css_external:
        ok("无外链资源，可离线打开")

    # 7. 占位符
    found = [token for token in PLACEHOLDERS if token.lower() in data_src.lower()]
    if found:
        err(f"data.js 仍有占位符：{', '.join(found)}")
    else:
        ok("无占位符残留")

    # 8. 体积
    size = 0
    if directory.is_dir():
        for path in directory.rglob("*"):
            if path.is_file():
                size += path.stat().st_size
    ok(f"包体积约 {size / 1048576:.1f} MB，图片 {len(files)} 张")

    print("\n=== 结构检查 ===")
    for message in oks:
        print("  ok   " + message)
    if warns:
        print("\n=== 警告（不阻塞） ===")
        for message in warns:
            print("  warn " + message)
    if errors:
        print("\n=== 错误 ===")
        for message in errors:
            print("  FAIL " + message)
        print(f"\n结果：{len(errors)} 个错误，{len(warns)} 个警告")
        return 1
    print(f"\n结果：通过（{len(warns)} 个警告）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
