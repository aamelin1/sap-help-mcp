"""Search SAP Community through the public Khoros API (LiQL).

The request shape comes from mcp-sap-docs (Apache 2.0), src/lib/communityBestMatch.ts.
LiQL is the SQL-like query language of the Khoros platform; reading needs no auth.

The trap, confirmed live: **MATCHES treats a multi-word query as OR over the words,
and returns results unranked — newest first.** The query
'foreign currency valuation FAGL_FCV' came back full of yesterday's posts that merely
contained the word "currency", with no FAGL_FCV posts in sight at all.

Hence three things (the ranking idea also comes from mcp-sap-docs):
  1) separate queries for the "rare" terms (FAGL_FCV, UDM_MSG300, long words) against
     subjects only — otherwise a rare term never reaches the top of a broad, recent list;
  2) one broad query for the whole phrase over subject and body, for recall;
  3) merge with dedup plus our own ranking: how many query terms actually appear in the
     subject (weight 3) and in the snippet (weight 1), then kudos, then recency.
Plus a cut-off: with three or more terms in the query, posts with no subject match and
fewer than two snippet matches are dropped — that is the filter against "currency".
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from .fetcher import build_url, get_json

BASE = "https://community.sap.com"
LIQL_URL = f"{BASE}/api/2.0/search"
SELECT = ("SELECT id, subject, search_snippet, post_time, view_href, "
          "kudos.sum(weight)")

STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are",
        "how", "what", "why", "with", "not", "can", "sap", "error", "issue"}
MAX_PARALLEL = 4


def _escape(value: str) -> str:
    """Escape a LiQL string literal. Backslash first, then the quote."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def liql_url(query: str, *, limit: int = 10, subject_only: bool = False,
             min_kudos: int = 0) -> str:
    escaped = _escape(query)
    match = (f"subject MATCHES '{escaped}'" if subject_only
             else f"(subject MATCHES '{escaped}' OR body MATCHES '{escaped}')")
    kudos = f" AND kudos.sum(weight) >= {int(min_kudos)}" if min_kudos > 0 else ""
    liql = f"{SELECT} FROM messages WHERE {match} AND depth = 0{kudos} LIMIT {int(limit)}"
    return build_url(LIQL_URL, {"q": liql})


def _items(url: str) -> tuple[list[dict], str | None]:
    data, err = get_json(url)
    if err:
        return [], err
    if (data or {}).get("status") != "success":
        return [], f"The Community API returned status {(data or {}).get('status')!r}."
    return (((data or {}).get("data") or {}).get("items")) or [], None


def _terms(query: str) -> list[str]:
    return [t for t in re.split(r"[\s,;]+", query.lower())
            if len(t) > 2 and t not in STOP]


def _rare_first(terms: list[str], keep: int = 3) -> list[str]:
    """Terms worth a query of their own: identifier-looking ones first (digits or
    underscores), then the longest remaining words."""
    ident = [t for t in terms if re.search(r"[\d_]", t)]
    rest = sorted((t for t in terms if t not in ident), key=len, reverse=True)
    return (ident + rest)[:keep]


def _kudos(item: dict) -> int:
    k = item.get("kudos")
    if isinstance(k, dict):
        return int((k.get("sum") or {}).get("weight") or 0)
    return 0


def search(query: str, *, limit: int = 10, min_kudos: int = 0) -> dict:
    """Search Community posts, ranked on our side. Always returns a dict."""
    query = (query or "").strip()
    if not query:
        return {"error": "Empty query."}
    terms = _terms(query)
    fetch_limit = max(limit * 3, 25)

    urls = [liql_url(query, limit=fetch_limit, min_kudos=min_kudos)]
    urls += [liql_url(t, limit=fetch_limit, subject_only=True, min_kudos=min_kudos)
             for t in _rare_first(terms)]

    errors: list[str] = []
    merged: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        for items, err in pool.map(_items, urls):
            if err:
                errors.append(err)
                continue
            for it in items:
                post_id = it.get("id")
                if post_id is None:            # no id, nothing to dedupe on
                    continue
                merged.setdefault(str(post_id), it)

    if not merged:
        if errors:
            return {"error": errors[0], "query": query, "endpoint": LIQL_URL}
        return {"query": query, "found": 0, "results": [],
                "note": ("Nothing found. The forum matches literally — try the exact error "
                         "text, a message number, or a transaction name.")}

    scored = []
    for it in merged.values():
        subject = (it.get("subject") or "").lower()
        snippet = re.sub(r"<[^>]+>", " ", it.get("search_snippet") or "").lower()
        in_subj = sum(1 for t in terms if t in subject)
        in_snip = sum(1 for t in terms if t in snippet)
        if len(terms) >= 3 and in_subj == 0 and in_snip < 2:
            continue                        # noise: matched one common word only
        scored.append((in_subj * 3 + in_snip, in_subj, _kudos(it),
                       it.get("post_time") or "", it))
    # Two passes rather than one composite key: Python's sort is stable, so recency
    # ends up as the third criterion without having to invert a date string.
    scored.sort(key=lambda x: x[3], reverse=True)
    scored.sort(key=lambda x: (-x[0], -x[2]))

    results = []
    for score, _in_subj, kudos, _posted, it in scored[:limit]:
        href = it.get("view_href") or ""
        results.append({
            "title": (it.get("subject") or "").strip(),
            "url": href if href.startswith("http") else BASE + href,
            "posted": (it.get("post_time") or "")[:10],
            "kudos": kudos,
            "match_score": score,
            "snippet": re.sub(r"<[^>]+>", "", it.get("search_snippet") or "").strip(),
        })

    out = {
        "query": query,
        "found": len(results),
        "candidates_examined": len(merged),
        "results": results,
        "source": "community.sap.com",
        "hint": ("This is a forum: field experience and workarounds, not the last word — "
                 "verify against documentation or an SAP Note. match_score shows how many "
                 "query terms actually matched (subject counts more than snippet)."),
    }
    if errors:
        out["partial"] = f"Some sub-queries failed: {errors[0]}"
    if not results:
        out["note"] = ("There were candidates, but all were dropped as single-common-word "
                       "matches. Rephrase more precisely, or give one or two key terms.")
    return out
