# Publishing checklist

Everything in the repository is ready; these are the steps that need a human with
credentials. This file is for the maintainer and is not part of the product — delete
it, or keep it, as you prefer.

## 1. Create the GitHub repository

Create an **empty** public repository at `github.com/aamelin1/sap-help-mcp` (no README,
no license, no .gitignore — the tree already has them), then:

```bash
cd sap-help-mcp
git remote add origin git@github.com:aamelin1/sap-help-mcp.git
git push -u origin main
```

The history is a single commit and contains no personal paths or internal references.

After the first push, in **Settings → General**: add the description and topics
(`mcp`, `sap`, `s4hana`, `abap`, `claude`, `model-context-protocol`) — topics are how
people find MCP servers on GitHub.

## 2. Claim the name on PyPI and set up trusted publishing

The release workflow publishes without any stored token, using PyPI's OIDC trusted
publishing. Configure it **before** the first tag:

1. Log in to <https://pypi.org> → **Your projects → Publishing → Add a new pending
   publisher**.
2. Fill in:
   - PyPI project name: `sap-help-mcp`
   - Owner: `aamelin1`
   - Repository: `sap-help-mcp`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. In GitHub → **Settings → Environments**, create an environment named `pypi`.

## 3. Release

```bash
git tag v1.0.0
git push origin v1.0.0
```

The `Release` workflow then:

1. checks that the tag matches the version in `pyproject.toml`,
   `src/sap_help_mcp/__init__.py` and `manifest.json`;
2. runs the tests;
3. builds the wheel and sdist and publishes them to PyPI;
4. packs `sap-help-mcp.mcpb` and attaches it, with the distributions, to a GitHub
   release with generated notes.

Once that release exists, both install paths in the README work verbatim: the `.mcpb`
download link points at `releases/latest`, and `uvx sap-help-mcp` resolves from PyPI.

## 4. Smoke-test the way a colleague would

On a machine that has never seen the project:

* **Windows** — install uv, add the `uvx` block to
  `%APPDATA%\Claude\claude_desktop_config.json`, restart Claude Desktop fully, ask it
  to *"call web_status"*.
* **macOS** — download the `.mcpb` from the release, install it through
  **Settings → Extensions**, ask the same question.

Both should answer with version `1.0.0` and the two portal endpoints.

## Later versions

Bump the version in all three files together (CI enforces it), add a `CHANGELOG.md`
entry, tag, push the tag. Nothing else is manual.
