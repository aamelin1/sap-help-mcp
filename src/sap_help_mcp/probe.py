"""Live check of the online sources — run it on a machine with internet access.

The help.sap.com endpoints are undocumented and can change; this script shows what
the portal actually answers, without starting an MCP server.

    python -m sap_help_mcp.probe                       # search + read + community
    python -m sap_help_mcp.probe "document splitting"  # your own query
    python -m sap_help_mcp.probe --raw                 # print the raw URLs
"""

from __future__ import annotations

import sys

from . import community, helpportal


def main(argv: list[str] | None = None) -> int:
    # Output is meant to be pasted into a bug report, i.e. redirected to a file. On
    # Windows that drops the console's UTF-8 writer and falls back to the ANSI code
    # page, which cannot encode page text — so pin UTF-8 and never crash on a dash.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    argv = list(argv if argv is not None else sys.argv[1:])
    raw = "--raw" in argv
    if raw:
        argv.remove("--raw")
    query = argv[0] if argv else "foreign currency valuation FAGL_FCV"
    ok = True

    print(f"Query: {query!r}\n")

    print("[1/3] help.sap.com — search")
    if raw:
        print("      " + helpportal.search_url(query, product="SAP_ERP"))
    r = helpportal.search(query, product="SAP_ERP", limit=3)
    if r.get("error"):
        ok = False
        print(f"      FAILED: {r['error']}")
    else:
        print(f"      found: {r.get('found')}")
        for it in r.get("results", []):
            print(f"      - {it['title'][:70]}  [{it['product']} {it['version']}]")

    print("\n[2/3] help.sap.com — read the first page")
    first = (r.get("results") or [{}])[0].get("ref")
    if not first:
        print("      skipped: the search returned nothing")
    else:
        if raw:
            print(f"      ref: {first}")
        p = helpportal.read(first)
        if p.get("error"):
            ok = False
            print(f"      FAILED ({p.get('step')}): {p['error']}")
        else:
            print(f"      \"{p['title'][:70]}\", parts: {p['total_parts']}, "
                  f"chars in the first: {len(p['content'])}")
            print("      " + p["content"][:200].replace("\n", " "))

    print("\n[3/3] community.sap.com — search")
    if raw:
        print("      " + community.liql_url(query, limit=3))
    c = community.search(query, limit=3)
    if c.get("error"):
        ok = False
        print(f"      FAILED: {c['error']}")
    else:
        print(f"      found: {c.get('found')} "
              f"(out of {c.get('candidates_examined', 0)} candidates)")
        for it in c.get("results", []):
            print(f"      - {it['title'][:66]}  "
                  f"[{it['posted']}, +{it['kudos']}, score {it['match_score']}]")
        if c.get("partial"):
            print(f"      WARNING: {c['partial']}")

    print("\n" + ("ALL SOURCES LIVE" if ok else "FAILURES — see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
