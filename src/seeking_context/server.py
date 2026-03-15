r"""FastMCP entry point for SeekingContext.

Boots the MCP server, registers all tools, resources,
and prompts, then starts the selected transport.

Usage::

    # stdio (default)
    uv run seeking-context

    # SSE
    SEEKING_CONTEXT_TRANSPORT=sse uv run seeking-context

    # Combined MCP (SSE) + REST API
    uv run seeking-context-all
"""

from __future__ import annotations

import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from seeking_context.config import get_config

logger = logging.getLogger("seeking_context")

mcp = FastMCP("SeekingContext")


def _register_all() -> None:
    """Import submodules so their decorators register."""
    import seeking_context.tools.memory_tools  # noqa: F401
    import seeking_context.tools.context_tools  # noqa: F401
    import seeking_context.tools.session_tools  # noqa: F401
    import seeking_context.resources.memory_resources  # noqa: F401
    import seeking_context.prompts.memory_prompts  # noqa: F401


def main() -> None:
    """CLI entry point for MCP-only mode."""
    config = get_config()
    config.ensure_data_dir()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(name)s "
            "%(levelname)s %(message)s"
        ),
    )

    _register_all()

    transport = config.transport
    logger.info(
        "Starting SeekingContext (%s)", transport,
    )
    mcp.run(transport=transport)


def main_all() -> None:
    """CLI entry point for combined MCP + REST mode.

    Runs the MCP server (SSE/streamable-http) and the
    FastAPI REST server concurrently via asyncio.
    """
    config = get_config()
    config.ensure_data_dir()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(name)s "
            "%(levelname)s %(message)s"
        ),
    )

    _register_all()

    async def _run_both() -> None:
        """Run MCP (SSE) and REST API concurrently."""
        import uvicorn

        from seeking_context.api import create_app

        rest_app = create_app()

        # REST API server
        rest_config = uvicorn.Config(
            rest_app,
            host=config.rest_host,
            port=config.rest_port,
            log_level="info",
        )
        rest_server = uvicorn.Server(rest_config)

        logger.info(
            "Starting combined mode: "
            "MCP (sse) + REST (%s:%d)",
            config.rest_host,
            config.rest_port,
        )

        # MCP SSE server (uses its own port 8080)
        transport = config.transport
        if transport == "stdio":
            transport = "sse"
            logger.info(
                "Combined mode overrides transport "
                "from stdio to sse",
            )

        # Run both concurrently
        await asyncio.gather(
            _run_mcp_async(transport),
            rest_server.serve(),
        )

    asyncio.run(_run_both())


async def _run_mcp_async(transport: str) -> None:
    """Run MCP server in async context.

    Args:
        transport: MCP transport type (sse,
            streamable-http).
    """
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
