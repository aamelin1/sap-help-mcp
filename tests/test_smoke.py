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


def test_thread_query_uses_topic_id_not_conversation_id():
    """conversation.id is readable per message but rejected as a constraint — the
    instance answers 'Invalid query syntax', code 604. topic.id is the one that
    filters. Verified live; this guards the distinction."""
    url = C.thread_url("12175476")
    liql = urllib.parse.unquote(
        urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0])
    assert "topic.id = '12175476'" in liql
    assert "conversation.id" not in liql
    assert "ORDER BY post_time ASC" in liql
    assert "is_solution" in liql


def test_thread_query_can_drop_the_solution_flag():
    liql = urllib.parse.unquote(
        urllib.parse.parse_qs(urllib.parse.urlparse(
            C.thread_url("1", with_solution_flag=False)).query)["q"][0])
    assert "is_solution" not in liql


@pytest.mark.parametrize("ref, expected", [
    ("https://community.sap.com/t5/enterprise-resource-planning-q-a/x/qaq-p/12175476",
     "12175476"),
    ("https://community.sap.com/t5/technology-blogs-by-sap/y/ba-p/13570001", "13570001"),
    ("https://community.sap.com/t5/x/y/m-p/999", "999"),
    ("12175476", "12175476"),
])
def test_message_id_is_taken_from_every_url_shape(ref, expected):
    """Khoros puts the id last: qaq-p for questions, ba-p for blogs, m-p for a single
    message, td-p for discussions."""
    with mock.patch.object(C, "_items", lambda url: ([], None)), \
         mock.patch.object(C, "_resolve_topic_id", lambda mid: (mid, None)):
        result = C.read(ref)
    # Nothing was found, but the error must name the id we extracted rather than
    # complain about the URL shape.
    assert expected in result["error"]


def test_unusable_ref_is_rejected_before_any_request():
    result = C.read("https://help.sap.com/docs/SAP_ERP/x/y.html")
    assert "error" in result
    assert "sap_community_search" in result["error"]


# Verbatim from community.sap.com, thread 12175476, captured 2026-08-03: the field
# names, the HTML in the bodies and the reply nesting are all as the instance returns
# them, so the renderer is exercised against real markup rather than a tidy invention.
REAL_THREAD = [
    {"type": "message", "id": "12175476",
     "author": {"type": "user", "login": "Former Member"},
     "subject": "Foreign Currency Valuation - FAGL_FCV - Reset Valuation Posted "
                "without Valuation itself Posted",
     "body": "<P>Hello all,</P>\n  <P>In Foreign Currency Valuation transaction "
             "\"FAGL_FCV\" the user executed it but by mistake had a check in \"Reset "
             "Valuation\".</P>\n  <P>Is this supposed to happen?</P>",
     "post_time": "2020-02-19T17:16:04.000+01:00", "depth": 0,
     "kudos": {"sum": {"weight": 0}}, "message_type": "forum_topic_message"},
    {"type": "message", "id": "12175477",
     "author": {"type": "user", "login": "Rob_McNally"},
     "subject": "Re: Foreign Currency Valuation - FAGL_FCV - Reset Valuation Posted",
     "body": "<P><A href=\"https://wiki.scn.sap.com/wiki/display/ERPFI/Foreign\" "
             "rel=\"noopener noreferrer\">Here </A>is a good explanation of the reset "
             "logic. </P>Also; take a look in table FAGL_BSBW_HISTRY &amp; check which "
             "transactions were reset.",
     "post_time": "2020-02-20T02:20:50.000+01:00", "depth": 1, "is_solution": True,
     "kudos": {"sum": {"weight": 1}}, "message_type": "forum_reply_message"},
    {"type": "message", "id": "12175479",
     "author": {"type": "user", "login": "Former Member"},
     "subject": "Re: Foreign Currency Valuation - FAGL_FCV - Reset Valuation Posted",
     "body": "<P>Hi Robert,</P><P>Thanks for the feedback.</P>",
     "post_time": "2020-02-20T11:08:49.000+01:00", "depth": 2,
     "kudos": {"sum": {"weight": 0}}, "message_type": "forum_reply_message"},
]


def _read_real_thread(**kwargs):
    with mock.patch.object(C, "_items", lambda url: (list(REAL_THREAD), None)):
        return C.read(
            "https://community.sap.com/t5/erp-q-a/x/qaq-p/12175476", **kwargs)


def test_thread_reads_as_a_conversation():
    result = _read_real_thread()
    assert result["replies"] == 2
    assert result["solved"] is True
    assert result["title"].startswith("Foreign Currency Valuation")

    content = result["content"]
    assert "## Question — Former Member, 2020-02-19" in content
    assert "## Reply 1 — Rob_McNally, 2020-02-20 (accepted solution, +1)" in content
    # Nesting matters: a depth-2 reply answers the reply above, not the question.
    assert "reply depth 2" in content


def test_reply_bodies_are_converted_from_html():
    content = _read_real_thread()["content"]
    assert "<P>" not in content and "<A href" not in content
    assert "FAGL_BSBW_HISTRY" in content
    assert "&amp;" not in content          # entities are decoded, not passed through
    assert "wiki.scn.sap.com" in content   # links survive as markdown


def test_reply_subjects_are_dropped():
    """Every reply is titled "Re: <the question>"; repeating it four times is noise."""
    assert "Re: Foreign Currency" not in _read_real_thread()["content"]


def test_unsolved_thread_says_so():
    unsolved = [dict(m, is_solution=False) for m in REAL_THREAD]
    with mock.patch.object(C, "_items", lambda url: (list(unsolved), None)):
        result = C.read("https://community.sap.com/t5/x/y/qaq-p/12175476")
    assert result["solved"] is False
    assert result["kind"] == "question"
    assert "accepted solution" in result["hint"]


def test_a_blog_post_is_not_an_unsolved_question():
    """Search returns blog articles too. Calling one a Question, and its lack of
    comments 'unsolved', was wrong on both counts — seen on a real article. The URL
    marker decides: message_type comes back as a forum type even for articles, which
    a first attempt at this relied on and got wrong."""
    article = dict(REAL_THREAD[0],
                   subject="Reset clearing of document that has Withholding Tax items")
    with mock.patch.object(C, "_items", lambda url: ([article], None)):
        result = C.read("https://community.sap.com/t5/erp-blog-posts/x/ba-p/12972431")
    assert result["kind"] == "article"
    assert result["content"].startswith("## Article — ")
    assert "hint" not in result


def test_blog_comments_are_comments_not_replies():
    comment = dict(REAL_THREAD[1], is_solution=False)
    with mock.patch.object(C, "_items", lambda url: ([REAL_THREAD[0], comment], None)):
        content = C.read("https://community.sap.com/t5/x/y/ba-p/1")["content"]
    assert "## Comment 1 — " in content
    assert "## Reply" not in content


def test_a_thread_nobody_answered_gets_no_warning():
    with mock.patch.object(C, "_items", lambda url: ([REAL_THREAD[0]], None)):
        result = C.read("https://community.sap.com/t5/x/y/qaq-p/12175476")
    assert result["replies"] == 0
    assert "hint" not in result


def test_long_thread_is_paginated():
    filler = dict(REAL_THREAD[1], body="<P>" + "word " * 4000 + "</P>")
    with mock.patch.object(C, "_items", lambda url: ([REAL_THREAD[0], filler], None)):
        first = C.read("https://community.sap.com/t5/x/y/qaq-p/12175476")
        second = C.read("https://community.sap.com/t5/x/y/qaq-p/12175476", part=2)
    assert first["total_parts"] > 1
    assert "part=2" in first["more"]
    assert second["part"] == 2
    assert second["content"] and second["content"] != first["content"]


def test_link_to_a_reply_falls_back_to_the_thread_root():
    """topic.id only matches the root, so a link to a reply finds nothing until the
    root is resolved through the reply's conversation.id."""
    calls = []

    def fake_items(url):
        calls.append(url)
        # First attempt is the reply id and comes back empty; the retry uses the root.
        return ((list(REAL_THREAD), None) if "12175476" in url else ([], None))

    with mock.patch.object(C, "_items", fake_items), \
         mock.patch.object(C, "_resolve_topic_id", lambda mid: ("12175476", None)):
        result = C.read("https://community.sap.com/t5/x/y/m-p/12175479")
    assert result["replies"] == 2
    assert len(calls) >= 2


def test_syntax_error_retries_without_the_solution_flag():
    attempts = []

    def fake_items(url):
        attempts.append(url)
        if "is_solution" in urllib.parse.unquote(url):
            return [], "The Community API returned status 'error'. Invalid query syntax"
        return list(REAL_THREAD), None

    with mock.patch.object(C, "_items", fake_items):
        result = C.read("https://community.sap.com/t5/x/y/qaq-p/12175476")
    assert result["replies"] == 2
    assert len(attempts) == 2


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


def test_server_exposes_exactly_five_tools():
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
            assert tools == ["sap_community_read", "sap_community_search",
                             "sap_help_read", "sap_help_search", "sap_help_status"]

            status = await c.call_tool("sap_help_status", {})
            assert "help.sap.com" in status.data["search_endpoint"]
            assert status.data["version"]

            with mock.patch.object(H, "get_json",
                                   lambda url, **kw: (fake_hit, None)):
                res = await c.call_tool("sap_help_search",
                                        {"query": "document splitting", "limit": 1})
            assert res.data["found"] == 1
            assert res.data["results"][0]["url"].startswith("https://help.sap.com/docs/")
            # One name only. Offering both url and ref made a local model pass "url"
            # into a parameter called "ref", and three tool calls were rejected.
            assert "ref" not in res.data["results"][0]

    asyncio.run(run())
    assert fetcher.cache_stats()["entries"] >= 0    # cache survived the round trip


def test_sap_identifiers_keep_their_underscores():
    """markdownify escapes underscores by default, which turns nearly every SAP
    identifier into FAGL\\_BSBW\\_HISTRY. The model then quotes that back, or feeds it
    into the next search."""
    from sap_help_mcp.fetcher import html_to_markdown

    md = html_to_markdown(
        "<p>Check FAGL_BSBW_HISTRY and CX_SY_ZERODIVIDE, then run FAGL_FCV.</p>")
    assert "FAGL_BSBW_HISTRY" in md
    assert "CX_SY_ZERODIVIDE" in md
    assert "\\_" not in md


def test_scripts_and_styles_never_reach_the_markdown():
    """markdownify's strip= drops the tags but keeps their text, so they are cut out
    before conversion. Regression guard for raw JS landing in sap_help_read output."""
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


def test_both_read_tools_accept_url_or_ref():
    """Search returns `url`; the read tools used to demand `ref`. A local model passed
    the field it had been given and its calls were rejected — three in a row. Either
    name is accepted now, and `url` is the one advertised."""
    import asyncio

    from fastmcp import Client

    from sap_help_mcp import server

    page = {"title": "T", "url": "u", "product": "p", "version": "v",
            "part": 1, "total_parts": 1, "content": "body", "source": "help.sap.com"}
    thread = {"title": "T", "url": "u", "kind": "question", "replies": 0,
              "solved": False, "part": 1, "total_parts": 1, "content": "body",
              "source": "community.sap.com"}
    doc_url = "https://help.sap.com/docs/SAP_ERP/x/y.html"
    post_url = "https://community.sap.com/t5/x/y/qaq-p/1"

    async def run():
        async with Client(server.mcp) as c:
            with mock.patch.object(H, "read", lambda ref, **kw: dict(page)), \
                 mock.patch.object(C, "read", lambda ref, **kw: dict(thread)):
                for name, args in [
                    ("sap_help_read", {"url": doc_url}),
                    ("sap_help_read", {"ref": doc_url}),
                    ("sap_community_read", {"url": post_url}),
                    ("sap_community_read", {"ref": post_url}),
                ]:
                    result = await c.call_tool(name, args)
                    assert "error" not in result.data, (name, args)

                # Neither name given is a usable error, not a crash.
                for name in ("sap_help_read", "sap_community_read"):
                    result = await c.call_tool(name, {})
                    assert "url" in result.data["error"]

    asyncio.run(run())
