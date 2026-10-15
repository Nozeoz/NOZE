"""One shared async HTTP client: polite User-Agent, per-host concurrency,
per-source pacing, retries, 429 handling, capped streaming downloads."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .config import Settings


try:  # HTTP/2 is optional (pip install h2)
    import h2  # noqa: F401

    _HTTP2 = True
except ImportError:  # pragma: no cover - depends on environment
    _HTTP2 = False


class SourceError(Exception):
    """A source failed in a way worth showing to the user."""


class RateLimited(SourceError):
    def __init__(self, message: str, retry_after: float = 600.0):
        super().__init__(message)
        self.retry_after = retry_after


class TooLarge(SourceError):
    pass


@dataclass
class Downloaded:
    path: Path
    sha256: str
    size: int
    mime: str
    final_url: str


def _retry_after(resp: httpx.Response, default: float) -> float:
    value = resp.headers.get("retry-after")
    if value:
        try:
            return max(1.0, float(value))
        except ValueError:
            pass
    reset = resp.headers.get("x-ratelimit-reset")
    if reset:
        try:
            r = float(reset)
            return max(1.0, r - time.time()) if r > 1e9 else max(1.0, r)
        except ValueError:
            pass
    return default


def _short(text: str, n: int = 200) -> str:
    text = " ".join((text or "").split())
    return text[:n] + ("…" if len(text) > n else "")


async def check_public_url(url: str, allow_private: bool = False) -> None:
    """Refuse non-http(s) URLs and (unless allowed) URLs resolving to private networks (SSRF guard)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("only http(s) URLs are allowed")
    if allow_private:
        return
    host = parsed.hostname
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("private/local addresses are not allowed")
    addrs: list[str] = []
    try:
        ipaddress.ip_address(host)
        addrs = [host]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
            addrs = [i[4][0] for i in infos]
        except OSError:
            addrs = []  # unresolvable here (e.g. behind a proxy) — the request itself will tell
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%", 1)[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("private/local addresses are not allowed")


class Http:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent, "Accept": "application/json, */*;q=0.5"},
            limits=httpx.Limits(max_connections=48, max_keepalive_connections=24),
            http2=_HTTP2,  # multiplexes thumbnail fetches; some APIs (Wikimedia) also treat h2 clients better
        )
        self._host_sems: dict[str, asyncio.Semaphore] = {}
        self._pace_locks: dict[str, asyncio.Lock] = {}
        self._last_call: dict[str, float] = {}

    async def aclose(self) -> None:
        await self.client.aclose()

    def _host_sem(self, url: str) -> asyncio.Semaphore:
        host = urlparse(url).hostname or ""
        sem = self._host_sems.get(host)
        if sem is None:
            sem = asyncio.Semaphore(6)
            self._host_sems[host] = sem
        return sem

    async def _pace(self, key: str | None, min_interval: float) -> None:
        if not key or min_interval <= 0:
            return
        lock = self._pace_locks.setdefault(key, asyncio.Lock())
        async with lock:
            wait = self._last_call.get(key, 0) + min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[key] = time.monotonic()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
        auth: Any = None,
        rate_key: str | None = None,
        min_interval: float = 0.0,
        timeout: float | None = None,
        retries: int = 2,
    ) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            await self._pace(rate_key, min_interval)
            try:
                async with self._host_sem(url):
                    resp = await self.client.request(
                        method, url, params=params, headers=headers, json=json, data=data, auth=auth,
                        timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                    )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt <= retries:
                    await asyncio.sleep(0.8 * attempt)
                    continue
                raise SourceError(f"network error: {type(exc).__name__}: {_short(str(exc), 120)}") from exc
            if resp.status_code == 429:
                wait = _retry_after(resp, 600.0)
                if wait <= 3 and attempt <= retries:
                    await asyncio.sleep(wait)
                    continue
                raise RateLimited(f"rate limited (429), retry after {int(wait)}s", wait)
            if resp.status_code >= 500 and attempt <= retries:
                await asyncio.sleep(1.0 * attempt)
                continue
            if resp.status_code >= 400:
                if resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
                    raise RateLimited("rate limited (403)", _retry_after(resp, 600.0))
                if resp.status_code == 403 and "robot policy" in resp.text[:300]:
                    raise RateLimited("blocked as a bot for now (Wikimedia) — add WIKIMEDIA_TOKEN or try later", 3600.0)
                raise SourceError(f"HTTP {resp.status_code}: {_short(resp.text)}")
            return resp

    async def get_json(self, url: str, **kw: Any) -> Any:
        resp = await self.request("GET", url, **kw)
        try:
            return resp.json()
        except ValueError as exc:
            raise SourceError(f"invalid JSON from {urlparse(url).hostname}") from exc

    async def post_json(self, url: str, payload: Any, **kw: Any) -> Any:
        resp = await self.request("POST", url, json=payload, **kw)
        try:
            return resp.json()
        except ValueError as exc:
            raise SourceError(f"invalid JSON from {urlparse(url).hostname}") from exc

    async def fetch_bytes(self, url: str, max_bytes: int = 12 * 1024 * 1024, headers: dict[str, str] | None = None,
                          timeout: float = 25.0) -> tuple[bytes, str]:
        async with self._host_sem(url):
            async with self.client.stream("GET", url, headers=headers, timeout=timeout) as resp:
                if resp.status_code >= 400:
                    raise SourceError(f"HTTP {resp.status_code} for {urlparse(url).hostname}")
                length = resp.headers.get("content-length")
                if length and length.isdigit() and int(length) > max_bytes:
                    raise TooLarge(f"file too large ({int(length) // 1024} KB)")
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise TooLarge("file too large")
                    chunks.append(chunk)
                return b"".join(chunks), resp.headers.get("content-type", "")

    async def download(self, url: str, dest_dir: Path, max_bytes: int, headers: dict[str, str] | None = None,
                       timeout: float = 300.0, check_public: bool = False) -> Downloaded:
        """Stream a file to a temp path while hashing it."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        tmp = dest_dir / f"dl-{uuid.uuid4().hex}.part"
        digest = hashlib.sha256()
        size = 0
        current = url
        try:
            for _ in range(6):
                if check_public:
                    await check_public_url(current, self.settings.allow_private_fetch)
                async with self._host_sem(current):
                    async with self.client.stream(
                        "GET", current, headers=headers, timeout=timeout, follow_redirects=not check_public
                    ) as resp:
                        if resp.is_redirect and check_public:
                            current = urljoin(current, resp.headers.get("location", ""))
                            continue
                        if resp.status_code >= 400:
                            raise SourceError(f"HTTP {resp.status_code} downloading from {urlparse(current).hostname}")
                        length = resp.headers.get("content-length")
                        if length and length.isdigit() and int(length) > max_bytes:
                            raise TooLarge(f"file is {int(length) / 1e6:.0f} MB, limit is {max_bytes / 1e6:.0f} MB")
                        with tmp.open("wb") as fh:
                            async for chunk in resp.aiter_bytes(1 << 16):
                                size += len(chunk)
                                if size > max_bytes:
                                    raise TooLarge(f"file exceeds {max_bytes / 1e6:.0f} MB limit")
                                digest.update(chunk)
                                fh.write(chunk)
                        return Downloaded(tmp, digest.hexdigest(), size, resp.headers.get("content-type", ""), str(resp.url))
            raise SourceError("too many redirects")
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    async def fetch_user_url(self, url: str, max_bytes: int = 5 * 1024 * 1024) -> tuple[bytes, str, str]:
        """GET a URL supplied by the user (bookmarklet/paste) with SSRF checks on every redirect hop."""
        current = url
        for _ in range(6):
            await check_public_url(current, self.settings.allow_private_fetch)
            async with self.client.stream(
                "GET", current, follow_redirects=False, timeout=20.0,
                headers={"Accept": "text/html,application/xhtml+xml,image/*,video/*,*/*;q=0.8"},
            ) as resp:
                if resp.is_redirect:
                    current = urljoin(current, resp.headers.get("location", ""))
                    continue
                if resp.status_code >= 400:
                    raise SourceError(f"HTTP {resp.status_code}")
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        break
                    chunks.append(chunk)
                return b"".join(chunks), resp.headers.get("content-type", ""), str(resp.url)
        raise SourceError("too many redirects")
