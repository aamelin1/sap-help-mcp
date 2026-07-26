"""Minimal HTTP client for the SAP sources: GET, JSON, timeout, in-memory cache.

Standard library on purpose — pulling in httpx for two GET requests is not worth
the dependency. Nothing raises out of this module: callers get (data, error).

The cache exists because documentation pages and forum posts change rarely, while
asking the same question twice inside one conversation is completely normal.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

USER_AGENT = f"sap-help-mcp/{__version__} (+https://github.com/aamelin1/sap-help-mcp)"
TIMEOUT = 12.0          # seconds per request
CACHE_TTL = 6 * 3600    # 6 hours
CACHE_MAX = 300

# community.search fans out over a thread pool, so the cache is touched
# concurrently. The lock keeps eviction from racing with insertion.
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def build_url(base: str, params: dict) -> str:
    """URL with a query string; empty and None parameters are dropped."""
    clean = {k: str(v) for k, v in params.items() if v not in (None, "")}
    return f"{base}?{urllib.parse.urlencode(clean)}" if clean else base


def _cache_get(url: str) -> dict | None:
    with _cache_lock:
        hit = _cache.get(url)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    return None


def _cache_put(url: str, data: dict) -> None:
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest, None)
        _cache[url] = (time.time(), data)


def get_json(url: str, *, referer: str | None = None,
             use_cache: bool = True) -> tuple[dict | None, str | None]:
    """Return (data, error). The error is a human-readable string, never an exception."""
    if use_cache:
        cached = _cache_get(url)
        if cached is not None:
            return cached, None

    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return None, (f"SAP responded {exc.code} {exc.reason}. A 4xx usually means the "
                      "portal changed its request format (see sap_help_mcp/probe.py).")
    except urllib.error.URLError as exc:
        return None, f"Network unreachable or timed out: {exc.reason}"
    except Exception as exc:                      # noqa: BLE001 — networking, anything goes
        return None, f"Unexpected request failure: {exc}"

    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return None, ("Response was not JSON — the portal most likely returned an HTML "
                      "placeholder (bot protection, or the endpoint moved).")
    if not isinstance(data, dict):
        return None, "Response was JSON but not an object — the format changed."

    if use_cache:
        _cache_put(url, data)
    return data, None


_SCRIPT_STYLE_RE = None


def html_to_markdown(html: str) -> str:
    """HTML fragment -> markdown. markdownify is optional: without it, a crude fallback.

    Scripts and styles are cut out here, before conversion, on purpose: markdownify's
    strip= drops the tags but keeps their text content, which would otherwise dump raw
    JavaScript and CSS into the middle of the page text.
    """
    global _SCRIPT_STYLE_RE
    if _SCRIPT_STYLE_RE is None:
        import re as _re
        _SCRIPT_STYLE_RE = _re.compile(r"<(script|style)\b[^>]*>.*?</\1>",
                                       _re.S | _re.I)
    html = _SCRIPT_STYLE_RE.sub(" ", html)

    try:
        from markdownify import markdownify
        return markdownify(html, heading_style="ATX", strip=["script", "style"]).strip()
    except Exception:
        import html as html_mod
        import re
        text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", html, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_mod.unescape(text)
        return re.sub(r"[ \t]{2,}", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def cache_stats() -> dict:
    with _cache_lock:
        entries = len(_cache)
    return {"entries": entries, "ttl_seconds": CACHE_TTL}
