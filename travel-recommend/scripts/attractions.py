#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""查询景点知识库：按省份 / 类型 / 标签 / 关键词筛选，或给「去过某地」找同类替代。

为什么要有它：推荐不该由模型凭印象临时挑景点。先查库（确定性、可复现），
库里没有的再去联网补；用户说「去过 XX」时，用 --exclude 或 --similar 得到候选。

用法：
  uv run --no-project scripts/attractions.py                          # 统计概览
  uv run --no-project scripts/attractions.py --province 浙江 --type 山岳
  uv run --no-project scripts/attractions.py --tag 世界遗产 --tag 人文
  uv run --no-project scripts/attractions.py --keyword 湖 --limit 10
  uv run --no-project scripts/attractions.py --name 喀纳斯
  uv run --no-project scripts/attractions.py --exclude 丽江,平遥 --province 云南
  uv run --no-project scripts/attractions.py --similar 长白山           # 同省同类型替代
  uv run --no-project scripts/attractions.py --suggest 8                # 每个类型挑一个
  uv run --no-project scripts/attractions.py --missing-intro            # 还需要补介绍的条目
  uv run --no-project scripts/attractions.py --province 四川 --format json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "assets" / "attractions" / "attractions.jsonl"


def load() -> list[dict]:
    if not DATA.is_file():
        print(f"缺少数据文件：{DATA}\n先运行 build_attractions.py 生成。", file=sys.stderr)
        raise SystemExit(1)
    rows = []
    for line in DATA.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def names_of(record: dict) -> list[str]:
    return [record.get("name", "")] + list(record.get("aliases") or [])


def matched(record: dict, visited: list[str]) -> bool:
    for name in names_of(record):
        if not name:
            continue
        for item in visited:
            if item and (item in name or name in item):
                return True
    return False


def render(rows: list[dict], fmt: str, limit: int | None) -> None:
    if limit:
        rows = rows[:limit]
    if fmt == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if fmt == "markdown":
        print("| 景点 | 省份 | 类型 | 标签 | 介绍 |")
        print("|---|---|---|---|---|")
        for r in rows:
            intro = (r.get("intro") or "（待补）").replace("|", "／")
            print(f"| {r['name']} | {r.get('province') or '—'} | {r.get('type') or '—'} | "
                  f"{'、'.join(r.get('tags') or []) or '—'} | {intro[:80]} |")
        return
    for r in rows:
        intro = (r.get("intro") or "（待补介绍）")
        print(f"{r['name']}｜{r.get('province') or '—'}·{r.get('type') or '—'}"
              f"{('·' + '、'.join(r['tags'])) if r.get('tags') else ''}")
        print(f"  {intro[:120]}")
        if r.get("address"):
            print(f"  地址：{r['address']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="查询景点知识库")
    parser.add_argument("--province", action="append", default=[], help="省份，可多次")
    parser.add_argument("--type", action="append", default=[], help="类型，可多次")
    parser.add_argument("--tag", action="append", default=[], help="标签，可多次（同时满足）")
    parser.add_argument("--keyword", help="名称或介绍里的关键词")
    parser.add_argument("--name", help="按名称精确/包含匹配")
    parser.add_argument("--exclude", default="", help="去过的地方，逗号分隔，直接排除")
    parser.add_argument("--similar", help="给它找同省同类型的替代（自动排除它自己）")
    parser.add_argument("--suggest", type=int, help="每种类型挑 N 个，用于没有明确目标的场景")
    parser.add_argument("--missing-intro", action="store_true", help="列出还缺介绍的条目")
    parser.add_argument("--dup", action="store_true", help="检查疑似重复条目")
    parser.add_argument("--format", choices=["table", "json", "markdown"], default="table")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, help="--suggest 的随机种子，便于复现")
    args = parser.parse_args()

    rows = load()
    if not any([args.province, args.type, args.tag, args.keyword, args.name, args.exclude,
                args.similar, args.suggest, args.missing_intro, args.dup]):
        provinces = sorted({r["province"] for r in rows if r.get("province")})
        types = sorted({r["type"] for r in rows if r.get("type")})
        with_intro = sum(1 for r in rows if len(r.get("intro") or "") >= 20)
        print(f"景点库：{len(rows)} 条，{with_intro} 条有介绍；省份 {len(provinces)} 个，类型 {len(types)} 种")
        print("省份：" + "、".join(provinces))
        print("类型：" + "、".join(types))
        tags = sorted({t for r in rows for t in (r.get("tags") or [])})
        print("标签：" + "、".join(tags))
        print(f"\n数据文件：{DATA}")
        return 0

    if args.missing_intro:
        todo = [r for r in rows if len(r.get("intro") or "") < 20]
        render(todo, args.format, args.limit)
        print(f"\n共 {len(todo)} 条待补；用 build_attractions.py --enrich 自动补。", file=sys.stderr)
        return 0

    if args.dup:
        seen: dict[str, list[str]] = {}
        for r in rows:
            key = re.sub(r"[·\s\-—－()（）]|景区|风景区|古镇|古城", "", r["name"])
            seen.setdefault(key, []).append(r["name"])
        dups = {k: v for k, v in seen.items() if len(v) > 1}
        for key, names in dups.items():
            print(f"{key}: {' / '.join(names)}")
        print(f"\n疑似重复 {len(dups)} 组", file=sys.stderr)
        return 0

    visited = [item.strip() for item in args.exclude.split(",") if item.strip()]
    selected = rows
    if args.name:
        selected = [r for r in selected if any(args.name in n or n in args.name for n in names_of(r))]
    if args.similar:
        base = next((r for r in rows if any(args.similar in n or n in args.similar for n in names_of(r))), None)
        if not base:
            print(f"库里没有「{args.similar}」，先联网补资料，或用 --keyword 搜同类。", file=sys.stderr)
            return 1
        visited = visited + names_of(base)
        same_province_type = [r for r in rows if r is not base
                              and r.get("province") == base.get("province")
                              and r.get("type") == base.get("type")]
        if not same_province_type:  # 同省同类型没有 → 退到同省其它类型
            same_province_type = [r for r in rows if r is not base
                                  and r.get("province") == base.get("province")]
            print("（同省同类型没有其它候选，已放宽到同省其它类型）", file=sys.stderr)
        if not same_province_type:  # 同省都没有 → 退到全国同类，并提示跨省
            same_province_type = [r for r in rows if r is not base and r.get("type") == base.get("type")]
            print("（同省没有其它候选，已放宽到全国同类型）", file=sys.stderr)
        selected = same_province_type
    if args.province:
        selected = [r for r in selected if r.get("province") in args.province]
    if args.type:
        selected = [r for r in selected if r.get("type") in args.type]
    if args.tag:
        selected = [r for r in selected
                    if all(tag in (r.get("tags") or []) for tag in args.tag)]
    if args.keyword:
        selected = [r for r in selected
                    if args.keyword in r["name"] or args.keyword in (r.get("intro") or "")]
    if visited:
        selected = [r for r in selected if not matched(r, visited)]

    if args.suggest:
        rng = random.Random(args.seed)
        by_type: dict[str, list[dict]] = {}
        for r in selected:
            by_type.setdefault(r.get("type") or "综合", []).append(r)
        picked = []
        for group in by_type.values():
            rng.shuffle(group)
            picked.append(group[0])
        rng.shuffle(picked)
        selected = picked[:args.suggest]

    render(selected, args.format, args.limit)
    print(f"\n匹配 {len(selected)} 条" + (f"（已排除：{'、'.join(visited)}）" if visited else ""),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
