#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""按名称查经纬度，输出可直接粘进 data.js 的坐标（构建期脚本，不影响离线报告）。

为什么不用 Nominatim：2026-11 实测本机 IP 被 openstreetmap 返回 403/429，
维基的 prop=coordinates 稳定且允许批量查询，所以以 zh.wikipedia 为主、
en.wikipedia 兜底，实在没有就手填（清单第三列）。

用法：
  uv run --no-project scripts/fetch_geo.py <清单.tsv> [--out geo.json] [--sleep 0.5]

清单每行（| 分隔）：
  泉州开元寺|开元寺 (泉州)
  秦始皇兵马俑|秦始皇兵马俑
  某野景点|不存在的条目|110.29,25.27        # 第三列 lng,lat 手填，跳过查询
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from lib import Client, info

UA = "TravelRecommendSkill/1.6 (offline report builder; contact: you@example.com)"
SITES = [
    ("https://zh.wikipedia.org/w/api.php", "zh"),
    ("https://en.wikipedia.org/w/api.php", "en"),
]


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def wikidata_lookup(client: Client, title: str) -> dict | None:
    """维基条目没有坐标时，走 Wikidata 实体 P625。"""
    try:
        found = client.get_json("https://www.wikidata.org/w/api.php", {
            "action": "wbsearchentities", "search": title, "language": "zh",
            "uselang": "zh", "limit": "5", "format": "json", "type": "item",
        }, headers={"User-Agent": UA})
    except Exception:
        return None
    ids = [row["id"] for row in (found.get("search") or []) if row.get("id")]
    if not ids:
        return None
    try:
        entities = client.get_json("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "ids": "|".join(ids[:5]),
            "props": "claims", "format": "json",
        }, headers={"User-Agent": UA})
    except Exception:
        return None
    for entity in ((entities.get("entities") or {})).values():
        claims = (entity.get("claims") or {}).get("P625") or []
        for claim in claims:
            value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
            if "latitude" in value and "longitude" in value:
                return {
                    "lat": round(float(value["latitude"]), 3),
                    "lng": round(float(value["longitude"]), 3),
                    "page": f"wikidata:{entity.get('id', '')}",
                    "lang": "wikidata",
                }
    return None


def lookup(client: Client, title: str) -> dict | None:
    want_cjk = has_cjk(title)
    for endpoint, lang in SITES:
        try:
            payload = client.get_json(endpoint, {
                "action": "query", "prop": "coordinates", "titles": title,
                "format": "json", "redirects": "1",
            }, headers={"User-Agent": UA})
        except Exception:
            continue
        for page in ((payload.get("query") or {}).get("pages") or {}).values():
            coords = page.get("coordinates") or []
            page_title = page.get("title", "")
            # 中文查询不接受纯拉丁标题（否则「南澳岛」会命中一场战役条目）
            if coords and not (want_cjk and not has_cjk(page_title)):
                return {
                    "lat": round(float(coords[0]["lat"]), 3),
                    "lng": round(float(coords[0]["lon"]), 3),
                    "page": page_title,
                    "lang": lang,
                }
    return wikidata_lookup(client, title)


def main() -> int:
    parser = argparse.ArgumentParser(description="查询维基坐标")
    parser.add_argument("manifest")
    parser.add_argument("--out", default="geo.json")
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    manifest = Path(args.manifest)
    if not manifest.is_file():
        info(f"清单不存在: {manifest}")
        return 1

    client = Client(user_agent=UA, timeout=30, retries=2)
    result: dict[str, dict] = {}
    missing: list[str] = []

    for raw in manifest.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [part.strip() for part in raw.split("|")]
        slug = parts[0]
        title = parts[1] if len(parts) > 1 and parts[1] else parts[0]
        if len(parts) > 2 and "," in parts[2]:
            lng, lat = (float(value) for value in parts[2].split(","))
            result[slug] = {"lat": round(lat, 3), "lng": round(lng, 3), "source": "manual"}
            print(f"  {slug:<30} {lat:.3f}, {lng:.3f}  (manual)")
            continue
        found = lookup(client, title)
        if not found:
            info(f"未找到 {slug}（{title}）：换个正式条目名，或用第三列手填 lng,lat")
            missing.append(slug)
            time.sleep(args.sleep)
            continue
        result[slug] = found
        print(f"  {slug:<30} {found['lat']:.3f}, {found['lng']:.3f}  [{found['lang']}] {found['page']}")
        time.sleep(args.sleep)

    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    info(f"\n写入 {args.out}：{len(result)} 个点位，缺 {len(missing)} 个")
    if missing:
        info("缺口：" + " ".join(missing))
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
