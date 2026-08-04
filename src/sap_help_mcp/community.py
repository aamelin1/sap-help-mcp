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

from .fetcher import build_url, get_json, html_to_markdown

BASE = "https://community.sap.com"
LIQL_URL = f"{BASE}/api/2.0/search"
SELECT = ("SELECT id, subject, search_snippet, post_time, view_href, "
          "kudos.sum(weight)")

STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are",
        "how", "what", "why", "with", "not", "can", "sap", "error", "issue"}
MAX_PARALLEL = 4

# Reading a whole thread. Verified live against community.sap.com, and the shape is
# not the obvious one: `conversation.id` can be SELECTed but is rejected as a
# constraint ("Invalid query syntax", code 604) — `topic.id` is the one that filters,
# and it returns the root post together with every reply in one request.
THREAD_SELECT = ("SELECT id, subject, body, post_time, depth, is_solution, "
                 "author.login, kudos.sum(weight)")
# Same field list without is_solution. Selecting it alongside a topic.id constraint is
# the one combination not exercised by hand, so a syntax error falls back to this
# rather than failing the call: losing the solved marker beats losing the thread.
THREAD_SELECT_MINIMAL = ("SELECT id, subject, body, post_time, depth, "
                         "author.login, kudos.sum(weight)")
THREAD_LIMIT = 100
MAX_TEXT_CHARS = 12000

# Khoros puts the message id last in every URL shape the forum uses: qaq-p for
# questions, td-p for discussions, m-p for a single message, ba-p for blog articles.
MESSAGE_ID_RE = re.compile(r"-p/(\d+)")


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
        "hint": ("Snippets are truncated by the forum — the working answer is usually a few "
                 "replies down, so call sap_community_read(url) on anything promising. "
                 "This is a forum: field experience and workarounds, not the last word, so "
                 "verify against documentation or an SAP Note. match_score shows how many "
                 "query terms actually matched (subject counts more than snippet)."),
    }
    if errors:
        out["partial"] = f"Some sub-queries failed: {errors[0]}"
    if not results:
        out["note"] = ("There were candidates, but all were dropped as single-common-word "
                       "matches. Rephrase more precisely, or give one or two key terms.")
    return out


def thread_url(message_id: str, *, with_solution_flag: bool = True) -> str:
    select = THREAD_SELECT if with_solution_flag else THREAD_SELECT_MINIMAL
    liql = (f"{select} FROM messages WHERE topic.id = '{_escape(message_id)}' "
            f"ORDER BY post_time ASC LIMIT {THREAD_LIMIT}")
    return build_url(LIQL_URL, {"q": liql})


def _fetch_thread(message_id: str) -> tuple[list[dict], str | None]:
    """Messages of one thread, oldest first. Retries without is_solution if the
    instance rejects that field alongside a topic.id constraint."""
    items, err = _items(thread_url(message_id))
    if err and "syntax" in err.lower():
        items, err = _items(thread_url(message_id, with_solution_flag=False))
    return items, err


def _resolve_topic_id(message_id: str) -> tuple[str | None, str | None]:
    """The root id of the thread a message belongs to.

    Needed when the link points at a reply rather than at the thread: topic.id only
    matches the root. conversation.id is readable per message and holds exactly that
    root id, which is why it is worth a second request.
    """
    liql = (f"SELECT id, conversation.id FROM messages "
            f"WHERE id = '{_escape(message_id)}'")
    items, err = _items(build_url(LIQL_URL, {"q": liql}))
    if err:
        return None, err
    if not items:
        return None, f"community.sap.com has no message {message_id}."
    root = ((items[0].get("conversation") or {}).get("id"))
    return (str(root) if root else None), None


def _is_forum_thread(root: dict) -> bool:
    """Whether this is a question with replies rather than a published article.

    Search returns both, and they read differently: calling a blog post a "Question"
    and its lack of replies "unsolved" is simply wrong. message_type arrives on every
    message without being selected — 'forum_topic_message' for a question,
    'forum_reply_message' for a reply. The check stays loose about what a blog calls
    itself, because only the forum values have been seen for certain.
    """
    kind = str(root.get("message_type") or "")
    return "forum" in kind or "topic" in kind


def _render(messages: list[dict]) -> str:
    """The thread as markdown: the opening post, then the replies in order.

    Reply subjects are all "Re: <the question>", so they are dropped; what a reader
    needs per reply is who wrote it, when, whether it was accepted, and the text.
    """
    forum = _is_forum_thread(messages[0])
    first_label = "Question" if forum else "Article"
    reply_label = "Reply" if forum else "Comment"

    lines: list[str] = []
    for index, message in enumerate(messages):
        author = ((message.get("author") or {}).get("login") or "unknown").strip()
        posted = (message.get("post_time") or "")[:10]
        kudos = _kudos(message)
        marks = []
        if message.get("is_solution"):
            marks.append("accepted solution")
        if kudos:
            marks.append(f"+{kudos}")
        # depth is the nesting level, and a deep reply usually answers the one above
        # rather than the question, which changes how the text reads.
        depth = int(message.get("depth") or 0)
        if depth > 1:
            marks.append(f"reply depth {depth}")
        suffix = f" ({', '.join(marks)})" if marks else ""

        heading = (f"## {first_label}" if index == 0
                   else f"## {reply_label} {index}")
        lines.append(f"{heading} — {author}, {posted}{suffix}")
        body = html_to_markdown(message.get("body") or "").strip()
        lines.append(body or "_(empty)_")
        lines.append("")
    return "\n".join(lines).strip()


def read(ref: str, *, part: int = 1) -> dict:
    """A whole SAP Community thread as markdown. Always returns a dict."""
    ref = (ref or "").strip()
    match = MESSAGE_ID_RE.search(ref)
    message_id = match.group(1) if match else (ref if ref.isdigit() else "")
    if not message_id:
        return {"error": "Pass the url field from a sap_community_search result (or a "
                         "bare message id). Expected something ending in -p/<number>, "
                         f"got {ref[:80]!r}."}

    messages, err = _fetch_thread(message_id)
    if err:
        return {"error": err, "endpoint": LIQL_URL}

    # A link to a reply finds nothing, because topic.id only matches the root.
    if not messages:
        root_id, err = _resolve_topic_id(message_id)
        if err:
            return {"error": err, "endpoint": LIQL_URL}
        if root_id and root_id != message_id:
            messages, err = _fetch_thread(root_id)
            if err:
                return {"error": err, "endpoint": LIQL_URL}
    if not messages:
        return {"error": f"No thread found for message {message_id}. The post may have "
                         "been removed, or the link may not be a forum message."}

    messages.sort(key=lambda m: (m.get("post_time") or ""))
    root = messages[0]
    text = _render(messages)
    total_parts = max(1, (len(text) + MAX_TEXT_CHARS - 1) // MAX_TEXT_CHARS)
    part = max(1, min(int(part), total_parts))

    forum = _is_forum_thread(root)
    out = {
        "title": (root.get("subject") or "").strip(),
        "url": ref if ref.startswith("http") else f"{BASE}/t5/-/-/m-p/{message_id}",
        "kind": "question" if forum else "article",
        "replies": len(messages) - 1,
        "solved": any(m.get("is_solution") for m in messages),
        "part": part,
        "total_parts": total_parts,
        "content": text[(part - 1) * MAX_TEXT_CHARS: part * MAX_TEXT_CHARS],
        "source": "community.sap.com",
    }
    if total_parts > 1:
        out["more"] = (f"Part {part} of {total_parts}; next: "
                       f"sap_community_read(ref, part={part + 1}).")
    if len(messages) >= THREAD_LIMIT:
        out["truncated"] = (f"Only the first {THREAD_LIMIT} messages of this thread were "
                            "read; it is longer.")
    # Only a question can lack an accepted answer. Saying it about a blog post, or
    # about a thread nobody replied to, is noise that reads as a warning.
    if forum and not out["solved"] and out["replies"]:
        out["hint"] = ("Nothing here is marked as an accepted solution, so treat the "
                       "replies as suggestions and verify before acting on them.")
    return out
