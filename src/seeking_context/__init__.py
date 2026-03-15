"""SeekingContext - Universal Memory MCP Server."""

__version__ = "0.1.0"

from seeking_context.client import (  # noqa: F401
    SeekingContextClient,
)

__all__ = ["SeekingContextClient", "__version__"]
