#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""12306 车次与票价实查（只读，不登录、不下单）。

用法：
  uv run --no-project scripts/fetch_rail_fares.py 上海虹桥 泉州南 2026-11-25
  uv run --no-project scripts/fetch_rail_fares.py 广州南 潮汕 2026-12-02 O

输出（TSV）：车次 / 出发站 / 时刻 / 历时 / 二等座 / 一等座 / 商务座 / 无座
说明：12306 预售期约 14 天，超出窗口返回空——这是「尚未开售」，不是「无车」。
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

from lib import Client, die, info

BASE = "https://kyfw.12306.cn/otn"
REFERER = f"{BASE}/leftTicket/init"
STATIONS_URL = f"{BASE}/resources/js/framework/station_name.js"


def ensure_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        die(f"乘车日期格式应为 YYYY-MM-DD：{value}")
    return value


def query(client: Client, endpoint: str, params: dict[str, str]) -> dict | None:
    """查 leftTicket。返回 None 表示对方回的是 HTML 页（超预售期/风控），不是「无车」。"""
    response = client.session.get(
        f"{BASE}/{endpoint}",
        params=params,
        headers={"Accept": "application/json, text/javascript, */*", "Referer": REFERER},
        timeout=client.timeout,
    )
    response.raise_for_status()
    if "json" not in (response.headers.get("content-type") or "").lower():
        return None
    try:
        return response.json()
    except ValueError:
        return None


def station_table(client: Client) -> dict[str, str]:
    raw = client.get(STATIONS_URL).decode("utf-8-sig", errors="replace")
    table: dict[str, str] = {}
    for segment in raw.split("@"):
        parts = segment.split("|")
        if len(parts) >= 3 and parts[1] and parts[2]:
            table.setdefault(parts[1], parts[2])
    return table


def code_of(table: dict[str, str], name: str) -> str:
    code = table.get(name)
    if code:
        return code
    near = [f"{key}({value})" for key, value in table.items() if name in key][:5]
    hint = " ".join(near) if near else "无"
    die(f"找不到车站「{name}」。可用近似名：{hint}")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="12306 车次与票价实查")
    parser.add_argument("from_name", help="出发站中文名，如 上海虹桥")
    parser.add_argument("to_name", help="到达站中文名，如 泉州南")
    parser.add_argument("date", help="乘车日期 YYYY-MM-DD")
    parser.add_argument("seat", nargs="?", default="", help="席别过滤：O=二等座，M=一等座")
    args = parser.parse_args()
    travel_date = ensure_date(args.date)

    client = Client(timeout=30)
    client.get(REFERER)  # 先拿会话 cookie；缺 cookie 时查询接口会返回空
    table = station_table(client)
    from_code = code_of(table, args.from_name)
    to_code = code_of(table, args.to_name)

    params = {
        "leftTicketDTO.train_date": travel_date,
        "leftTicketDTO.from_station": from_code,
        "leftTicketDTO.to_station": to_code,
        "purpose_codes": "ADULT",
    }
    probe = query(client, "leftTicket/query", params)
    if probe is None:
        info(f"# {args.from_name} -> {args.to_name} {travel_date}：12306 返回的是 HTML 页而不是 JSON。")
        info("# 这通常意味着超出约 14 天预售期（尚未开售）或触发风控，**不是「无车」**。")
        info("# 处理方式：开售后再查；本次报价改用 estimated 区间并注明未开售。")
        return 3
    endpoint = probe.get("c_url") or "leftTicket/queryG"
    payload = query(client, endpoint, params) or probe
    rows = ((payload or {}).get("data") or {}).get("result") or []
    if not rows:
        info(f"# {args.from_name} -> {args.to_name} {travel_date}：无可售车次。")
        info("# 常见原因：当日无直达、站名写法不符，或该 OD 暂无车次。")
        return 3

    reverse = {value: key for key, value in table.items()}
    print("车次\t出发站\t时刻\t历时\t二等座\t一等座\t商务座\t无座")
    emitted = 0
    seat_skipped = 0
    dest_seen: dict[str, int] = {}
    for row in rows:
        fields = row.split("|")
        if len(fields) < 36:
            continue
        dest_seen[fields[7]] = dest_seen.get(fields[7], 0) + 1
        if fields[7] != to_code:
            continue
        train = fields[3]
        from_tele = fields[6]
        dep, arr, duration = fields[8], fields[9], fields[10]
        train_no, from_no, to_no, seat_types = fields[2], fields[16], fields[17], fields[35]
        if not train_no:
            continue
        try:
            prices = client.get_json(f"{BASE}/leftTicket/queryTicketPrice", {
                "train_no": train_no,
                "from_station_no": from_no,
                "to_station_no": to_no,
                "seat_types": seat_types,
                "train_date": travel_date,
            })
        except Exception:
            prices = {}
        data = (prices or {}).get("data") or {}

        def pick(key: str) -> str:
            value = data.get(key)
            return str(value) if value not in (None, "") else "—"

        second, first, business, standing = pick("O"), pick("M"), pick("A9"), pick("WZ")
        if (args.seat == "O" and second == "—") or (args.seat == "M" and first == "—"):
            seat_skipped += 1
            continue
        print("\t".join([
            train,
            reverse.get(from_tele, from_tele),
            f"{dep}-{arr}",
            duration,
            second,
            first,
            business,
            standing,
        ]))
        emitted += 1
        time.sleep(0.3)

    if emitted == 0:
        if seat_skipped:
            info(f"# {args.from_name} -> {args.to_name} {travel_date}："
                 f"有 {seat_skipped} 班终到本站，但该席别无票。")
            return 3
        near = "、".join(
            f"{reverse.get(code, code)}({code}) {count} 班"
            for code, count in sorted(dest_seen.items(), key=lambda kv: -kv[1])[:5]
        )
        info(f"# {args.from_name} -> {args.to_name} {travel_date}："
             f"没有终到「{args.to_name}」的直达车次。")
        info(f"# 12306 返回 {len(rows)} 班，终到站分布：{near or '—'}")
        info("# 注意：12306 不按 from/to 参数过滤，返回的是整片区域车次；"
             "换邻近大站再查，或改用飞机。")
        return 3
    info(f"# 数据源：12306 leftTicket/query + queryTicketPrice｜"
         f"查询时间：{dt.datetime.now():%Y-%m-%d %H:%M}｜乘车日：{travel_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
