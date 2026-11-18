#!/usr/bin/env bash
# calc_budget.sh — 命令行复算旅行预算，和页面里的计算器同一套公式。
#
# 用法：
#   bash calc_budget.sh --rail-a 1011 --rail-b 753.5 --stay 420 --nights 3 --rooms 1 \
#        --food 130 --days 4 --local 35 --tickets 58 --exp 210 --buffer 10 --people 2
#
# 说明：--rail-a/--rail-b 是两个人的往返大交通（单人价）；
#       住宿按「单价 × 晚数 × 间数 ÷ 人数」分摊；机动按小计百分比追加。

set -euo pipefail
SELF="${BASH_SOURCE[0]}"

RAIL_A=""; RAIL_B=""; STAY=0; NIGHTS=1; ROOMS=1
FOOD=0; DAYS=1; LOCAL=0; TICKETS=0; EXP=0; BUFFER=10; PEOPLE=2
LABEL_A="A"; LABEL_B="B"

while [ $# -gt 0 ]; do
  case "$1" in
    --rail-a)  RAIL_A="$2"; shift 2 ;;
    --rail-b)  RAIL_B="$2"; shift 2 ;;
    --stay)    STAY="$2"; shift 2 ;;
    --nights)  NIGHTS="$2"; shift 2 ;;
    --rooms)   ROOMS="$2"; shift 2 ;;
    --food)    FOOD="$2"; shift 2 ;;
    --days)    DAYS="$2"; shift 2 ;;
    --local)   LOCAL="$2"; shift 2 ;;
    --tickets) TICKETS="$2"; shift 2 ;;
    --exp)     EXP="$2"; shift 2 ;;
    --buffer)  BUFFER="$2"; shift 2 ;;
    --people)  PEOPLE="$2"; shift 2 ;;
    --label-a) LABEL_A="$2"; shift 2 ;;
    --label-b) LABEL_B="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$SELF"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

[ -z "$RAIL_A" ] && { echo "必须给 --rail-a（A 往返大交通）" >&2; exit 2; }
[ -z "$RAIL_B" ] && RAIL_B="$RAIL_A"

awk -v railA="$RAIL_A" -v railB="$RAIL_B" -v stay="$STAY" -v nights="$NIGHTS" \
    -v rooms="$ROOMS" -v food="$FOOD" -v days="$DAYS" -v local="$LOCAL" \
    -v tickets="$TICKETS" -v exper="$EXP" -v buffer="$BUFFER" -v people="$PEOPLE" \
    -v la="$LABEL_A" -v lb="$LABEL_B" '
function money(x,   s, out, i, c) {
  s = sprintf("%.0f", (x < 0 ? -x : x))
  out = ""; c = 0
  for (i = length(s); i >= 1; i--) {
    out = substr(s, i, 1) out
    c++
    if (c % 3 == 0 && i > 1) out = "," out
  }
  return (x < 0 ? "-¥" : "¥") out
}
BEGIN {
  stayShare = stay * nights * rooms / people
  foodTotal = food * days
  localTotal = local * days
  subA = railA + stayShare + foodTotal + localTotal + tickets + exper
  subB = railB + stayShare + foodTotal + localTotal + tickets + exper
  bufA = subA * buffer / 100
  bufB = subB * buffer / 100

  printf "%-24s %12s %12s\n", "项目", la, lb
  printf "%-24s %12s %12s\n", "大交通（往返）", money(railA), money(railB)
  printf "%-24s %12s %12s\n", sprintf("住宿（%d晚×%d间，分摊）", nights, rooms), money(stayShare), money(stayShare)
  printf "%-24s %12s %12s\n", sprintf("餐饮（%d天）", days), money(foodTotal), money(foodTotal)
  printf "%-24s %12s %12s\n", sprintf("市内交通（%d天）", days), money(localTotal), money(localTotal)
  printf "%-24s %12s %12s\n", "门票", money(tickets), money(tickets)
  printf "%-24s %12s %12s\n", "体验项目", money(exper), money(exper)
  printf "%-24s %12s %12s\n", "小计", money(subA), money(subB)
  printf "%-24s %12s %12s\n", sprintf("机动 %g%%", buffer), money(bufA), money(bufB)
  printf "%-24s %12s %12s\n", "人均合计", money(subA + bufA), money(subB + bufB)
  printf "%-24s %12s\n", "两人总支出", money(subA + bufA + subB + bufB)
}' 
