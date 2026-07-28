# Publishing checklist

Everything in the repository is ready; these are the steps that need a human with
credentials. This file is for the maintainer and is not part of the product — delete
it, or keep it, as you prefer.

## 1. Publish the repository

The local repository is already initialised: branch `main`, two commits, clean working
tree, **no remote configured on purpose** — GitHub Desktop creates the remote itself.

### With GitHub Desktop (nothing to create on github.com first)

1. **Sign in.** GitHub Desktop → *Settings → Accounts* → sign in as `aamelin1`.
2. **Set the commit identity before anything else.** *Settings → Git*:
   - Name: `Andrey Amelin`
   - Email: `aamelin1@users.noreply.github.com`

   Do not leave a work email here — every commit email is public forever in a public
   repository. The two existing commits already use the noreply address.
3. **Add the folder.** *File → Add local repository…* and select
   `Documents/SAP KB MCPs/sap-help-mcp`.

   Select that subfolder exactly, **not** the parent `SAP KB MCPs` — the parent holds
   unrelated internal notes and the predecessor project.
4. It should report *"No local changes"* and show the two commits under *History*.
5. **Publish.** Click *Publish repository* in the top bar:
   - Name: `sap-help-mcp`
   - Description: `MCP server for searching SAP Help Portal and SAP Community`
   - **Uncheck "Keep this code private"**
   - Organization: *None*

   Press *Publish repository*. GitHub Desktop creates the repository on GitHub, sets
   up the remote over HTTPS with your existing credentials, and pushes `main`.

### Then, on github.com

6. Open the new repository → gear icon next to *About* → add the same description and
   these topics: `mcp`, `model-context-protocol`, `sap`, `s4hana`, `abap`, `claude`.
   Topics are how people actually find MCP servers.
7. Open the *Actions* tab. The CI workflow runs on the first push; wait for it to go
   green (six jobs: three operating systems × two Python versions, plus the version
   and bundle checks).
8. Optional but recommended: *Your profile → Settings → Emails* → tick **"Keep my
   email addresses private"**. That makes GitHub reject any future push carrying a
   real email address, so the safeguard in step 2 cannot be undone by accident.

### If you prefer the command line

```bash
cd "sap-help-mcp"
git remote add origin https://github.com/aamelin1/sap-help-mcp.git
git push -u origin main
```

This variant needs the empty repository to exist on github.com first: *New
repository* → name `sap-help-mcp` → Public → **add no README, no .gitignore and no
license**, since the tree already contains all three.

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
download link points at `releases/latest`, and `uvx sap-help-mcp@latest` resolves from
PyPI.

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
