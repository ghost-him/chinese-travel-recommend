#!/usr/bin/env -S uv run --no-project --script
"""命令行复算旅行预算，和页面计算器同一套公式。

用法：
  uv run --no-project scripts/calc_budget.py --rail-a 1500 --rail-b 925 \
       --stay 350 --nights 5 --rooms 1 --food 120 --days 6 --local 30 \
       --tickets 150 --exp 100 --buffer 10 --people 2

说明：--rail-a/--rail-b 是两个人的往返大交通（单人价）；
      住宿按「单价 × 晚数 × 间数 ÷ 人数」分摊；机动按小计百分比追加。
"""

from __future__ import annotations

import argparse


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}¥{abs(round(value)):,}"


def main() -> None:
    parser = argparse.ArgumentParser(description="旅行预算复算")
    parser.add_argument("--rail-a", type=float, required=True, help="A 的往返大交通（单人）")
    parser.add_argument("--rail-b", type=float, help="B 的往返大交通（单人），默认同 A")
    parser.add_argument("--stay", type=float, default=0, help="住宿单价/晚")
    parser.add_argument("--nights", type=int, default=1)
    parser.add_argument("--rooms", type=int, default=1)
    parser.add_argument("--food", type=float, default=0, help="餐饮/人/天")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--local", type=float, default=0, help="市内交通/人/天")
    parser.add_argument("--tickets", type=float, default=0, help="门票/人")
    parser.add_argument("--exp", type=float, default=0, help="体验项目/人")
    parser.add_argument("--buffer", type=float, default=10, help="机动百分比")
    parser.add_argument("--people", type=int, default=2)
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    args = parser.parse_args()

    rail_b = args.rail_a if args.rail_b is None else args.rail_b
    people = max(1, args.people)
    stay_share = args.stay * args.nights * args.rooms / people
    food_total = args.food * args.days
    local_total = args.local * args.days

    sub_a = args.rail_a + stay_share + food_total + local_total + args.tickets + args.exp
    sub_b = rail_b + stay_share + food_total + local_total + args.tickets + args.exp
    buffer_a = sub_a * args.buffer / 100
    buffer_b = sub_b * args.buffer / 100

    rows = [
        ("大交通（往返）", args.rail_a, rail_b),
        (f"住宿（{args.nights}晚×{args.rooms}间，分摊）", stay_share, stay_share),
        (f"餐饮（{args.days}天）", food_total, food_total),
        (f"市内交通（{args.days}天）", local_total, local_total),
        ("门票", args.tickets, args.tickets),
        ("体验项目", args.exp, args.exp),
        ("小计", sub_a, sub_b),
        (f"机动 {args.buffer:g}%", buffer_a, buffer_b),
        ("人均合计", sub_a + buffer_a, sub_b + buffer_b),
    ]
    print(f"{'项目':<24}{args.label_a:>12}{args.label_b:>12}")
    for label, a, b in rows:
        print(f"{label:<24}{money(a):>12}{money(b):>12}")
    print(f"{'两人总支出':<24}{money(sub_a + buffer_a + sub_b + buffer_b):>12}")


if __name__ == "__main__":
    main()
