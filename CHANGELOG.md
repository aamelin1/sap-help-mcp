# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] — 2026-07-27

### Fixed

- The extension no longer fails to install on Windows machines that have a 32-bit
  Python. The MCPB `uv` runtime could pick up a system interpreter, and `cryptography`
  — a transitive dependency of every MCP server SDK, unused by this server — publishes
  no 32-bit Windows wheel, so uv fell back to compiling its Rust extension and failed
  for want of an MSVC linker. The bundle now starts with `--managed-python --python
  3.13`, so uv uses an interpreter of its own, matching the architecture of the
  operating system, at a version this project's CI actually tests. The trade-off is a
  one-off interpreter download on first start, even where a suitable system Python
  exists. Reported from the field; only the bundle is affected, `uvx` was already fine.

### Changed

- `uvx sap-help-mcp@latest` is now the documented command. Plain `uvx sap-help-mcp`
  resolves a version once and then reuses its cached environment, so it never picks up
  a new release; `@latest` refreshes the cache on each start.
- Documented the Claude Desktop config path for Microsoft Store installs, which
  differs from the installer's, and how to open the file in use from the app itself.
- Added a quick start above the rationale, and an option for running from a downloaded
  bundle on machines that cannot reach PyPI.
- Dropped the HTTP self-hosting section from the README. The mode is still in the code
  and described in `docs/ARCHITECTURE.md`.

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

[1.0.2]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.1
[1.0.0]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.0
