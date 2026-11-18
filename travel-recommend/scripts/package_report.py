#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["json5>=0.9"]
# ///
"""把报告目录打成 zip，保留顶层文件夹（解压后不散落）。

用法：
  uv run --no-project scripts/package_report.py <report-dir> [out.zip] [--skip-verify]

默认先跑 verify_report.py，自检不通过就中止，避免把缺图的包发出去。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="报告打包（先自检）")
    parser.add_argument("report_dir")
    parser.add_argument("out_zip", nargs="?")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    report = Path(args.report_dir).resolve()
    if not report.is_dir():
        print(f"ERROR: 目录不存在: {report}", file=sys.stderr)
        return 1
    out = Path(args.out_zip).resolve() if args.out_zip else Path.cwd() / f"{report.name}.zip"

    if not args.skip_verify:
        verifier = Path(__file__).with_name("verify_report.py")
        print("运行自检…", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, str(verifier), str(report)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            print("ERROR: 自检未通过，已中止打包（--skip-verify 可跳过）", file=sys.stderr)
            return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    entries = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        skip_names = {".DS_Store", ".seen-md5", "credits.jsonl", "credits.snippet.js", "manifest.json"}
        for path in sorted(report.rglob("*")):
            if not path.is_file() or path.resolve() == out:
                continue
            if path.name in skip_names or path.name.startswith(".meta-") or "__pycache__" in path.parts:
                continue
            if path.suffix.lower() == ".zip":
                continue
            archive.write(path, arcname=f"{report.name}/{path.relative_to(report).as_posix()}")
            entries += 1

    if not out.is_file():
        print(f"ERROR: 打包失败：未生成 {out}", file=sys.stderr)
        return 1
    size_mb = out.stat().st_size / 1048576
    print(f"\n完成：{out}（{size_mb:.1f} MB，{entries} 个文件，顶层 {report.name}/）", file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
