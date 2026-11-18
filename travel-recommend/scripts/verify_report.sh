#!/usr/bin/env bash
# verify_report.sh — 报告包自检入口。有 node/bun 跑完整检查，没有则退化为基础检查。
#
# 用法：bash verify_report.sh <report-dir>

set -euo pipefail
HERE="$(dirname "${BASH_SOURCE[0]}")"
HERE="${HERE//\\//}"
source "$HERE/lib.sh"

DIR="${1:?用法: verify_report.sh <report-dir>}"
[ -d "$DIR" ] || die "目录不存在: $DIR"

if have node; then
  exec node "$HERE/verify_report.mjs" "$DIR"
elif have bun; then
  exec bun "$HERE/verify_report.mjs" "$DIR"
fi

info "未找到 node/bun，退化为基础检查（建议装 Node 以获得完整校验）"
fail=0
for f in index.html css/style.css js/data.js js/app.js images; do
  if [ -e "$DIR/$f" ]; then info "  ok   $f"; else info "  FAIL 缺 $f"; fail=1; fi
done

img_count=$(find "$DIR/images" -maxdepth 1 -type f \( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' \) 2>/dev/null | wc -l | tr -d ' ')
ref_count=$(grep -oE '"[a-z0-9-]+-[0-9]+"' "$DIR/js/data.js" | sort -u | wc -l | tr -d ' ')
credit_count=$(grep -cE '^\s*"[a-z0-9-]+[0-9a-z-]*":\s*\{' "$DIR/js/data.js" 2>/dev/null || echo 0)
info "  图片文件 $img_count 张，数据里引用 $ref_count 个 id，credits 条目约 $credit_count"

[ "$fail" -ne 0 ] && exit 1
info "基础检查通过"
