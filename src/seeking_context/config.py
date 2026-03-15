r"""Configuration for SeekingContext MCP server.

Uses pydantic-settings to load from environment variables
with the ``SEEKING_CONTEXT_`` prefix.

Attributes:
    data_dir (str): Base directory for all persistent storage.
        Defaults to ``~/.seeking_context``.
    vector_backend (str): Vector store backend name.
        Currently only ``chromadb`` is supported.
    embedding_model (str): Sentence-transformer model used
        by ChromaDB for embedding generation.
    vector_weight (float): Weight applied to vector similarity
        scores during hybrid search merging.
    text_weight (float): Weight applied to BM25 keyword scores
        during hybrid search merging.
    mmr_lambda (float): Balance between relevance (1.0) and
        diversity (0.0) in MMR re-ranking.
    temporal_decay_half_life_days (float): Number of days for
        a memory score to decay to half its original value.
    boost_recent_days (float): Memories newer than this many
        days receive a recency boost.
    boost_factor (float): Multiplier applied to scores of
        recent memories.
    min_decay (float): Floor for temporal decay factor so
        old memories never score zero.
    default_top_k (int): Default number of results returned
        by search operations.
    transport (str): MCP transport protocol
        (``stdio`` | ``sse`` | ``streamable-http``).
    rest_host (str): Bind address for the REST API server.
    rest_port (int): Port for the REST API server.
    api_key (str | None): Optional API key for REST auth.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class SeekingContextConfig(BaseSettings):
    r"""Global configuration loaded from environment.

    All fields can be overridden via environment variables
    prefixed with ``SEEKING_CONTEXT_``.  For example::

        export SEEKING_CONTEXT_DATA_DIR=/tmp/sc
        export SEEKING_CONTEXT_VECTOR_WEIGHT=0.8
        export SEEKING_CONTEXT_REST_PORT=8080
    """

    model_config = {"env_prefix": "SEEKING_CONTEXT_"}

    # --- storage ---------------------------------------------
    data_dir: str = os.path.join(
        Path.home(), ".seeking_context"
    )
    vector_backend: str = "chromadb"
    embedding_model: str = "all-MiniLM-L6-v2"
    markdown_enabled: bool = True

    # --- hybrid search ---------------------------------------
    vector_weight: float = 0.7
    text_weight: float = 0.3

    # --- MMR -------------------------------------------------
    mmr_lambda: float = 0.7

    # --- temporal decay --------------------------------------
    temporal_decay_half_life_days: float = 30.0
    boost_recent_days: float = 7.0
    boost_factor: float = 1.2
    min_decay: float = 0.1

    # --- defaults --------------------------------------------
    default_top_k: int = 10

    # --- transport -------------------------------------------
    transport: str = "stdio"

    # --- REST API --------------------------------------------
    rest_host: str = "127.0.0.1"
    rest_port: int = 9377
    api_key: str | None = None

    def ensure_data_dir(self) -> Path:
        """Create and return the data directory path."""
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_config() -> SeekingContextConfig:
    """Return the global configuration singleton."""
    return SeekingContextConfig()
