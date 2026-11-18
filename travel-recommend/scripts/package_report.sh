#!/usr/bin/env bash
# package_report.sh — 把报告目录打成 zip，保留顶层文件夹（解压后不散落）。
#
# 用法：bash package_report.sh <report-dir> [out.zip]
# 依赖：zip / 7z / Windows PowerShell 任一。

set -euo pipefail
HERE="$(dirname "${BASH_SOURCE[0]}")"
HERE="${HERE//\\//}"
source "$HERE/lib.sh"

DIR="${1:?用法: package_report.sh <report-dir> [out.zip]}"
[ -d "$DIR" ] || die "目录不存在: $DIR"

ABS_DIR="$(cd "$(dirname "$DIR")" && pwd)/$(basename "$DIR")"
ABS_DIR="${ABS_DIR//\\//}"
NAME="$(basename "$ABS_DIR")"
OUT="${2:-$NAME.zip}"
case "$OUT" in
  /*|[A-Za-z]:[/\\]*) : ;;
  *) OUT="$(pwd)/$OUT" ;;
esac
OUT="${OUT//\\//}"

# 先自检，避免把缺图的包发出去
if [ "${SKIP_VERIFY:-0}" != "1" ]; then
  info "运行自检…"
  if have node; then node "$HERE/verify_report.mjs" "$ABS_DIR" >/dev/null || die "自检未通过，已中止打包（SKIP_VERIFY=1 可跳过）"
  elif have bun; then bun "$HERE/verify_report.mjs" "$ABS_DIR" >/dev/null || die "自检未通过，已中止打包（SKIP_VERIFY=1 可跳过）"
  fi
fi

info "打包 $NAME …"
if have zip; then
  (cd "$(dirname "$ABS_DIR")" && rm -f "$OUT" && zip -qr "$OUT" "$NAME")
elif have 7z; then
  (cd "$(dirname "$ABS_DIR")" && rm -f "$OUT" && 7z a -tzip "$OUT" "$NAME" >/dev/null)
elif have powershell.exe; then
  win_dir="$(cygpath -w "$(dirname "$ABS_DIR")" 2>/dev/null || printf '%s' "$(dirname "$ABS_DIR")")"
  win_out="$(cygpath -w "$OUT" 2>/dev/null || printf '%s' "$OUT")"
  powershell.exe -NoProfile -Command "Compress-Archive -Path '$win_dir\\$NAME' -DestinationPath '$win_out' -Force" >/dev/null
else
  die "没有 zip / 7z / PowerShell，无法打包"
fi

[ -f "$OUT" ] || die "打包失败：未生成 $OUT"

if have unzip; then
  tmp_list="$(mktemp)"
  unzip -l "$OUT" > "$tmp_list" 2>/dev/null || true
  entries="$(awk 'END{print $2}' "$tmp_list")"
  top="$(awk 'NR>3 && $4!="" {print $4; exit}' "$tmp_list")"
  rm -f "$tmp_list"
elif have 7z; then
  tmp_list="$(mktemp)"
  7z l "$OUT" > "$tmp_list" 2>/dev/null || true
  entries="$(awk '/files, / {print $3; exit}' "$tmp_list")"
  top="?"
  rm -f "$tmp_list"
else
  entries="?"
  top="?"
fi
[ -z "${entries:-}" ] && entries="?"
[ -z "${top:-}" ] && top="?"
size="$(du -h "$OUT" | awk '{print $1}')"
info "完成：$OUT（$size，$entries 个条目，顶层 $top）"
printf '%s\n' "$OUT"
