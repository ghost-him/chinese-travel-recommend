#!/usr/bin/env bash
# fetch_rail_fares.sh — 12306 车次与票价实查（只读，不登录、不下单）
#
# 用法：
#   bash fetch_rail_fares.sh 上海虹桥 泉州南 2026-11-25
#   bash fetch_rail_fares.sh 广州南 潮汕 2026-12-02 O     # 第 4 参数指定席别代码
#
# 依赖：curl、jq。Windows 的 schannel curl 需要绕过吊销检查，脚本会自动加参数。
# 输出：TSV，列为 车次 / 出发-到达 / 历时 / 二等座 / 一等座 / 商务座 / 无座
#
# 说明：12306 预售期约 15 天，超出窗口会返回空结果——这不是故障，而是「尚未开售」。
#       脚本会明确打印该状态，不要把空结果当成「无车」。

set -euo pipefail

FROM_NAME="${1:?用法: fetch_rail_fares.sh <出发站中文名> <到达站中文名> <YYYY-MM-DD> [席别]}"
TO_NAME="${2:?缺少到达站}"
TRAIN_DATE="${3:?缺少乘车日期，例如 2026-11-25}"
SEAT_FILTER="${4:-}"

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
REFERER="https://kyfw.12306.cn/otn/leftTicket/init"
TMP="./.fare-tmp.$$"
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

# Windows/schannel 需要关闭吊销检查；其他平台忽略该参数
CURL=(curl -sS -m 30 -A "$UA" -H "Referer: $REFERER")
if curl --help all 2>/dev/null | grep -q -- '--ssl-no-revoke'; then
  CURL+=(--ssl-no-revoke)
fi

# 先取一次 init，拿到会话 cookie；缺 cookie 时查询接口会返回空
"${CURL[@]}" -c "$TMP/ck.txt" -o "$TMP/init.html" "https://kyfw.12306.cn/otn/leftTicket/init" || true
CURL+=(-b "$TMP/ck.txt")

# 1. 站名 -> 电报码
"${CURL[@]}" -o "$TMP/stations.js" "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
code_of() {
  local name="$1"
  local code
  # 站点表格式：拼音码|中文名|电报码|...
  code="$(tr '@' '\n' < "$TMP/stations.js" | awk -F'|' -v n="$name" '$2==n {print $3; exit}')"
  if [ -z "$code" ]; then
    echo "找不到车站「$name」。可用近似名试：$(tr '@' '\n' < "$TMP/stations.js" | awk -F'|' -v n="$name" 'index($2,n) {print $2"("$3")"}' | head -5 | paste -sd' ' -)" >&2
    exit 2
  fi
  printf '%s' "$code"
}
FROM_CODE="$(code_of "$FROM_NAME")"
TO_CODE="$(code_of "$TO_NAME")"

# 2. 车次列表（先探一次，拿到当前有效的 query 端点）
"${CURL[@]}" -o "$TMP/probe.json" -G "https://kyfw.12306.cn/otn/leftTicket/query" \
  --data-urlencode "leftTicketDTO.train_date=$TRAIN_DATE" \
  --data-urlencode "leftTicketDTO.from_station=$FROM_CODE" \
  --data-urlencode "leftTicketDTO.to_station=$TO_CODE" \
  --data-urlencode "purpose_codes=ADULT" || true

ENDPOINT="$(jq -r '.c_url // empty' "$TMP/probe.json" 2>/dev/null || true)"
[ -z "$ENDPOINT" ] && ENDPOINT="leftTicket/queryG"

"${CURL[@]}" -o "$TMP/list.json" -G "https://kyfw.12306.cn/otn/$ENDPOINT" \
  --data-urlencode "leftTicketDTO.train_date=$TRAIN_DATE" \
  --data-urlencode "leftTicketDTO.from_station=$FROM_CODE" \
  --data-urlencode "leftTicketDTO.to_station=$TO_CODE" \
  --data-urlencode "purpose_codes=ADULT"

COUNT="$(jq -r '.data.result | length' "$TMP/list.json" 2>/dev/null || echo 0)"
if [ "${COUNT:-0}" = "0" ]; then
  echo "# $FROM_NAME -> $TO_NAME $TRAIN_DATE：无可售车次。" >&2
  echo "# 常见原因：超出 15 天预售期（尚未开售）、站名写法不符、或当日无直达。" >&2
  exit 3
fi

name_of() {
  local code="$1"
  tr '@' '\n' < "$TMP/stations.js" | awk -F'|' -v c="$code" '$3==c {print $2; exit}'
}

printf '车次\t出发站\t时刻\t历时\t二等座\t一等座\t商务座\t无座\n'

jq -r '.data.result[]' "$TMP/list.json" | awk -F'|' -v T="$TO_CODE" '$8==T' | while IFS='|' read -r -a f; do
  train="${f[3]}"
  from_tele="${f[6]}"
  dep="${f[8]}"; arr="${f[9]}"; dur="${f[10]}"
  train_no="${f[2]}"; from_no="${f[16]}"; to_no="${f[17]}"; seat_types="${f[35]}"
  [ -z "$train_no" ] && continue

  price_json="$("${CURL[@]}" -G "https://kyfw.12306.cn/otn/leftTicket/queryTicketPrice" \
    --data-urlencode "train_no=$train_no" \
    --data-urlencode "from_station_no=$from_no" \
    --data-urlencode "to_station_no=$to_no" \
    --data-urlencode "seat_types=$seat_types" \
    --data-urlencode "train_date=$TRAIN_DATE" 2>/dev/null || echo '{}')"

  pick() { printf '%s' "$price_json" | jq -r --arg k "$1" '.data[$k] // "—"' 2>/dev/null || printf '—'; }
  ze="$(pick O)"; zy="$(pick M)"; sw="$(pick A9)"; wz="$(pick WZ)"

  if [ -n "$SEAT_FILTER" ]; then
    case "$SEAT_FILTER" in
      O) [ "$ze" = "—" ] && continue ;;
      M) [ "$zy" = "—" ] && continue ;;
    esac
  fi

  printf '%s\t%s\t%s-%s\t%s\t%s\t%s\t%s\t%s\n' "$train" "$(name_of "$from_tele")" "$dep" "$arr" "$dur" "$ze" "$zy" "$sw" "$wz"
  sleep 0.3
done

echo "# 数据源：12306 leftTicket/query + queryTicketPrice｜查询时间：$(date '+%Y-%m-%d %H:%M')｜乘车日：$TRAIN_DATE" >&2
