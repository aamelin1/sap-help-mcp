# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-07-26

### Fixed

- `help_read` no longer leaks the portal's DITA toolchain into the page text. Pages
  carry XML processing instructions such as `<?sap-ot … text="…" xtrf="file:/home/…">`,
  which the HTML parser surfaces as text, so their attributes — including build paths
  from SAP's build machine — ended up in the markdown. They are now collapsed to the
  label in their `text=` attribute, which is where the visible link text actually
  lives: dropping them instead would delete the subject of the sentence.
- Customizing paths are readable again. They are rendered as a chain of labels
  separated by `navstep.gif` images, which previously appeared as image markup
  between every step; the navigation gifs are now replaced with `→`.

## [1.0.0] — 2026-07-26

First public release.

### Added

- `help_search` — live search over help.sap.com, including the Support Content
  (Expert Content wiki) space, with optional product and version filters.
- `help_read` — full page text as markdown, paginated for long pages via the
  three-step `deliverableMetadata` → `pagecontent` chain.
- `community_search` — SAP Community search with client-side relevance ranking,
  working around the Khoros LiQL `MATCHES` OR-semantics and unranked results.
- `web_status` — version, source endpoints and cache state.
- HTTP transport with bearer-token authentication and an open `/health` endpoint,
  for self-hosted deployments.
- Distribution as a PyPI package (`uvx sap-help-mcp`) and as an MCPB bundle
  (`.mcpb`, server type `uv`) for one-click installation in Claude Desktop.
- Offline test suite and `python -m sap_help_mcp.probe` for live source checks.

[1.0.1]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.1
[1.0.0]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.0
