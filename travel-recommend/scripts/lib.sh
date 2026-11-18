#!/usr/bin/env bash
# lib.sh — 脚本共用的小工具。不要直接执行。
# shellcheck shell=bash

UA_DEFAULT="TravelRecommendSkill/1.1 (local; contact: you@example.com)"

have() { command -v "$1" >/dev/null 2>&1; }

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*" >&2; }

# 初始化 CURL 数组：统一 UA；Windows 的 schannel curl 需要关闭吊销检查
curl_init() {
  CURL=(curl -sS -m 45 -A "${UA:-$UA_DEFAULT}")
  if curl --help all 2>/dev/null | grep -q -- '--ssl-no-revoke'; then
    CURL+=(--ssl-no-revoke)
  fi
}

# 统一的重试封装：retry <次数> <间隔秒> <命令...>
retry() {
  local tries="$1" gap="$2"; shift 2
  local n=1
  while true; do
    if "$@"; then return 0; fi
    [ "$n" -ge "$tries" ] && return 1
    sleep $((gap * n))
    n=$((n + 1))
  done
}

md5_of() {
  if have md5sum; then md5sum "$1" | awk '{print $1}'
  elif have md5; then md5 -q "$1"
  else shasum -a 256 "$1" | awk '{print $1}'
  fi
}
