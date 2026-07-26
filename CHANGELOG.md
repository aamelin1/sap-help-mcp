# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.0
