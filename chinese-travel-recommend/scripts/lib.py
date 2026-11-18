# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32"]
# ///
"""chinese-travel-recommend 脚本共用工具：HTTP、重试、哈希。

依赖由 uv 按本文件的 PEP 723 元数据自动安装；不要手动 pip install。
"""

from __future__ import annotations

import hashlib
import sys

UA_DEFAULT = "TravelRecommendSkill/1.4 (local; contact: you@example.com)"
UA_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def info(message: str) -> None:
    print(message, file=sys.stderr)


def die(message: str) -> "NoReturn":
    info(f"ERROR: {message}")
    raise SystemExit(1)


class Client:
    """带 cookie、重试、统一 UA 的 requests 会话。"""

    def __init__(self, *, user_agent: str = UA_DEFAULT, timeout: int = 45, retries: int = 3):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "*/*"})
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=1.2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> bytes:
        response = self.session.get(
            url,
            params=params,
            headers=headers or {},
            timeout=timeout or self.timeout,
        )
        response.raise_for_status()
        return response.content

    def get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        response = self.session.get(
            url,
            params=params,
            headers={"Accept": "application/json", **(headers or {})},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


def md5_of(path: str) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def js_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
