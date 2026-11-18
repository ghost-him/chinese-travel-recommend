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
说明：12306 预售期约 15 天，超出窗口返回空——这是「尚未开售」，不是「无车」。
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

    query = f"{BASE}/leftTicket/query"
    probe = client.get_json(query, {
        "leftTicketDTO.train_date": travel_date,
        "leftTicketDTO.from_station": from_code,
        "leftTicketDTO.to_station": to_code,
        "purpose_codes": "ADULT",
    })
    endpoint = (probe or {}).get("c_url") or "leftTicket/queryG"
    payload = client.get_json(f"{BASE}/{endpoint}", {
        "leftTicketDTO.train_date": travel_date,
        "leftTicketDTO.from_station": from_code,
        "leftTicketDTO.to_station": to_code,
        "purpose_codes": "ADULT",
    })
    rows = ((payload or {}).get("data") or {}).get("result") or []
    if not rows:
        info(f"# {args.from_name} -> {args.to_name} {travel_date}：无可售车次。")
        info("# 常见原因：超出 15 天预售期（尚未开售）、站名写法不符、或当日无直达。")
        return 3

    reverse = {value: key for key, value in table.items()}
    print("车次\t出发站\t时刻\t历时\t二等座\t一等座\t商务座\t无座")
    emitted = 0
    for row in rows:
        fields = row.split("|")
        if len(fields) < 36 or fields[7] != to_code:
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
        if args.seat == "O" and second == "—":
            continue
        if args.seat == "M" and first == "—":
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
        info(f"# {args.from_name} -> {args.to_name} {travel_date}：没有匹配席别的车次。")
        return 3
    info(f"# 数据源：12306 leftTicket/query + queryTicketPrice｜"
         f"查询时间：{dt.datetime.now():%Y-%m-%d %H:%M}｜乘车日：{travel_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
