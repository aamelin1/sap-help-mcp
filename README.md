# sap-help-mcp

**Stop your AI assistant from guessing at SAP configuration.** This MCP server gives
it live access to the two places the answer actually lives: the official SAP
documentation on [help.sap.com](https://help.sap.com) and the practitioner knowledge
on [community.sap.com](https://community.sap.com).

[![CI](https://github.com/aamelin1/sap-help-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/aamelin1/sap-help-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sap-help-mcp.svg)](https://pypi.org/project/sap-help-mcp/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

---

## Quick start

**Claude Desktop** — [download the extension](https://github.com/aamelin1/sap-help-mcp/releases/latest/download/sap-help-mcp.mcpb),
then open **Settings → Extensions → Advanced settings**, click **Install Extension**
and pick the downloaded file.

**Claude Code** — `claude mcp add sap-help -- uvx sap-help-mcp@latest`

That is all. [Install](#install) below covers the other clients, and
[Troubleshooting](#troubleshooting) covers what to do if a step misbehaves.

---

## Why

Ask a general-purpose model how to configure foreign currency valuation, or what
message `F5 702` means, and you get an answer assembled from memory: plausible, often
subtly wrong, and impossible to verify. SAP documentation is huge, versioned per
release, and mostly invisible to ordinary web search.

With this server connected, the assistant searches the portal first and answers from
the page it just read — with a link you can open.

> **You:** How do I set up a substitution for the profit center in FI documents in ECC?
>
> **Assistant:** *(calls `help_search`, then `help_read`)* According to
> *Substitution in Accounting Documents* (SAP_ERP 6.18) the callup point is 0002 …
> — https://help.sap.com/docs/SAP_ERP/49fc4b036bc14cceb9bcf1a45e472f20/0eacc2531bb9b44ce10000000a174cb4.html?version=6.18.latest

It also reaches the **Support Content** space — the FAQs and troubleshooting guides
written by SAP support, the ones that normally sit behind a search box nobody knows
about — and the forum, for the "has anyone actually hit this" half of the job.

## What it gives the assistant

| Tool | What it does |
|---|---|
| `help_search(query, product?, version?, limit)` | Search help.sap.com: all SAP product documentation plus the Support Content wiki. |
| `help_read(ref, part?)` | Fetch a full help.sap.com page as markdown, paginated for long pages. |
| `community_search(query, limit, min_kudos)` | Search SAP Community blogs, Q&A and discussions, ranked on our side. |
| `web_status()` | Version, source endpoints, cache state. Useful to confirm the connection works. |

**No credentials, no local data, nothing written to disk.** The server only issues
anonymous GET requests to public portal endpoints and caches responses in memory for
six hours.

**SAP Notes are not included.** Reading Notes requires a personal S-user, and this
server deliberately holds no secrets. Use [mcp-sap-notes](https://github.com/marianfoo/mcp-sap-notes)
alongside it — this server surfaces the Note numbers, that one opens them.

---

## Install

### Option A — one-click bundle (Claude Desktop, Windows and macOS)

1. **[Download sap-help-mcp.mcpb](https://github.com/aamelin1/sap-help-mcp/releases/latest/download/sap-help-mcp.mcpb)**
   — that link always serves the newest release, so it is the one to pass around.
2. In Claude Desktop, open **Settings → Extensions → Advanced settings**, click
   **Install Extension** and pick the downloaded `.mcpb` file.
3. The install dialog warns that the extension is not verified by Anthropic and will
   have access to your computer. That is expected for any bundle installed from a file
   rather than from Anthropic's directory — decide whether you trust this repository,
   then confirm.

**You do not need Python.** The bundle uses the MCPB `uv` runtime — Claude Desktop
downloads a private Python and the dependencies itself, per bundle, and removes them
on uninstall.

Updating is manual: installing from a file gives Claude Desktop no update source, so a
new release means downloading the next `.mcpb` and installing it again.

### Option B — `uvx` (Claude Desktop, Claude Code, Cursor, anything MCP)

Install [uv](https://docs.astral.sh/uv/) once — it is a single self-contained binary:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Claude Code** — one command, nothing to edit:

```bash
claude mcp add sap-help -- uvx sap-help-mcp@latest
```

**Claude Desktop** — add this block to the `mcpServers` section of your config file
(keep any servers already listed there):

```json
{
  "mcpServers": {
    "sap-help": {
      "command": "uvx",
      "args": ["sap-help-mcp@latest"]
    }
  }
}
```

| | Config file |
|---|---|
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Then quit Claude Desktop completely (**Cmd+Q** on macOS, **File → Exit** on Windows —
closing the window is not enough) and start it again. `uvx` installs the package on
first launch, which takes a few seconds once.

The `@latest` suffix is what keeps you current, and it is worth understanding why.
Plain `uvx sap-help-mcp` resolves the newest version on its *first* run and then reuses
its cached environment indefinitely — a new release is not picked up until the cache is
refreshed, so you would sit on whatever version you first installed. `@latest` asks for
the newest version and refreshes the cache, at the cost of one index lookup per server
start.

Pin instead if you would rather decide when to move: `"args": ["sap-help-mcp==1.0.1"]`.

### Option C — from a downloaded bundle (restricted networks)

The `.mcpb` is a plain zip: the same server, plus a `manifest.json` telling the host
how to start it. If PyPI is unreachable but GitHub is not, unpack it and point a client
at the unpacked copy — this is what Claude Desktop does internally in option A.

```bash
mkdir -p ~/mcp/sap-help && cd ~/mcp/sap-help
unzip ~/Downloads/sap-help-mcp.mcpb

# Claude Code (use an absolute path — the entry is stored verbatim)
claude mcp add sap-help -- \
  uv run --directory ~/mcp/sap-help src/sap_help_mcp/__main__.py
```

For Claude Desktop, the equivalent config entry is:

```json
{
  "mcpServers": {
    "sap-help": {
      "command": "uv",
      "args": ["run", "--directory",
               "/absolute/path/to/mcp/sap-help",
               "src/sap_help_mcp/__main__.py"]
    }
  }
}
```

Two caveats. This does not make the server work offline: `uv` still resolves
`fastmcp` and `markdownify`, so a package index — or a mirror of one — has to be
reachable. And there is no update path: a new release means downloading the next
`.mcpb` and unpacking it again. Prefer option B wherever PyPI is available.

### Option D — from source (for development)

```bash
git clone https://github.com/aamelin1/sap-help-mcp.git
cd sap-help-mcp
uv sync --extra dev
uv run pytest                       # offline tests
uv run python -m sap_help_mcp.probe # live check against both portals
```

Point a client at the checkout with
`"command": "uv", "args": ["run", "--directory", "/abs/path/to/sap-help-mcp", "sap-help-mcp"]`.

---

## Check that it works

Ask the AI assistant: **"call SAP-HELP web_status"**. You should get the server version and the
portal endpoints back. Then try a real question, e.g. *"search SAP help for document
splitting in new general ledger"*.

## Getting good answers out of it

* **Queries go to the portals in English** — both sources are English-only. Ask your
  own question in any language; the assistant is instructed to translate it into SAP
  terminology itself (*«переоценка валюты»* → *foreign currency valuation*).
* **Filter by product line when you know it.** `SAP_ERP` is ECC 6.0,
  `SAP_S4HANA_ON_PREMISE` and `SAP_S4HANA_CLOUD` are what they say, and
  `SUPPORT_CONTENT` is the support Expert Content wiki. Without a filter the portal
  happily returns ByDesign pages.
* **Rephrase once or twice if the results are thin.** It helps more than anything
  else, and the assistant is told to do it.
* **The forum is the forum.** `community_search` returns field experience, not truth.
  Each result carries a `match_score` and a kudos count so quality is visible.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Server does not appear in Claude Desktop | The config was edited but the app was not fully restarted. Quit it entirely and reopen. |
| `spawn uvx ENOENT` | `uvx` is not on the PATH the app inherits. Restart the machine after installing uv, or put the absolute path in `command` (`%USERPROFILE%\.local\bin\uvx.exe`, `~/.local/bin/uvx`). |
| Tools return `"Network unreachable or timed out"` | A corporate proxy or firewall is blocking the portals. Check that `help.sap.com` opens in a browser on the same machine. |
| Tools return `SAP responded 4xx` | The portal probably changed its undocumented endpoints. Run `uv run python -m sap_help_mcp.probe --raw` and open an issue with the output. |
| Search finds nothing sensible | Use the exact English SAP term, a transaction code or a message number; drop the `product` filter. |
| Claude Desktop logs | macOS: `~/Library/Logs/Claude/mcp-server-sap-help.log` · Windows: `%APPDATA%\Claude\logs\` |

## How it works

Roughly 800 lines of Python in four layers: tool declarations, one module per source,
and a single place where HTTP happens. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
covers the three-step page-read chain, the Khoros LiQL ranking problem and the
reasoning behind each design decision.

## Contributing

Issues and pull requests are welcome. Run `uv run pytest` before submitting; if you
touched any portal request shape, also run `uv run python -m sap_help_mcp.probe` and
say in the PR that you did — those endpoints are undocumented and only live checks
prove anything.

## Legal

SAP and other SAP product names are trademarks of SAP SE. This project is not
affiliated with SAP. All content reachable through the server remains the property of
SAP SE and the respective authors; the server stores and redistributes nothing. See
[NOTICE](NOTICE) for third-party attribution, including
[mcp-sap-docs](https://github.com/marianfoo/mcp-sap-docs), whose portal request shapes
this project builds on.

Licensed under the [Apache License 2.0](LICENSE).
