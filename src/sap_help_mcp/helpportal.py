"""Search and read help.sap.com — the official SAP documentation portal.

The request shapes come from mcp-sap-docs (Apache 2.0,
github.com/marianfoo/mcp-sap-docs), file src/lib/sapHelp.ts: the portal is a SPA
and its own JSON endpoints are not publicly documented, so there was no point in
rediscovering them from scratch. See NOTICE.

Reading a page takes three steps — one request will not give you the full text:
    1) /http.svc/elasticsearch       search; returns the page loio and url
    2) /http.svc/deliverableMetadata by loio + product: build id, buildNo, filePath
    3) /http.svc/pagecontent         by those three: the page HTML fragment
"""

from __future__ import annotations

import re
import urllib.parse

from .fetcher import build_url, get_json, html_to_markdown

BASE = "https://help.sap.com"
SEARCH_URL = f"{BASE}/http.svc/elasticsearch"
METADATA_URL = f"{BASE}/http.svc/deliverableMetadata"
PAGE_URL = f"{BASE}/http.svc/pagecontent"

# Only the transtypes that can actually be read afterwards. PDFs cannot be opened
# through pagecontent and only add noise to the result list.
TRANSTYPES = "standard,html"
DOCS_PATH_RE = re.compile(
    r"/docs/(?P<product>[^/]+)/(?P<deliverable>[^/]+)/(?P<loio>[^/?#]+?)\.html")

MAX_TEXT_CHARS = 12000


def absolute(url: str) -> str:
    if not url:
        return ""
    return url if url.startswith("http") else BASE + ("" if url.startswith("/") else "/") + url


def search_url(query: str, *, product: str = "", version: str = "",
               limit: int = 10, language: str = "en-US") -> str:
    return build_url(SEARCH_URL, {
        "transtype": TRANSTYPES,
        "state": "PRODUCTION,TEST,DRAFT",
        "product": product,
        "version": version,
        "q": query,
        "to": str(max(0, min(int(limit), 20) - 1)),
        "area": "content",
        "advancedSearch": "0",
        "excludeNotSearchable": "1",
        "language": language,
    })


def search(query: str, *, product: str = "", version: str = "",
           limit: int = 10) -> dict:
    """Search help.sap.com. Always returns a dict, never raises."""
    if not (query or "").strip():
        return {"error": "Empty query."}
    url = search_url(query, product=product, version=version, limit=limit)
    data, err = get_json(url, referer=BASE)
    if err:
        return {"error": err, "query": query, "endpoint": SEARCH_URL}

    hits = (((data or {}).get("data") or {}).get("results")) or []
    out = []
    for h in hits[:limit]:
        page_url = absolute(h.get("url") or "")
        out.append({
            "title": (h.get("title") or "").strip(),
            "url": page_url,
            "ref": page_url,                       # pass this straight into help_read
            "product": h.get("product") or h.get("productId") or "",
            "version": h.get("version") or h.get("versionId") or "",
            "snippet": re.sub(r"<[^>]+>", "", h.get("snippet") or "").strip(),
        })
    if not out:
        return {
            "query": query, "found": 0, "results": [],
            "note": ("The portal found nothing. Try different English terms, or drop "
                     "the product filter."),
        }
    return {
        "query": query,
        "found": len(out),
        "results": out,
        "source": "help.sap.com",
        "hint": ("Full text: help_read(ref). Check the product field — the portal also "
                 "returns ByDesign and cloud editions; for ECC / S/4HANA on premise "
                 "look for SAP_ERP and SAP_S4HANA_ON_PREMISE."),
    }


def read(ref: str, *, part: int = 1) -> dict:
    """Full text of a help.sap.com page by its URL (the ref from help_search)."""
    ref = (ref or "").strip()
    m = DOCS_PATH_RE.search(ref)
    if not m:
        return {"error": "This does not look like help.sap.com/docs/<product>/<deliverable>/"
                         "<loio>.html — pass the ref field returned by help_search."}
    product_url, deliverable_url, loio = m.group("product", "deliverable", "loio")
    # urlsplit + parse_qs rather than a regex: the values are percent-encoded, and a
    # trailing #fragment must not end up glued to the version.
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(ref).query)
    version = (qs.get("version") or [""])[0]
    language = (qs.get("locale") or ["en-US"])[0]

    meta_url = build_url(METADATA_URL, {
        "product_url": product_url,
        "topic_url": f"{loio}.html",
        "version": version,
        "loadlandingpageontopicnotfound": "true",
        "deliverable_url": deliverable_url,
        "language": language,
        "deliverableInfo": "1",
        "toc": "1",
    })
    meta, err = get_json(meta_url, referer=BASE)
    if err:
        return {"error": err, "step": "deliverableMetadata"}

    mdata = (meta or {}).get("data") or {}
    deliverable = mdata.get("deliverable") or {}
    deliverable_id, build_no = deliverable.get("id"), deliverable.get("buildNo")
    file_path = mdata.get("filePath") or f"{loio}.html"
    if not deliverable_id or not build_no:
        return {"error": "The portal did not return the page build id (deliverable/buildNo). "
                         "The version may be wrong — retry with a ref that has no version "
                         "parameter.",
                "step": "deliverableMetadata"}

    page, err = get_json(build_url(PAGE_URL, {
        "deliverableInfo": "1", "deliverable_id": deliverable_id,
        "buildNo": build_no, "file_path": file_path}), referer=BASE)
    if err:
        return {"error": err, "step": "pagecontent"}

    pdata = (page or {}).get("data") or {}
    body = pdata.get("body") or ""
    if not body:
        return {"error": "The page came back empty (no body).", "step": "pagecontent"}

    text = html_to_markdown(body)
    total_parts = max(1, (len(text) + MAX_TEXT_CHARS - 1) // MAX_TEXT_CHARS)
    part = max(1, min(int(part), total_parts))
    chunk = text[(part - 1) * MAX_TEXT_CHARS: part * MAX_TEXT_CHARS]

    out = {
        "title": ((pdata.get("currentPage") or {}).get("t")
                  or deliverable.get("title") or loio),
        "url": ref,
        "product": product_url,
        "version": deliverable.get("version") or version or "latest",
        "part": part,
        "total_parts": total_parts,
        "content": chunk,
        "source": "help.sap.com",
    }
    if total_parts > 1:
        out["more"] = f"Part {part} of {total_parts}; next: help_read(ref, part={part + 1})."
    return out
