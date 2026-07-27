"""Minimal HTTP client for the SAP sources: GET, JSON, timeout, in-memory cache.

Standard library on purpose — pulling in httpx for two GET requests is not worth
the dependency. Nothing raises out of this module: callers get (data, error).

The cache exists because documentation pages and forum posts change rarely, while
asking the same question twice inside one conversation is completely normal.
"""

from __future__ import annotations

import html as html_mod
import json
import re
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


_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)

# The portal emits leftovers of its DITA toolchain as XML processing instructions,
# e.g. <?sap-ot O2O class="- topic/xref " href="0444….xml"
#      text="Foreign currency balance sheet accounts" … xtrf="file:/home/builder/…" >
# Note it closes with a plain ">", not "?>". html.parser surfaces the whole thing as
# text, so markdownify faithfully prints the attributes — including build paths from
# SAP's build machine. The visible link label lives ONLY in the text= attribute, so
# these must be collapsed to that text rather than dropped: deleting one turns
# "Foreign currency balance sheet accounts, that is, the G/L accounts you manage…"
# into ", that is, the G/L accounts you manage…".
# The trailing \s* is deliberate: the portal puts a newline straight after the
# instruction, and markdownify turns that into a line break, splitting the sentence
# between the label and the comma that continues it.
_PROCESSING_INSTRUCTION_RE = re.compile(r"<\?[^>]*>\s*", re.S)
_PI_TEXT_RE = re.compile(r'\btext="([^"]*)"')
_NO_SPACE_BEFORE = ",.;:!?)]}"

# Customizing paths are rendered as label/gif/label/gif/…; navstep is the separator,
# navstart and navend only bracket the path. Left alone they bury the path itself in
# image markup, and the path is the whole point of the page.
_NAV_IMG_RE = re.compile(r'<img\b[^>]*?\bnav(start|step|end)\.gif\b[^>]*>', re.I)
_NAV_REPLACEMENT = {"step": " → ", "start": "", "end": ""}


def _strip_portal_artifacts(html: str) -> str:
    """Remove markup that carries no meaning for a reader of the page text.

    Everything here was observed live on help.sap.com; see the fixture in the tests.
    """
    html = _SCRIPT_STYLE_RE.sub(" ", html)
    html = _NAV_IMG_RE.sub(lambda m: _NAV_REPLACEMENT[m.group(1).lower()], html)

    def pi_to_label(match: re.Match) -> str:
        found = _PI_TEXT_RE.search(match.group(0))
        if not found:
            return " "
        label = html_mod.unescape(found.group(1))
        # The whitespace the instruction was followed by has been consumed, so put a
        # space back unless the next character is punctuation that must not be
        # preceded by one.
        nxt = match.string[match.end():match.end() + 1]
        if nxt and nxt not in _NO_SPACE_BEFORE:
            label += " "
        return label

    return _PROCESSING_INSTRUCTION_RE.sub(pi_to_label, html)


def html_to_markdown(html: str) -> str:
    """HTML fragment -> markdown. markdownify is optional: without it, a crude fallback.

    Scripts, styles and portal artifacts are cut out before conversion on purpose:
    markdownify's strip= removes the tags but keeps their text content, so raw
    JavaScript, CSS and DITA leftovers would otherwise land in the middle of the page.
    """
    html = _strip_portal_artifacts(html)

    try:
        from markdownify import markdownify
        return markdownify(html, heading_style="ATX", strip=["script", "style"]).strip()
    except Exception:
        text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", html, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_mod.unescape(text)
        return re.sub(r"[ \t]{2,}", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def cache_stats() -> dict:
    with _cache_lock:
        entries = len(_cache)
    return {"entries": entries, "ttl_seconds": CACHE_TTL}
