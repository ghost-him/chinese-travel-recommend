#!/usr/bin/env bash
# fetch_images.sh — 从 Wikimedia Commons 批量抓图，自动带署名与许可，去重、限速、重试。
#
# 用法：
#   bash fetch_images.sh <输出目录> <清单.tsv>
#
# 清单每行（用 | 分隔，可带 # 注释）：
#   kaiyuan-1|Kaiyuan Temple, Quanzhou 16.jpg
#   kaiyuan-2|File:The courtyard of Quanzhou Kaiyuan Temple 20170727.jpg
#   第三个字段可选：宽度（默认 1200）
#
# 产物：
#   <输出目录>/<slug>.jpg
#   <输出目录>/credits.jsonl          每行一条完整元数据
#   <输出目录>/credits.snippet.js     可直接粘进 data.js 的 credits 块
#   <输出目录>/manifest.json          本次抓取汇总
#
# 依赖：curl、jq。Commons 要求带可识别 UA，并且不要并发轰炸（本脚本串行 + 4s 间隔）。

set -euo pipefail
# 注意：不要用 `cd ... && pwd` 取脚本目录——Windows 的 bash 会返回 C:\...\ 反斜杠路径，
# 拼成 "$HERE/lib.sh" 后 source 会失败。直接用 dirname 的相对/正斜杠形式。
HERE="$(dirname "${BASH_SOURCE[0]}")"
HERE="${HERE//\\//}"
source "$HERE/lib.sh"

OUT="${1:?用法: fetch_images.sh <输出目录> <清单.tsv>}"
# Commons 对同一 IP 的抓取很敏感：命中限流后连续请求会一直拿到 60 字节的提示页。
# 补图时用 SLEEP=45 或更大值放慢节奏即可恢复。
SLEEP="${SLEEP:-6}"
MANIFEST="${2:?缺少清单文件}"
[ -f "$MANIFEST" ] || die "清单不存在: $MANIFEST"
have curl || die "需要 curl"
have jq || die "需要 jq"

mkdir -p "$OUT"
curl_init

: > "$OUT/credits.jsonl"
printf '{\n' > "$OUT/credits.snippet.js"

seen_md5_file="$OUT/.seen-md5"
: > "$seen_md5_file"

total=0; ok=0; failed=0
failed_list=""

while IFS='|' read -r slug title width || [ -n "${slug:-}" ]; do
  slug="$(printf '%s' "${slug:-}" | tr -d '[:space:]')"
  [ -z "$slug" ] && continue
  case "$slug" in \#*) continue ;; esac
  title="$(printf '%s' "${title:-}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^File://')"
  width="${width:-1200}"
  width="$(printf '%s' "$width" | tr -d '[:space:]')"
  [ -z "$title" ] && { info "跳过 $slug：缺文件名"; continue; }

  total=$((total + 1))
  meta="$OUT/.meta-$slug.json"

  fetch_meta() {
    "${CURL[@]}" -G "https://commons.wikimedia.org/w/api.php" \
      --data-urlencode "action=query" \
      --data-urlencode "titles=File:$title" \
      --data-urlencode "prop=imageinfo" \
      --data-urlencode "iiprop=url|extmetadata" \
      --data-urlencode "iiurlwidth=$width" \
      --data-urlencode "format=json" \
      -o "$meta" && jq -e '.query.pages' "$meta" >/dev/null 2>&1
  }

  if ! retry 3 8 fetch_meta; then
    info "失败 $slug：API 取不到（可能是 429 限流或文件名不对）"
    failed=$((failed + 1)); failed_list="$failed_list $slug"
    sleep "$SLEEP"
    continue
  fi

  url="$(jq -r '.query.pages[].imageinfo[0].thumburl // empty' "$meta")"
  if [ -z "$url" ]; then
    if jq -e '.query.pages[] | select(.missing)' "$meta" >/dev/null 2>&1; then
      info "失败 $slug：Commons 上没有这个文件（检查文件名与大小写）"
    else
      info "失败 $slug：无缩略图 URL"
    fi
    failed=$((failed + 1)); failed_list="$failed_list $slug"; continue
  fi

  author="$(jq -r '.query.pages[].imageinfo[0].extmetadata.Artist.value // "Unknown"' "$meta" | sed -e 's/<[^>]*>//g' | tr -d '\n' | sed -e 's/[[:space:]]\+/ /g' -e 's/^User://' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  license="$(jq -r '.query.pages[].imageinfo[0].extmetadata.LicenseShortName.value // "Unknown"' "$meta")"
  out="$OUT/$slug.jpg"

  # upload.wikimedia.org 会把「非浏览器 UA」直接回成 200 + 60 字节的 robot policy 页面
  # （API 不拦），所以媒体下载单独用浏览器 UA，API 仍用 lib.sh 里带联系方式的 UA。
  UA_MEDIA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
  dl() { "${CURL[@]}" -A "$UA_MEDIA" -H "Referer: https://commons.wikimedia.org/" \
         -H "Accept: image/avif,image/webp,image/*,*/*;q=0.8" -o "$out" "$url"; }
  if ! retry 3 8 dl; then
    info "失败 $slug：图片下载失败"; failed=$((failed + 1)); failed_list="$failed_list $slug"; sleep "$SLEEP"; continue
  fi

  # Commons 限流时会返回 HTTP 200 + 一段纯文本（"Please honor our robot policy..."），
  # 直接写盘就成了 60 字节的假图片，还会让后续图片被误判成重复图。必须校验魔数。
  bytes="$(wc -c < "$out" | tr -d ' ')"
  magic="$(od -An -tx1 -N2 "$out" | tr -d ' \n')"
  case "$magic" in
    ffd8|8950|4749|5249) : ;;  # jpeg / png / gif / ri 开头（webp 走 5249）
    *) info "失败 $slug：不是图片（$bytes B，magic=$magic），多半是 Commons 限流提示"; \
       rm -f "$out"; failed=$((failed + 1)); failed_list="$failed_list $slug(rl)"; sleep "$((SLEEP * 3))"; continue ;;
  esac
  if [ "${bytes:-0}" -lt 4096 ]; then
    info "失败 $slug：文件只有 $bytes B，判定无效"; rm -f "$out"; failed=$((failed + 1)); failed_list="$failed_list $slug(small)"; sleep "$SLEEP"; continue
  fi

  sum="$(md5_of "$out")"
  if grep -q "^$sum" "$seen_md5_file" 2>/dev/null; then
    prev="$(grep "^$sum" "$seen_md5_file" | head -1 | cut -d' ' -f2)"
    info "警告 $slug：与 $prev 内容相同（重复图），已删除"
    rm -f "$out"
    failed=$((failed + 1)); failed_list="$failed_list $slug(dup)"
  else
    printf '%s %s\n' "$sum" "$slug" >> "$seen_md5_file"
    size="$(wc -c < "$out" | tr -d ' ')"
    printf '{"slug":"%s","file":"%s","bytes":%s,"author":"%s","license":"%s","source":"https://commons.wikimedia.org/wiki/File:%s"}\n' \
      "$slug" "$out" "$size" "$author" "$license" "$title" >> "$OUT/credits.jsonl"
    esc_author="$(printf '%s' "$author" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
    esc_title="$(printf '%s' "$title" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
    printf '  "%s": { author: "%s", license: "%s", file: "%s" },\n' \
      "$slug" "$esc_author" "$license" "$esc_title" >> "$OUT/credits.snippet.js"
    printf '  %-22s %7s B  %-14s %s\n' "$slug" "$size" "$license" "$author"
    ok=$((ok + 1))
  fi

  sleep "$SLEEP"
done < "$MANIFEST"

# 收尾：snippet 去掉最后一个逗号，保证可粘贴
if [ "$ok" -gt 0 ]; then
  tmp="$(mktemp)"
  sed '$ s/,$//' "$OUT/credits.snippet.js" > "$tmp" && mv "$tmp" "$OUT/credits.snippet.js"
fi
printf '}\n' >> "$OUT/credits.snippet.js"

jq -n --argjson total "$total" --argjson ok "$ok" --argjson failed "$failed" \
  --arg dir "$OUT" --arg failed_list "$failed_list" \
  '{total:$total, ok:$ok, failed:$failed, dir:$dir, failed_slugs:($failed_list|split(" ")|map(select(length>0)))}' \
  > "$OUT/manifest.json"

info ""
info "完成：$ok/$total 张，失败 $failed"
[ "$failed" -gt 0 ] && info "失败清单：$failed_list"
[ "$ok" -eq 0 ] && exit 1
exit 0
