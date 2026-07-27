"""Offline smoke tests: request shapes, ref parsing, ranking, server assembly.

    pytest                        # or: uv run pytest
Live source checks are separate:  python -m sap_help_mcp.probe
"""

from __future__ import annotations

import urllib.parse
from unittest import mock

import pytest

from sap_help_mcp import community as C
from sap_help_mcp import helpportal as H

# --------------------------------------------------------------- help.sap.com


@pytest.mark.parametrize("param", [
    "transtype=standard%2Chtml",
    "state=PRODUCTION%2CTEST%2CDRAFT",
    "product=SAP_ERP",
    "q=document+splitting",
    "to=9",
    "area=content",
    "advancedSearch=0",
    "excludeNotSearchable=1",
    "language=en-US",
])
def test_help_search_url_carries_portal_parameters(param):
    """Shape verified against mcp-sap-docs and against the live portal."""
    assert param in H.search_url("document splitting", product="SAP_ERP", limit=10)


def test_ref_is_split_into_product_deliverable_loio():
    ref = ("https://help.sap.com/docs/SAP_ERP/17ec785ed229/8450d7531a4d.html"
           "?locale=en-US&version=6.18.latest")
    m = H.DOCS_PATH_RE.search(ref)
    assert m is not None
    assert m.group("product") == "SAP_ERP"
    assert m.group("deliverable") == "17ec785ed229"
    assert m.group("loio") == "8450d7531a4d"


def test_broken_ref_returns_structured_error():
    assert "error" in H.read("not a link")


def test_empty_query_returns_structured_error():
    assert "error" in H.search("   ")


# ------------------------------------------------------------------ community


def test_liql_query_is_assembled_correctly():
    url = C.liql_url("FBRA reset", limit=3, subject_only=True, min_kudos=2)
    q = urllib.parse.unquote(
        urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0])
    assert q.startswith("SELECT id, subject")
    assert "subject MATCHES 'FBRA reset'" in q
    assert "depth = 0" in q
    assert "kudos.sum(weight) >= 2" in q
    assert q.endswith("LIMIT 3")


def test_liql_literals_are_escaped():
    q = C.liql_url("O'Brien \\ test")
    assert "O\\'Brien" in urllib.parse.unquote(q)


def test_stopwords_dropped_identifiers_kept():
    assert C._terms("how to fix the FAGL_FCV error") == ["fix", "fagl_fcv"]


def test_identifiers_get_their_own_query_first():
    assert C._rare_first(
        ["foreign", "currency", "valuation", "fagl_fcv"])[0] == "fagl_fcv"


NOISE = {"id": 1, "subject": "Mass update group currency amounts",
         "search_snippet": "currency fields", "post_time": "2026-07-24T10:00:00",
         "view_href": "/t5/x/1", "kudos": {"sum": {"weight": 0}}}
TARGET = {"id": 2, "subject": "FAGL_FCV valuation of open items in foreign currency",
          "search_snippet": "program FAGL_FCV foreign currency valuation",
          "post_time": "2020-01-01T10:00:00", "view_href": "/t5/x/2",
          "kudos": {"sum": {"weight": 4}}}


def test_rare_term_beats_fresh_noise():
    """LiQL MATCHES is OR-over-words and returns newest first, so we rank ourselves:
    the post about the rare term must outrank recent single-word noise."""
    with mock.patch.object(C, "_items", lambda url: ([NOISE, TARGET], None)):
        r = C.search("foreign currency valuation FAGL_FCV", limit=5)
    assert r["found"] > 0
    assert "FAGL_FCV" in r["results"][0]["title"]
    assert r["results"][0]["match_score"] > r["results"][-1]["match_score"]


def test_single_common_word_match_is_filtered_out():
    with mock.patch.object(C, "_items", lambda url: ([NOISE], None)):
        r = C.search("asset revaluation index series", limit=5)
    assert r["found"] == 0
    assert "note" in r


def test_network_failure_becomes_structured_error():
    with mock.patch.object(C, "_items", lambda url: ([], "the portal is down")):
        r = C.search("anything", limit=5)
    assert "error" in r


# --------------------------------------------------------------- MCP assembly


def test_server_exposes_exactly_four_tools():
    """No network: the one tool call here is served by a stubbed fetcher."""
    import asyncio

    from fastmcp import Client

    from sap_help_mcp import fetcher, server

    fake_hit = {"data": {"results": [{
        "title": "Customizing of Document Splitting",
        "url": "/docs/SAP_ERP/17ec785ed229/6178d0531d8b.html?version=6.18.latest",
        "product": "SAP ERP", "version": "6.0 EHP8", "snippet": "<b>Use</b> ..."}]}}

    async def run():
        async with Client(server.mcp) as c:
            tools = sorted(t.name for t in await c.list_tools())
            assert tools == ["community_search", "help_read",
                             "help_search", "web_status"]

            status = await c.call_tool("web_status", {})
            assert "help.sap.com" in status.data["help_search_endpoint"]
            assert status.data["version"]

            with mock.patch.object(H, "get_json",
                                   lambda url, **kw: (fake_hit, None)):
                res = await c.call_tool("help_search",
                                        {"query": "document splitting", "limit": 1})
            assert res.data["found"] == 1
            assert res.data["results"][0]["ref"].startswith("https://help.sap.com/docs/")

    asyncio.run(run())
    assert fetcher.cache_stats()["entries"] >= 0    # cache survived the round trip


def test_scripts_and_styles_never_reach_the_markdown():
    """markdownify's strip= drops the tags but keeps their text, so they are cut out
    before conversion. Regression guard for raw JS landing in help_read output."""
    from sap_help_mcp.fetcher import html_to_markdown

    md = html_to_markdown(
        '<p>Before</p><script>var s=1;alert("boom")</script>'
        '<style>.a{color:red}</style><p>After</p>')
    assert "Before" in md and "After" in md
    assert "alert" not in md and "color:red" not in md


# Taken from help.sap.com, page 8450d7531a4d424de10000000a174cb4 (SAP_ERP
# 6.18.latest), captured 2026-07-26; only the xtrf path is abridged. Two portal
# artifacts in one fragment: a DITA processing instruction, and a customizing path
# built out of gifs.
#
# The newline after the instruction matters and must not be tidied away — it is what
# markdownify turns into a line break, splitting "Foreign currency balance sheet
# accounts" from the ", that is, …" that continues the sentence.
REAL_PAGE_FRAGMENT = (
    '<ul class="ul"><li class="li"><p class="p"> '
    '<?sap-ot O2O class="- topic/xref " href="0444d7531a4d424de10000000a174cb4.xml"'
    ' text="Foreign currency balance sheet accounts" desc="" xtrc="xref:1"'
    ' xtrf="file:/home/builder/src/dita-all/kid1718795600684/loio17ec785ed229_en-US/'
    'src/content/localization/en-us/8450d7531a4d424de10000000a174cb4.xml"'
    ' output-class="xref" outputTopicFile="file:/home/builder/tp.net.sf.dita-ot/2.3/'
    'plugins/org.dita.html5/xsl/map2html5Content.xsl" >'
    '\n, that is, the G/L accounts that you manage in foreign currency.</p></li></ul>'
    '<p class="p"><span class="ph menucascade">'
    '<img src="themes/sap-light/img/navstart.gif" alt="Start of the navigation path" '
    'title="Start of the navigation path">'
    '<span class="ph uicontrol">Financial Accounting (New)</span>&nbsp;'
    '<img src="themes/sap-light/img/navstep.gif" alt="Next navigation step" '
    'title="Next navigation step">&nbsp;'
    '<span class="ph uicontrol">Periodic Processing</span>&nbsp;'
    '<img src="themes/sap-light/img/navend.gif" alt="End of the navigation path" '
    'title="End of the navigation path"></span></p>'
)


def test_dita_processing_instruction_collapses_to_its_label():
    """The visible link text lives only in the PI's text= attribute, so dropping the
    instruction would silently delete the subject of the sentence."""
    from sap_help_mcp.fetcher import html_to_markdown

    md = html_to_markdown(REAL_PAGE_FRAGMENT)
    assert "Foreign currency balance sheet accounts, that is, the G/L accounts" in md


def test_no_portal_plumbing_survives_into_the_markdown():
    from sap_help_mcp.fetcher import html_to_markdown

    md = html_to_markdown(REAL_PAGE_FRAGMENT)
    for leak in ("sap-ot", "/home/builder", "map2html5Content", "outputTopicFile",
                 "xtrf", "navstep.gif", "navstart.gif", "navend.gif", "themes/"):
        assert leak not in md, f"{leak!r} leaked into the page text"


def test_customizing_path_reads_as_a_path():
    from sap_help_mcp.fetcher import html_to_markdown

    md = html_to_markdown(REAL_PAGE_FRAGMENT)
    assert "Financial Accounting (New) → Periodic Processing" in " ".join(md.split())


def test_ref_query_parsing_survives_a_fragment():
    ref = ("https://help.sap.com/docs/SAP_ERP/17ec785ed229/8450d7531a4d.html"
           "?locale=en-US&version=6.18.latest#section-2")
    captured = {}

    def fake_get_json(url, **kw):
        captured["url"] = url
        return None, "stop here"

    with mock.patch.object(H, "get_json", fake_get_json):
        H.read(ref)
    assert "version=6.18.latest&" in captured["url"] + "&"
    assert "section-2" not in captured["url"]
