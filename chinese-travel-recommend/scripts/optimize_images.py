#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""把报告里的图片压到便于传输的体积（长边 ≤1400、JPEG q82），不改变文件名。

为什么需要：Commons/Openverse 的原图常是 1920–4000px，几十张就能把报告顶到 70MB+。
页面最大展示宽度约 900px，压到 1400 长边肉眼无损，包体积能降到原来的 1/5。

用法：
  uv run --no-project scripts/optimize_images.py <images-dir> [--max-edge 1400] [--quality 82]

规则：
- 已经小于 max-edge 且小于 400KB 的图直接跳过
- 透明 PNG 会先铺白底再转 JPEG（报告里全是 jpg）
- 压完打印总体积变化；不会删除任何文件
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def human(num: int) -> str:
    return f"{num / 1048576:.1f} MB" if num >= 1048576 else f"{num / 1024:.0f} KB"


def main() -> int:
    parser = argparse.ArgumentParser(description="压缩报告图片")
    parser.add_argument("images_dir")
    parser.add_argument("--max-edge", type=int, default=1400)
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--skip-under-kb", type=int, default=400)
    args = parser.parse_args()

    directory = Path(args.images_dir)
    if not directory.is_dir():
        print(f"目录不存在: {directory}", file=sys.stderr)
        return 1

    before = after = 0
    changed = skipped = 0
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        size = path.stat().st_size
        before += size
        try:
            with Image.open(path) as probe:
                width, height = probe.size
                mode = probe.mode
                image = probe.convert("RGB") if mode in ("RGBA", "P", "LA") else probe.copy()
        except Exception as exc:
            print(f"  跳过 {path.name}：无法解码（{type(exc).__name__}）", file=sys.stderr)
            skipped += 1
            after += size
            continue

        longest = max(width, height)
        needs_resize = longest > args.max_edge
        needs_recompress = size > args.skip_under_kb * 1024
        if not needs_resize and not needs_recompress:
            skipped += 1
            after += size
            continue

        if needs_resize:
            ratio = args.max_edge / longest
            image = image.resize((max(1, round(width * ratio)), max(1, round(height * ratio))), Image.LANCZOS)
        target = path.with_suffix(".jpg")
        image.save(target, "JPEG", quality=args.quality, optimize=True, progressive=True)
        if target != path:
            path.unlink()
        new_size = target.stat().st_size
        after += new_size
        changed += 1
        print(f"  {path.name:<34} {human(size):>9} → {human(new_size):>9}  {width}×{height} → {image.size[0]}×{image.size[1]}")

    print(f"\n压缩 {changed} 张，跳过 {skipped} 张；总计 {human(before)} → {human(after)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
