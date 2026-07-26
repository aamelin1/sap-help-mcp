"""Entry point for `python -m sap_help_mcp` and for the .mcpb bundle.

Absolute import on purpose: the MCPB `uv` runtime launches this file by path
(`uv run --directory <bundle> src/sap_help_mcp/__main__.py`), and by then uv has
already installed the project into its environment — so `sap_help_mcp` resolves.
"""

from sap_help_mcp.server import main

if __name__ == "__main__":
    main()
