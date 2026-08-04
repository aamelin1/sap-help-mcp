"""MCP tool declarations. The logic lives in helpportal.py and community.py; this
module holds only signatures, the descriptions the model reads, and error trapping.

The rule that _safe() exists for: a network problem MUST come back as a structured
{"error": ...} response rather than an exception — one failed call must never take
the server down.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from . import __version__, community, helpportal
from .fetcher import cache_stats


def _safe(fn, *args, **kwargs) -> dict:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:                       # noqa: BLE001 — networking, anything goes
        return {"error": f"Source unavailable: {exc}"}


def register(mcp) -> None:
    """Register every tool on the given FastMCP server."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def sap_help_search(
        query: str = Field(description=(
            "Query IN ENGLISH against SAP documentation. Feature names, transaction "
            "codes, IMG paths, field names and message numbers all work.")),
        product: Optional[str] = Field(None, description=(
            "Restrict to a product line: SAP_ERP (ECC 6.0), SAP_S4HANA_ON_PREMISE, "
            "SAP_S4HANA_CLOUD, SUPPORT_CONTENT (the Expert Content wiki — support "
            "FAQs and troubleshooting guides). Without a filter the portal returns "
            "every line including ByDesign, so read the product field of each result.")),
        version: Optional[str] = Field(None, description=(
            "Pin a version exactly as a previous search reported it (e.g. 6.18.latest). "
            "Rarely needed.")),
        limit: int = Field(8, ge=1, le=20, description="How many results to return."),
    ) -> dict:
        """PRIMARY search over SAP documentation: help.sap.com, queried live.

        Call this FIRST — before a web search, and before answering from memory — for
        any question about standard SAP ERP / S/4HANA: an error or message code, "how
        do I configure", a customizing path, the behaviour of a transaction or report,
        "what is the difference between". The index covers both the official
        documentation and the Support Content space: the FAQs and troubleshooting
        guides written by SAP support.

        Next step: sap_help_read(ref) for the full page text. If the documentation is
        silent on real-world practice, try sap_community_search.
        """
        return _safe(helpportal.search, query, product=product or "",
                     version=version or "", limit=limit)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def sap_help_read(
        ref: str = Field(description=(
            "URL of a help.sap.com page, taken from the ref field of a "
            "sap_help_search result.")),
        part: int = Field(1, ge=1, description=(
            "Part number for long pages (see total_parts in the response).")),
    ) -> dict:
        """Read a full help.sap.com page as markdown — use after sap_help_search."""
        return _safe(helpportal.read, ref, part=part)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def sap_community_search(
        query: str = Field(description=(
            "Query IN ENGLISH. The forum matches literally: exact error text, a message "
            "number, or a transaction or report name works best.")),
        limit: int = Field(8, ge=1, le=25, description="How many posts to return."),
        min_kudos: int = Field(0, ge=0, le=10, description=(
            "Minimum kudos: 0 for everything, 1-2 to drop unanswered posts, "
            "5+ for community-validated answers only.")),
    ) -> dict:
        """Search SAP Community: blogs, Q&A and discussions — practice and workarounds.

        Call this when the official documentation is silent or when you need real
        implementation experience: "has anyone hit this, and what fixed it". It is a
        forum, so verify anything found here against documentation or an SAP Note
        before recommending it. The match_score field shows how many query terms
        actually matched.
        """
        return _safe(community.search, query, limit=limit, min_kudos=min_kudos)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def sap_community_read(
        ref: str = Field(description=(
            "URL of a community.sap.com post, taken from the url field of a "
            "sap_community_search result. A bare message id also works.")),
        part: int = Field(1, ge=1, description=(
            "Part number for long threads (see total_parts in the response).")),
    ) -> dict:
        """Read a whole SAP Community thread — the question and every reply.

        Call this on anything sap_community_search turns up that looks relevant. The
        search only returns a truncated snippet of the opening post, and on a forum
        the answer that actually worked is usually several replies down, sometimes
        contradicting the question's own assumptions.

        Replies come in order, each with its author, date, kudos, and a marker when
        the community accepted it as the solution. The solved field says whether an
        accepted answer exists at all — if it does not, treat the thread as
        suggestions rather than as an answer.
        """
        return _safe(community.read, ref, part=part)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def sap_help_status() -> dict:
        """Server status: version, source endpoints and cache state."""
        return {
            "version": __version__,
            "search_endpoint": helpportal.SEARCH_URL,
            "read_endpoints": [helpportal.METADATA_URL, helpportal.PAGE_URL],
            "community_endpoint": community.LIQL_URL,
            "cache": cache_stats(),
            "note": ("The help.sap.com endpoints are not publicly documented and may "
                     "change. Live check: python -m sap_help_mcp.probe"),
        }
