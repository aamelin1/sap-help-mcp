#!/usr/bin/env python3
"""sap-help-mcp — an MCP server that searches SAP Help Portal and SAP Community.

Five tools:
    sap_help_search       search help.sap.com (documentation + Support Content wiki)
    sap_help_read         full page text from help.sap.com as markdown
    sap_community_search  search the forum: blogs, Q&A, discussions
    sap_community_read    a whole forum thread — question and every reply
    sap_help_status       endpoints, version and cache state

Every name carries the sap_ prefix on purpose: an MCP server does not know what else
lives in the user's client, and generic names collide. Renamed in 1.1.0.

What is deliberately absent, and why:
    * SAP Notes — served by a separate MCP server, github.com/aamelin1/sap-notes-mcp:
      reading Notes needs a personal S-user, and this server holds no credentials of
      any kind.
    * A local knowledge base — help.sap.com indexes the SUPPORT_CONTENT space itself
      and returns the same pages with full text, so a local copy was pure duplication.

Running it:
    sap-help-mcp                                        # stdio, for Claude Desktop
    MCP_TRANSPORT=http MCP_TOKEN=<secret> sap-help-mcp  # for a VPS

In HTTP mode every request must carry Authorization: Bearer <secret>; /health stays
open for monitoring. Expose it only behind a TLS-terminating reverse proxy.
"""

from __future__ import annotations

import hmac
import os
import sys

from fastmcp import FastMCP

from . import __version__
from .tools import register

INSTRUCTIONS = """
Search two live SAP sources.

help.sap.com — the official documentation for every SAP product, plus the Support
Content space (the SAP support Expert Content wiki: FAQs, troubleshooting guides and
customizing instructions with links to SAP Notes and KBAs).

community.sap.com — the forum: blogs, Q&A, discussions. Implementation practice and
workarounds that never make it into the documentation.

QUERIES MUST BE IN ENGLISH — both sources are English-only. Translate the user's
question yourself, into SAP terminology rather than word for word ('переоценка
валюты' -> 'foreign currency valuation', 'MVZ' -> 'cost center'). When the results
are weak, make one or two more calls with different phrasings — that works better
than anything else.

Order of use: sap_help_search -> sap_help_read for the full text; sap_community_search
-> sap_community_read when you need field experience or the documentation is silent.

Both searches return snippets, not answers. Reading is not optional: a documentation
page states the rule, and a forum thread usually hides the fix a few replies down. SAP
Note numbers found along the way can be read through a separate MCP server for Notes.
"""

# show_banner=False below, plus this: FastMCP's startup banner phones pypi.org to
# check for a newer version of itself and caches the answer on disk. That costs a
# round trip on every client launch, breaks the "nothing written to disk, no calls
# beyond the SAP portals" promise, and on a machine with a SOCKS proxy configured it
# raises before the server ever serves a request.
try:
    import fastmcp as _fastmcp

    _fastmcp.settings.check_for_updates = "off"
except Exception:                              # noqa: BLE001 — setting may be renamed
    pass

mcp = FastMCP(name="sap-help", version=__version__,
              instructions=INSTRUCTIONS.strip())
register(mcp)


def _add_health_route() -> None:
    """GET /health for monitoring in HTTP mode. Optional: skipped if the installed
    FastMCP does not expose custom routes."""
    try:
        from starlette.responses import JSONResponse

        @mcp.custom_route("/health", methods=["GET"])
        async def health(_request):            # noqa: ANN001 — starlette Request
            return JSONResponse({"status": "ok", "version": __version__})
    except Exception as exc:                   # noqa: BLE001
        print(f"[sap-help-mcp] /health not registered: {exc}", file=sys.stderr)


def _bearer_middleware(token: str) -> list:
    """Require Authorization: Bearer <token> on every request; /health stays open.

    Compared with hmac.compare_digest: a plain == returns on the first mismatching
    character, so response timing could in theory leak the token one byte at a time.
    Both sides are encoded to bytes because compare_digest rejects non-ASCII str.
    """
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    expected = f"Bearer {token}".encode()

    class BearerAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path.rstrip("/") == "/health":
                return await call_next(request)
            got = request.headers.get("authorization", "").encode("utf-8", "replace")
            if not hmac.compare_digest(got, expected):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    return [Middleware(BearerAuth)]


LOOPBACK = {"127.0.0.1", "::1", "localhost", "0:0:0:0:0:0:0:1"}


def main() -> None:
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"sap-help-mcp {__version__}")
        return
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport in ("", "stdio"):
        mcp.run(show_banner=False)
        return
    if transport != "http":
        raise SystemExit(f"MCP_TRANSPORT must be 'stdio' or 'http', got {transport!r}")

    host = os.environ.get("MCP_HOST", "127.0.0.1").strip()
    raw_port = os.environ.get("MCP_PORT", "8010").strip()
    if not raw_port.isdigit() or not 1 <= int(raw_port) <= 65535:
        raise SystemExit(f"MCP_PORT must be a port number, got {raw_port!r}")

    token = os.environ.get("MCP_TOKEN", "")
    if not token and host not in LOOPBACK:
        raise SystemExit(
            f"Refusing to serve HTTP on {host} without MCP_TOKEN — that would be an "
            "open MCP server. Set MCP_TOKEN, or bind to 127.0.0.1.")

    _add_health_route()
    kwargs: dict = {"transport": "http", "host": host, "port": int(raw_port),
                    "show_banner": False}
    if token:
        kwargs["middleware"] = _bearer_middleware(token)
    else:
        print("[sap-help-mcp] note: no MCP_TOKEN, so this listener is unauthenticated; "
              "bound to loopback only.", file=sys.stderr)
    mcp.run(**kwargs)


if __name__ == "__main__":
    main()
