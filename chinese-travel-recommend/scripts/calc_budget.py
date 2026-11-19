#!/usr/bin/env -S uv run --no-project --script
"""命令行复算旅行预算，和页面计算器同一套公式。

用法：
  uv run --no-project scripts/calc_budget.py --rail 1500 --rail 925 \
       --label 上海 --label 广州 --stay 350 --nights 5 --rooms 1 --food 120 \
       --days 6 --local 30 --tickets 150 --exp 100 --group-transport 80 --buffer 10 \
       --mode per_person --cap 4000 --cap 3000

说明：
  --rail 可重复，人数 = len(--rail)；每个人的往返路费可以不同。
  --cap 可重复，顺序对应 --rail；per_person / uniform 用。
  --mode shared 时用 --total-cap；shared 只看所有人合计。
  住宿按「单价 × 晚数 × 间数 ÷ 人数」分摊；--people 可覆盖住宿分摊人数（默认 = 人数）。
  餐饮、市内交通、门票、体验、组合内城际交通等共同开销按统一标准计算，
  对应 SKILL 的「按消费能力最差者标准」。
"""

from __future__ import annotations

import argparse


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}¥{abs(round(value)):,}"


def main() -> None:
    parser = argparse.ArgumentParser(description="旅行预算复算（支持 N 人）")
    parser.add_argument("--rail", type=float, action="append", required=True,
                        help="每个人的往返大交通（仅出发地到组合开始位置），可重复")
    parser.add_argument("--label", action="append", default=[],
                        help="每个人的标签，可重复，顺序对应 --rail")
    parser.add_argument("--cap", type=float, action="append", default=[],
                        help="每个人的预算上限，可重复；per_person / uniform 用")
    parser.add_argument("--mode", choices=["shared", "per_person", "uniform"],
                        default="per_person", help="预算口径")
    parser.add_argument("--total-cap", type=float, help="shared 的总预算")
    parser.add_argument("--stay", type=float, default=0, help="住宿单价/晚")
    parser.add_argument("--nights", type=int, default=1)
    parser.add_argument("--rooms", type=int, default=1)
    parser.add_argument("--food", type=float, default=0, help="餐饮/人/天")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--local", type=float, default=0, help="市内交通/人/天")
    parser.add_argument("--tickets", type=float, default=0, help="门票/人")
    parser.add_argument("--exp", type=float, default=0, help="体验项目/人")
    parser.add_argument("--group-transport", type=float, default=0, help="组合内城际交通/人")
    parser.add_argument("--people", type=int, help="住宿分摊人数，默认 = --rail 的个数")
    parser.add_argument("--buffer", type=float, default=10, help="机动百分比")
    args = parser.parse_args()

    rails = [max(0.0, x) for x in args.rail]
    people = max(1, args.people if args.people else len(rails))
    labels = list(args.label)
    while len(labels) < len(rails):
        labels.append(f"同行者{len(labels) + 1}")
    labels = labels[:len(rails)]

    stay_share = args.stay * args.nights * args.rooms / people
    food_total = args.food * args.days
    local_total = args.local * args.days
    on_site = stay_share + food_total + local_total + args.tickets + args.exp + args.group_transport

    subs = [rail + on_site for rail in rails]
    bufs = [sub * args.buffer / 100 for sub in subs]
    totals = [sub + buf for sub, buf in zip(subs, bufs)]

    width = 14
    header = f"{'项目':<24}" + "".join(f"{label:>{width}}" for label in labels)
    print(header)
    print("-" * len(header))

    def row(label: str, values: list[float]) -> None:
        print(f"{label:<24}" + "".join(f"{money(v):>{width}}" for v in values))

    row("大交通（往返）", rails)
    row(f"住宿（{args.nights}晚×{args.rooms}间，分摊）", [stay_share] * len(rails))
    row(f"餐饮（{args.days}天）", [food_total] * len(rails))
    row(f"市内交通（{args.days}天）", [local_total] * len(rails))
    row("门票", [args.tickets] * len(rails))
    row("体验项目", [args.exp] * len(rails))
    row("组合内交通", [args.group_transport] * len(rails))
    row("小计", subs)
    row(f"机动 {args.buffer:g}%", bufs)
    row("每人合计", totals)
    print(f"{'所有人总支出':<24}{money(sum(totals)):>{width}}")

    if args.mode == "shared":
        if args.total_cap is None:
            print("\n[提示] shared 模式未给 --total-cap，无法判断是否超支。")
        else:
            diff = sum(totals) - args.total_cap
            state = f"在预算内，余 {money(-diff)}" if diff <= 0 else f"超出 {money(diff)}"
            print(f"\n共同预算 {money(args.total_cap)}：{state}。")
    else:
        caps = list(args.cap)
        while len(caps) < len(rails):
            caps.append(float("nan"))
        caps = caps[:len(rails)]
        if args.mode == "uniform":
            valid = [c for c in caps if c == c]
            if valid:
                high, low = max(valid), min(valid)
                print(f"\n统一上限取较高者 {money(high)}：")
                for label, total, cap in zip(labels, totals, caps):
                    if cap == cap:
                        diff = total - high
                        state = f"余 {money(-diff)}" if diff <= 0 else f"超出 {money(diff)}"
                        print(f"  {label}: {money(total)}，{state}")
                over_low = sum(max(0.0, total - low) for total in totals)
                print(f"  按较低上限 {money(low)} 合计超出 {money(over_low)}")
        else:
            print("\n各自上限：")
            for label, total, cap in zip(labels, totals, caps):
                if cap != cap:
                    print(f"  {label}: {money(total)}，未设上限")
                else:
                    diff = total - cap
                    state = f"在预算内，余 {money(-diff)}" if diff <= 0 else f"超出 {money(diff)}"
                    print(f"  {label}: {money(total)}，上限 {money(cap)}，{state}")
    print("\n说明：路费逐人不同；游玩、门票、市内与组合内交通按统一标准计算（对应最低消费能力者）。")


if __name__ == "__main__":
    main()
