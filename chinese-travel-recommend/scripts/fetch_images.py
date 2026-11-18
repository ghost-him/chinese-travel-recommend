#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32", "pillow>=10"]
# ///
"""从 Wikimedia Commons 按文件名批量抓图（去重、重试、尺寸校验）。

用法：
  uv run --no-project scripts/fetch_images.py <输出目录> <清单.tsv> [--sleep 6]

清单每行（| 分隔，可带 # 注释）：
  kaiyuan-1|Kaiyuan Temple, Quanzhou 16.jpg
  kaiyuan-2|File:The courtyard of Quanzhou Kaiyuan Temple 20170727.jpg
  第三个字段可选：宽度（默认 1200）

产物：<slug>.jpg、manifest.json（`.seen-md5` 记录去重哈希）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from lib import UA_BROWSER, Client, info, md5_of

API = "https://commons.wikimedia.org/w/api.php"


def fetch_url(client: Client, title: str, width: int) -> str | None:
    try:
        payload = client.get_json(API, {
            "action": "query",
            "titles": f"File:{title}",
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": str(width),
            "format": "json",
        })
    except Exception:
        return None
    for page in ((payload.get("query") or {}).get("pages") or {}).values():
        if page.get("missing"):
            return None
        imageinfo = (page.get("imageinfo") or [None])[0]
        if imageinfo:
            return imageinfo.get("thumburl") or imageinfo.get("url")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Commons 批量抓图")
    parser.add_argument("out_dir")
    parser.add_argument("manifest")
    parser.add_argument("--sleep", type=float, default=6.0)
    parser.add_argument("--width", type=int, default=1200)
    args = parser.parse_args()

    out = Path(args.out_dir)
    manifest = Path(args.manifest)
    if not manifest.is_file():
        info(f"清单不存在: {manifest}")
        return 1
    out.mkdir(parents=True, exist_ok=True)

    seen_file = out / ".seen-md5"
    seen: dict[str, str] = {}
    if seen_file.is_file():
        for line in seen_file.read_text(encoding="utf-8").splitlines():
            if " " in line:
                digest, slug = line.split(" ", 1)
                seen[digest] = slug
    seen_file.write_text("", encoding="utf-8")

    client = Client(user_agent=UA_BROWSER, timeout=45)
    media = Client(user_agent=UA_BROWSER, timeout=90)
    total = ok = failed = 0
    failures: list[str] = []

    for raw in manifest.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [part.strip() for part in raw.split("|")]
        slug = re.sub(r"\s+", "", parts[0])
        title = re.sub(r"^File:", "", parts[1] if len(parts) > 1 else "")
        width = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else args.width
        if not slug or not title:
            info(f"跳过：{raw}")
            continue
        total += 1
        url = fetch_url(client, title, width)
        if not url:
            info(f"失败 {slug}：API 取不到（429 限流、文件名不对，或文件不存在）")
            failures.append(slug)
            failed += 1
            time.sleep(args.sleep)
            continue

        try:
            blob = media.get(url, headers={"Referer": "https://commons.wikimedia.org/"})
        except Exception:
            info(f"失败 {slug}：图片下载失败")
            failures.append(slug)
            failed += 1
            time.sleep(args.sleep)
            continue
        try:
            probe = Image.open(BytesIO(blob))
            probe.verify()
            probe = Image.open(BytesIO(blob))
            pixel_width, pixel_height = probe.size
        except (UnidentifiedImageError, OSError, ValueError):
            info(f"失败 {slug}：不是可解码图片（{len(blob)} B），多半是 Commons 限流提示")
            failures.append(slug)
            failed += 1
            time.sleep(args.sleep * 3)
            continue
        if len(blob) < 4096 or pixel_width < 300 or pixel_height < 200:
            info(f"失败 {slug}：图片过小（{len(blob)} B，{pixel_width}×{pixel_height}）")
            failures.append(slug)
            failed += 1
            time.sleep(args.sleep)
            continue
        target = out / f"{slug}.jpg"
        target.write_bytes(blob)
        digest = md5_of(str(target))
        if digest in seen:
            info(f"警告 {slug}：与 {seen[digest]} 内容相同（重复图），已删除")
            target.unlink(missing_ok=True)
            failures.append(f"{slug}(dup)")
            failed += 1
        else:
            seen[digest] = slug
            with seen_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{digest} {slug}\n")
            print(f"  {slug:<22} {len(blob):>8} B  {pixel_width}×{pixel_height}")
            ok += 1
        time.sleep(args.sleep)

    summary = {
        "total": total,
        "ok": ok,
        "failed": failed,
        "dir": str(out),
        "failed_slugs": failures,
    }
    (out / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    info("")
    info(f"完成：{ok}/{total} 张，失败 {failed}")
    if failures:
        info("失败清单：" + " ".join(failures))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
