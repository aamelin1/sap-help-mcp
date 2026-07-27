# CLAUDE.md — sap-help-mcp

MCP server that searches help.sap.com and SAP Community. Design rationale lives in
`docs/ARCHITECTURE.md`; read it before changing anything non-obvious.

## Commands

```bash
uv sync --extra dev                      # set up the environment
uv run pytest                            # offline tests — after every edit
uv run python -m sap_help_mcp.probe      # live source check (needs internet)
uv run sap-help-mcp                      # run over stdio, as a client would
```

## Rules for edits

* Keep the layers separate: `tools.py` holds signatures and model-facing text only,
  `helpportal.py` / `community.py` hold logic with no MCP awareness, `fetcher.py` is
  the only module that performs HTTP.
* Every tool returns a dict. Network problems come back as `{"error": ...}`, never as
  an exception — `_safe()` in `tools.py` is the backstop.
* Do not change the portal request shapes (`/http.svc/*`) without a live probe run.
  The endpoints are undocumented; the current shapes were derived from mcp-sap-docs
  and verified against the live portal.
* The Community ranking is covered by fixtures in `tests/test_smoke.py`. If you touch
  the scoring, run those first.
* All model-facing text is in English, including error strings. Queries to both
  portals must be English; translation is the calling model's job, not the server's.

## Release

Bump `version` in `pyproject.toml`, `__version__` in `src/sap_help_mcp/__init__.py`
and `version` in `manifest.json` together — CI checks that the three agree — and add
a `## [X.Y.Z]` section to `CHANGELOG.md`, which becomes the release notes and is
required. Then tag `vX.Y.Z` and push the tag; the release workflow verifies the tag
matches the version, publishes to PyPI and attaches the `.mcpb` bundle to the GitHub
release. Everything that can invalidate a release is checked before the PyPI upload,
because that step is the only irreversible one.
