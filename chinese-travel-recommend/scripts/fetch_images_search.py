#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32", "pillow>=10"]
# ///
"""按关键词从多个图源并发抓图（不需要预先知道文件名）。

为什么多源：单一图源有硬性限速（Commons 约 1 次/3.5 秒），串行抓几十张要十几分钟。
把请求分散到不同站点、各自遵守自己的限速，就能并行推进，还能拿到风格不同的图。

图源（2026-11-18 全部实测免 key 可用）：
  commons     Wikimedia Commons 关键词搜索         限速 3.5 s/次
  commonscat  Commons 分类（Category:<词>）成员    与 commons 共用限速
  openverse   Openverse v1（聚合 Flickr/博物馆等） 限速 1.2 s/次（偶发 0 结果，会熔断）
  wikipedia   维基条目首图（zh 优先、en 兜底）     限速 1.5 s/次

实测不可用（别再试）：Library of Congress（Cloudflare 403）、The Met（API 2026-10 下线）、
Art Institute of Chicago（Cloudflare 403）、Pexels/Pixabay/Unsplash（需 key）。

用法：
  uv run --no-project scripts/fetch_images_search.py <输出目录> <清单.tsv> [--workers 3]
  uv run --no-project scripts/fetch_images_search.py images m.tsv --sources commonscat,wikipedia
  uv run --no-project scripts/fetch_images_search.py images m.tsv --sources commons --workers 5 --sleep 2.5

清单每行（| 分隔，可带 # 注释）：
  changbaishan-tianchi|Changbai Mountain Tianchi|3
  字段：<slug 前缀> | <检索词> | <要几张，默认 2> [| <最小宽度，默认 1000>]

产物：<slug>-N.jpg、manifest.json。脚本只负责下载与去重；
**图片是否为目标地点，由 AI 抓完后逐张看图确认**（脚本不做题材判断）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from PIL import Image

from lib import UA_BROWSER, Client, md5_of

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
WIKI_APIS = [
    ("https://zh.wikipedia.org/w/api.php", "zh"),
    ("https://en.wikipedia.org/w/api.php", "en"),
]
OK_MIME = {"image/jpeg", "image/png"}
BAD_WORDS = ("map", "diagram", "logo", "icon", "seal", "flag", "chart", "svg", "coat of arms",
             "banner", "screenshot", "signature")
# 每个图源自己的最小请求间隔（秒）；互不共享，所以能并行
MIN_INTERVAL = {"commons": 3.5, "commonscat": 3.5, "openverse": 1.2, "wikipedia": 1.5, "web": 1.5}


class Throttle:
    """同一图源的请求串行排队，不同图源互不影响。"""

    def __init__(self, interval: float):
        self.interval = interval
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self) -> None:
        with self.lock:
            gap = time.time() - self.last
            if gap < self.interval:
                time.sleep(self.interval - gap)
            self.last = time.time()


class Fetcher:
    def __init__(self, sources: list[str]):
        self.sources = sources
        # commons 源即使没被选中，也要有节流对象（分类检索与维基首图都要回查它的 API）
        self.throttle = {name: Throttle(MIN_INTERVAL[name]) for name in set(sources) | {"commons"}}
        if "commonscat" in sources:
            self.throttle["commonscat"] = self.throttle["commons"]
        # 超时压短、重试 1 次：Openverse 与维基偶发长时间挂起，长重试会把整批任务拖死
        self.client = Client(user_agent=UA_BROWSER, timeout=25, retries=1)
        self.media = Client(user_agent=UA_BROWSER, timeout=60, retries=1)
        self.failures = {name: 0 for name in sources}
        self.dead: set[str] = set()
        self.state_lock = threading.Lock()

    def _mark(self, source: str, exc: Exception | None) -> None:
        """源熔断：连续 4 次异常就放弃这个源，避免一个坏源拖住整批。"""
        if exc is None:
            return
        with self.state_lock:
            self.failures[source] += 1
            if self.failures[source] >= 4 and source not in self.dead:
                self.dead.add(source)
                print(f"  [{source}] 连续失败 {self.failures[source]} 次，本批放弃该源", file=sys.stderr)

    # ---------- 公共：按文件标题批量取图信息 ----------
    def commons_info(self, titles: list[str], min_width: int) -> list[dict]:
        """titles 形如 ["File:A.jpg", ...]；一次批量查询，返回可下载的候选。"""
        if not titles:
            return []
        self.throttle["commons"].wait()
        payload = self.client.get_json(COMMONS_API, {
            "action": "query", "titles": "|".join(titles[:40]),
            "prop": "imageinfo", "iiprop": "url|size|mime",
            "iiurlwidth": "1400", "format": "json",
        })
        items: list[dict] = []
        for page in ((payload.get("query") or {}).get("pages") or {}).values():
            info = (page.get("imageinfo") or [None])[0]
            title = page.get("title", "")
            if not info or any(word in title.lower() for word in BAD_WORDS):
                continue
            if (info.get("mime") or "") not in OK_MIME or (info.get("width") or 0) < min_width:
                continue
            items.append({
                "url": info.get("thumburl") or info.get("url"),
                "title": title,
                "page": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
            })
        return items

    # ---------- 图源 1：Commons 关键词搜索 ----------
    def commons(self, term: str, want: int, min_width: int) -> list[dict]:
        self.throttle["commons"].wait()
        payload = self.client.get_json(COMMONS_API, {
            "action": "query", "generator": "search",
            "gsrsearch": f"filetype:bitmap {term}", "gsrnamespace": "6",
            "gsrlimit": str(max(want * 4, 10)),
            "prop": "imageinfo", "iiprop": "url|size|mime",
            "iiurlwidth": "1400", "format": "json",
        })
        items: list[dict] = []
        for page in ((payload.get("query") or {}).get("pages") or {}).values():
            info = (page.get("imageinfo") or [None])[0]
            title = page.get("title", "")
            if not info or any(word in title.lower() for word in BAD_WORDS):
                continue
            if (info.get("mime") or "") not in OK_MIME or (info.get("width") or 0) < min_width:
                continue
            items.append({
                "url": info.get("thumburl") or info.get("url"),
                "title": title,
                "page": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
            })
        return items

    # ---------- 图源 2：Commons 分类 ----------
    def commonscat(self, term: str, want: int, min_width: int) -> list[dict]:
        self.throttle["commonscat"].wait()
        payload = self.client.get_json(COMMONS_API, {
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{term}", "cmtype": "file",
            "cmlimit": str(max(want * 3, 6)), "format": "json",
        })
        titles = [row["title"] for row in ((payload.get("query") or {}).get("categorymembers") or [])
                  if row.get("title", "").lower().endswith((".jpg", ".jpeg", ".png"))]
        return self.commons_info(titles, min_width)

    # ---------- 图源 3：Openverse ----------
    def openverse(self, term: str, want: int, min_width: int) -> list[dict]:
        self.throttle["openverse"].wait()
        payload = self.client.get_json(OPENVERSE_API, {
            "q": term, "page_size": str(max(want * 4, 8)),
        })
        items: list[dict] = []
        for row in payload.get("results") or []:
            title = (row.get("title") or "").lower()
            if any(word in title for word in BAD_WORDS):
                continue
            if (row.get("width") or 0) and row["width"] < min_width:
                continue
            if not row.get("url"):
                continue
            items.append({
                "url": row["url"],
                "title": row.get("title") or term,
                "page": row.get("foreign_landing_url") or row["url"],
            })
        return items

    # ---------- 图源 4：维基条目首图 ----------
    def wikipedia(self, term: str, want: int, min_width: int) -> list[dict]:
        titles: list[str] = []
        for endpoint, _lang in WIKI_APIS:
            self.throttle["wikipedia"].wait()
            try:
                payload = self.client.get_json(endpoint, {
                    "action": "query", "generator": "search", "gsrsearch": term,
                    "gsrlimit": str(max(want, 3)), "gsrnamespace": "0",
                    "prop": "pageimages", "piprop": "name", "format": "json", "redirects": "1",
                })
            except Exception:
                continue
            for page in ((payload.get("query") or {}).get("pages") or {}).values():
                name = page.get("pageimage")
                if name:
                    titles.append(f"File:{name}")
            if len(titles) >= want:
                break
        # 首图可能来自同名他地，抓下来必须目检
        return self.commons_info(titles[:want], min_width)

    # ---------- 图源 5：公开网络（百度图片检索） ----------
    def web(self, term: str, want: int, min_width: int) -> list[dict]:
        self.throttle["web"].wait()
        payload = self.client.get_json("https://image.baidu.com/search/acjson", {
            "tn": "resultjson_com", "ipn": "rj", "word": term,
            "pn": "0", "rn": str(max(want * 6, 24)),
        }, headers={"Accept-Language": "zh-CN,zh;q=0.9", "Referer": "https://image.baidu.com/"})
        items: list[dict] = []
        for row in payload.get("data") or []:
            if not row:
                continue
            url = row.get("middleURL") or row.get("hoverURL") or row.get("thumbURL")
            if not url or any(word in url.lower() for word in BAD_WORDS):
                continue
            items.append({
                "url": url,
                "title": row.get("fromPageTitleEnc") or term,
                "page": row.get("fromURL") or ("https://" + row["fromURLHost"]) if row.get("fromURLHost") else "https://image.baidu.com/",
            })
        return items

    def search(self, source: str, term: str, want: int, min_width: int) -> list[dict]:
        if source in self.dead:
            return []
        try:
            items = getattr(self, source)(term, want, min_width)
        except Exception as exc:
            print(f"  [{source}] 检索失败 {term}: {type(exc).__name__}", file=sys.stderr)
            self._mark(source, exc)
            return []
        with self.state_lock:
            self.failures[source] = 0
        return items

    def download(self, item: dict) -> bytes | None:
        try:
            blob = self.media.get(item["url"], headers={"Referer": item["page"]})
            probe = Image.open(BytesIO(blob))
            probe.verify()
        except Exception:
            return None
        return blob if len(blob) >= 4096 else None


def main() -> int:
    parser = argparse.ArgumentParser(description="多源检索抓图")
    parser.add_argument("out_dir")
    parser.add_argument("manifest")
    parser.add_argument("--sleep", type=float, default=None, help="兼容旧参数：覆盖 commons 的间隔")
    parser.add_argument("--sources", default="commons,commonscat,wikipedia,openverse,web",
                        help="逗号分隔：commons,commonscat,wikipedia,openverse,web")
    parser.add_argument("--workers", type=int, default=3, help="并发任务数（每个图源内部仍各自限速）")
    args = parser.parse_args()

    sources = [name.strip() for name in args.sources.split(",") if name.strip() in MIN_INTERVAL]
    if not sources:
        print("ERROR: --sources 里没有可用图源", file=sys.stderr)
        return 1
    if args.sleep:
        MIN_INTERVAL["commons"] = args.sleep
        MIN_INTERVAL["commonscat"] = args.sleep

    out = Path(args.out_dir)
    manifest = Path(args.manifest)
    if not manifest.is_file():
        print(f"清单不存在: {manifest}", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    seen_file = out / ".seen-md5"
    seen: dict[str, str] = {}
    if seen_file.is_file():
        for line in seen_file.read_text(encoding="utf-8").splitlines():
            if " " in line:
                digest, slug = line.split(" ", 1)
                seen[digest] = slug

    jobs: list[tuple[str, str, int, int]] = []
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        jobs.append((
            re.sub(r"\s+", "", parts[0]),
            parts[1],
            int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 2,
            int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1000,
        ))

    fetcher = Fetcher(sources)
    results_lock = threading.Lock()
    stats = {"ok": 0, "total": sum(job[2] for job in jobs), "failed": []}

    def work(job: tuple[str, str, int, int]) -> None:
        slug, term, want, min_width = job

        def query(source: str) -> tuple[str, list[dict]]:
            return source, fetcher.search(source, term, want, min_width)

        # 同时向所有图源各问一次（各自限速、互不阻塞），再交替取图 → 风格更杂
        with ThreadPoolExecutor(max_workers=len(sources)) as inner:
            batches = list(inner.map(query, sources))
        pools = {name: items for name, items in batches}
        ordered: list[tuple[str, dict]] = []
        for index in range(want * 2):
            for name in sources:
                items = pools.get(name) or []
                if index < len(items):
                    ordered.append((name, items[index]))

        got = 0
        # 从已有文件的下一个编号续写，避免补图时把已抓到的 slug-1.jpg 覆盖掉
        existing = [
            int(match.group(1))
            for path in out.glob(f"{slug}-*.jpg")
            if (match := re.match(rf"{re.escape(slug)}-(\d+)\.jpg$", path.name))
        ]
        start = (max(existing) if existing else 0) + 1
        for source, item in ordered:
            if got >= want:
                break
            blob = fetcher.download(item)
            if not blob:
                continue
            with results_lock:
                number = start + got
                name = f"{slug}-{number}"
                target = out / f"{name}.jpg"
                target.write_bytes(blob)
                digest = md5_of(str(target))
                if digest in seen:
                    target.unlink(missing_ok=True)
                    continue
                seen[digest] = name
                with seen_file.open("a", encoding="utf-8") as handle:
                    handle.write(f"{digest} {name}\n")
                stats["ok"] += 1
                got += 1
                print(f"  {name:<26} {source:<10} {len(blob):>8} B  {item.get('title', '')[:40]}")
        if got < want:
            with results_lock:
                stats["failed"].append(f"{slug}({got}/{want})")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(work, job) for job in jobs]
        for future in as_completed(futures):
            future.result()

    (out / "manifest.json").write_text(json.dumps({
        "total": stats["total"], "ok": stats["ok"], "failed": stats["failed"],
        "dir": str(out), "sources": sources,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：{stats['ok']}/{stats['total']} 张，缺口 {len(stats['failed'])} 项", file=sys.stderr)
    if stats["failed"]:
        print("缺口：" + " ".join(stats["failed"]), file=sys.stderr)
    return 0 if stats["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
