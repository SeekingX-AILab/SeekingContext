r"""CLI for SeekingContext with setup subcommands.

Provides ``seeking-context run`` (start server),
``seeking-context setup <framework>`` to generate config
snippets, and ``seeking-context rebuild`` / ``export-markdown``
for markdown-first storage management.

Usage::

    seeking-context setup claude-code
    seeking-context setup less-agent
    seeking-context setup openviking
    seeking-context setup openclaw
    seeking-context setup rest
    seeking-context run           # start MCP server
    seeking-context run --all     # MCP + REST combined
    seeking-context rebuild       # rebuild indexes from .md
    seeking-context export-markdown  # export DB to .md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import typer

app = typer.Typer(
    name="seeking-context",
    help="SeekingContext - Universal Agent Memory",
    no_args_is_help=True,
)

setup_app = typer.Typer(
    name="setup",
    help="Generate config for agent frameworks.",
    no_args_is_help=True,
)
app.add_typer(setup_app, name="setup")


def _pkg_dir() -> str:
    """Return the package source directory path.

    Returns:
        Absolute path to the SeekingContext package root.
    """
    return str(
        Path(__file__).resolve().parent.parent.parent
    )


# -- run command ----------------------------------------------


@app.command()
def run(
    all_mode: bool = typer.Option(
        False, "--all",
        help="Run MCP + REST API combined.",
    ),
) -> None:
    """Start the SeekingContext server.

    By default starts MCP-only mode.  Use ``--all`` for
    combined MCP (SSE) + REST API mode.
    """
    if all_mode:
        from seeking_context.server import main_all
        main_all()
    else:
        from seeking_context.server import main
        main()


# -- setup subcommands ----------------------------------------


@setup_app.command("claude-code")
def setup_claude_code(
    write: bool = typer.Option(
        False, "--write",
        help="Write .mcp.json to current directory.",
    ),
    plugin: bool = typer.Option(
        False, "--plugin",
        help="Show Claude Code plugin install steps.",
    ),
) -> None:
    """Generate MCP config for Claude Code.

    Produces a ``.mcp.json`` snippet that tells Claude Code
    how to launch SeekingContext via stdio transport.

    Use ``--plugin`` to show steps for installing the
    Claude Code plugin (hooks + skills) instead.
    """
    if plugin:
        plugin_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "claude-plugin"
        )
        typer.echo(
            "# Claude Code Plugin (hooks + skills)"
        )
        typer.echo()
        typer.echo(
            "1. Start the SeekingContext REST API:"
        )
        typer.echo(
            "   uv run seeking-context-api"
        )
        typer.echo()
        typer.echo(
            "2. Install the plugin:"
        )
        typer.echo(
            f"   claude plugin install {plugin_dir}"
        )
        typer.echo()
        typer.echo(
            "3. (Optional) Set env vars in "
            "~/.claude/settings.json:"
        )
        env_cfg = {
            "env": {
                "SEEKING_CONTEXT_API_URL":
                    "http://127.0.0.1:9377",
                "SEEKING_CONTEXT_NAMESPACE":
                    "claude-code",
            }
        }
        typer.echo(
            json.dumps(env_cfg, indent=2)
        )
        typer.echo()
        typer.echo(
            "4. Restart Claude Code."
        )
        return

    pkg = _pkg_dir()
    config = {
        "mcpServers": {
            "seeking-context": {
                "command": "uv",
                "args": [
                    "--directory", pkg,
                    "run", "seeking-context",
                ],
            }
        }
    }
    snippet = json.dumps(config, indent=2)

    if write:
        out_path = Path(".mcp.json")
        out_path.write_text(snippet + "\n")
        typer.echo(f"Wrote {out_path.resolve()}")
    else:
        typer.echo("# .mcp.json for Claude Code (MCP)")
        typer.echo(snippet)
        typer.echo()
        typer.echo(
            "Tip: run with --write to create the "
            "file, or --plugin for hook-based setup."
        )


@setup_app.command("less-agent")
def setup_less_agent(
    write: bool = typer.Option(
        False, "--write",
        help="Write mcp_servers.json snippet.",
    ),
) -> None:
    """Generate MCP config for less-agent.

    Produces the ``mcp_servers.json`` entry for less-agent.
    Pass ``namespace="less-agent"`` in tool calls for
    scope isolation.
    """
    pkg = _pkg_dir()
    config = {
        "seeking-context": {
            "command": "uv",
            "args": [
                "--directory", pkg,
                "run", "seeking-context",
            ],
        }
    }
    snippet = json.dumps(config, indent=2)

    if write:
        out_path = Path("mcp_servers.json")
        out_path.write_text(snippet + "\n")
        typer.echo(f"Wrote {out_path.resolve()}")
    else:
        typer.echo(
            "# mcp_servers.json entry for less-agent"
        )
        typer.echo(snippet)
        typer.echo()
        typer.echo(
            "In tool calls, pass "
            'namespace="less-agent" for isolation.'
        )


@setup_app.command("openviking")
def setup_openviking(
    write: bool = typer.Option(
        False, "--write",
        help="Write .mcp.json for SSE mode.",
    ),
) -> None:
    """Generate SSE-mode MCP config for OpenViking.

    Requires the server to be running in SSE mode::

        SEEKING_CONTEXT_TRANSPORT=sse \\
            uv run seeking-context
    """
    config = {
        "mcpServers": {
            "seeking-context": {
                "url": "http://127.0.0.1:8080/sse",
            }
        }
    }
    snippet = json.dumps(config, indent=2)

    if write:
        out_path = Path(".mcp.json")
        out_path.write_text(snippet + "\n")
        typer.echo(f"Wrote {out_path.resolve()}")
    else:
        typer.echo("# .mcp.json for SSE-based clients")
        typer.echo(snippet)
        typer.echo()
        typer.echo("First start the server:")
        typer.echo(
            "  SEEKING_CONTEXT_TRANSPORT=sse "
            "uv run seeking-context"
        )


@setup_app.command("openclaw")
def setup_openclaw() -> None:
    """Print openclaw plugin setup instructions.

    Shows how to install the ``@seeking-context/openclaw``
    plugin package, or use the Python SDK directly.
    """
    plugin_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "openclaw-plugin"
    )
    typer.echo("# openclaw Plugin Setup")
    typer.echo()
    typer.echo("Option 1: Install the plugin package")
    typer.echo()
    config = {
        "plugins": [{
            "id": "seeking-context",
            "package": "@seeking-context/openclaw",
            "config": {
                "apiUrl": "http://127.0.0.1:9377",
                "namespace": "openclaw",
                "autoRecall": True,
            }
        }]
    }
    typer.echo(json.dumps(config, indent=2))
    typer.echo()
    typer.echo(
        f"Plugin source: {plugin_dir}"
    )
    typer.echo()
    typer.echo("Option 2: Use the Python SDK directly")
    typer.echo()
    snippet = '''from seeking_context import SeekingContextClient

client = SeekingContextClient(
    namespace="openclaw",
    default_agent_id="my-agent",
)

# Store a memory
client.add("some knowledge", category="cases")

# Search
results = client.search("find something")
for r in results:
    print(r["content"])'''

    typer.echo(snippet)


@setup_app.command("rest")
def setup_rest() -> None:
    """Print REST API usage examples.

    Shows curl commands for interacting with the REST API.
    Start the server first with ``uv run seeking-context-api``.
    """
    snippet = r'''# Start the REST API server
uv run seeking-context-api

# Store a memory
curl -X POST http://127.0.0.1:9377/v1/memories \
  -H "Content-Type: application/json" \
  -H "X-Namespace: my-app" \
  -d '{"content": "important fact", "category": "entities"}'

# Search memories
curl -X POST http://127.0.0.1:9377/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"query": "important", "namespace": "my-app"}'

# Cross-namespace search
curl -X POST http://127.0.0.1:9377/v1/memories/search/cross \
  -H "Content-Type: application/json" \
  -d '{"query": "fact", "namespaces": ["app-a", "app-b"]}'

# Health check
curl http://127.0.0.1:9377/v1/status'''

    typer.echo(snippet)


# -- markdown management commands -----------------------------


@app.command()
def rebuild() -> None:
    """Rebuild vector + FTS indexes from markdown files.

    Deletes ``chroma/`` and ``metadata.db``, then walks
    all ``memories/**/*.md`` files and re-populates both
    indexes.  Proves markdown is the source of truth.
    """
    from seeking_context.config import get_config
    from seeking_context.storage.memory_store import (
        MemoryStore,
    )
    from seeking_context.storage.markdown_store import (
        MarkdownStore,
    )

    config = get_config()
    data = config.ensure_data_dir()

    md_dir = data / "memories"
    if not md_dir.is_dir():
        typer.echo(
            "No memories/ directory found. "
            "Nothing to rebuild from."
        )
        raise typer.Exit(1)

    # Remove derived indexes.
    chroma_dir = data / "chroma"
    db_path = data / "metadata.db"

    if chroma_dir.is_dir():
        import shutil
        shutil.rmtree(chroma_dir)
        typer.echo("Removed chroma/ directory.")

    if db_path.is_file():
        db_path.unlink()
        typer.echo("Removed metadata.db.")

    # Rebuild from markdown.
    store = MemoryStore(config=config)
    md_store = MarkdownStore(str(md_dir))

    async def _rebuild() -> int:
        """Run the async rebuild."""
        return await md_store.rebuild_indexes(
            store.vector, store.meta
        )

    count = asyncio.run(_rebuild())
    typer.echo(
        f"Rebuilt indexes from {count} markdown files."
    )


@app.command("export-markdown")
def export_markdown() -> None:
    """Export all memories from SQLite to markdown files.

    Reads every item from ``metadata.db`` and writes a
    ``mem_{id}.md`` file for each.  One-time migration
    for existing users.
    """
    from seeking_context.config import get_config
    from seeking_context.storage.markdown_store import (
        MarkdownStore,
    )
    from seeking_context.storage.sqlite_store import (
        SQLiteStore,
    )

    config = get_config()
    data = config.ensure_data_dir()

    db_path = data / "metadata.db"
    if not db_path.is_file():
        typer.echo(
            "No metadata.db found. "
            "Nothing to export."
        )
        raise typer.Exit(1)

    md_dir = data / "memories"
    meta = SQLiteStore(db_path=str(db_path))
    md_store = MarkdownStore(str(md_dir))

    async def _export() -> int:
        """Run the async export."""
        return await md_store.export_from_db(meta)

    count = asyncio.run(_export())
    typer.echo(
        f"Exported {count} memories to "
        f"{md_dir}"
    )


if __name__ == "__main__":
    app()
