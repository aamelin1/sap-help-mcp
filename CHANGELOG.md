# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] — 2026-07-27

### Fixed

- Second attempt at the Windows install failure below. The interpreter is now requested
  through `.python-version` and `tool.uv.python-preference`, files uv reads whenever it
  operates on the bundle directory — which is what the install step does. The 1.0.2
  attempt put the flags in the manifest's `mcp_config`, which only governs launching an
  already-installed server, so the install still ran against the system's 32-bit
  CPython 3.11.

  Confirmed on the reporting host: uv now resolves a 64-bit interpreter and no longer
  attempts to compile `cryptography`. On a 64-bit machine the only visible change is
  that the bundle downloads a managed CPython 3.13 on first use instead of borrowing a
  system one.

### Documented

- Troubleshooting for `Missing expected target directory for Python minor version link`,
  a uv bug on Windows ([astral-sh/uv#19622](https://github.com/astral-sh/uv/issues/19622))
  that surfaces once uv starts managing its own interpreter: a dangling junction in its
  Python store which uv cannot repair, and the two commands that clear it.

## [1.0.2] — 2026-07-27

### Fixed

- Attempted to fix an extension install failure on Windows machines that have a 32-bit
  Python: `cryptography` — a transitive dependency of every MCP server SDK, unused by
  this server — publishes no 32-bit Windows wheel, so uv compiled its Rust extension
  and failed for want of an MSVC linker. **This attempt did not work**: the flags were
  added to the manifest's `mcp_config`, which the install step does not consult. Use
  option B on affected machines. Only the bundle is affected; `uvx` was always fine.

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

[1.0.3]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.3
[1.0.2]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.2
[1.0.1]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.1
[1.0.0]: https://github.com/aamelin1/sap-help-mcp/releases/tag/v1.0.0
