# SeekingContext

[English](README.md) / [中文](README_CN.md)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/Protocol-MCP-green.svg)](https://modelcontextprotocol.io/)

**Universal Memory MCP Server for AI Agents**

A memory server where every piece of knowledge is a readable `.md` file you can inspect, `grep`, and git-track — while still getting sub-second hybrid search under the hood.

---

## Why SeekingContext?

Most agent memory systems lock your data inside opaque binary databases. You can't read them, can't grep them, can't track changes in git, can't fix a bad memory with a text editor.

SeekingContext takes a different approach: **your memories are just markdown files**. The vector index and full-text index are derived caches that can be blown away and rebuilt from those files at any time.

```
~/.seeking_context/
├── memories/                     # Source of truth (human-readable)
│   ├── claude-code/
│   │   ├── .abstract.md          # Auto-generated directory summary
│   │   ├── .overview.md          # Auto-generated overview table
│   │   ├── profile.md            # Append-only user profile
│   │   ├── entities/
│   │   │   └── mem_a1b2c3.md     # One file per memory
│   │   └── preferences/
│   │       └── mem_d4e5f6.md
│   └── less-agent/
│       └── ...
├── chroma/                       # Derived vector index (rebuildable)
└── metadata.db                   # Derived FTS index (rebuildable)
```

**Delete `chroma/` and `metadata.db`. Run `seeking-context rebuild`. Everything comes back.** That's the guarantee.

---

## Features

### Dual-Layer Storage Architecture

The core design that sets SeekingContext apart:

- **Layer 1 — Markdown Source of Truth**: Every memory is a YAML-frontmatter `.md` file. Human-readable, git-trackable, grep-able, editable. You own your data in the most portable format possible.
- **Layer 2 — Derived Search Indexes**: ChromaDB (vector) and SQLite/FTS5 (keyword) are acceleration layers rebuilt from markdown at any time. They are caches, not canonical storage.

Every write goes to `.md` first, then to the indexes. Every read tries `.md` first, falls back to SQLite. The indexes can be deleted and rebuilt with a single command.

### Intelligent Search Pipeline

Not just keyword matching, not just embeddings — a four-stage pipeline:

1. **Hybrid Search** — Vector similarity (70%) + BM25 keyword matching (30%), tunable weights
2. **Temporal Decay** — Exponential decay with configurable half-life; recent memories get a boost
3. **MMR Reranking** — Maximal Marginal Relevance eliminates redundant results, balances relevance with diversity
4. **Multi-granularity Return** — Choose L0 (abstract), L1 (overview), or L2 (full content) per query

### Auto-Generated Directory Summaries

After every write, SeekingContext auto-generates:

- **`.abstract.md`** per directory — quick counts and latest entry
- **`.overview.md`** per namespace — Markdown table of all categories with counts

These files let you (or another agent) quickly scan what's in memory without reading every file.

### Everything Else

- **Scope Isolation** — user / agent / session three-level scoping
- **Namespace Isolation** — Multiple frameworks share one instance without ID collisions
- **Multi-protocol** — MCP (stdio/SSE/streamable-http), REST API, Python SDK
- **Profile Append-Only** — The `profile` category never overwrites, only appends
- **Six Memory Categories** — profile, preferences, entities, events, cases, patterns
- **CLI Tools** — Generate configs for Claude Code, less-agent, OpenViking, openclaw

---

## Installation

```bash
pip install seeking-context
```

---

## Quick Start

### Python SDK

```python
from seeking_context import SeekingContextClient

client = SeekingContextClient()

# Store memory
client.add(
    content="User prefers Python and FastAPI",
    category="preferences"
)

# Search memories
results = client.search("programming preferences", top_k=5)
```

### MCP Protocol

Configure `.mcp.json`:

```json
{
  "mcpServers": {
    "seeking-context": {
      "command": "uv",
      "args": ["run", "seeking-context"]
    }
  }
}
```

Use MCP tools:

```python
# Store
await memory_add(
    content="User name: Alice",
    category="profile",
    user_id="alice"
)

# Search
results = await memory_search(
    query="user information",
    top_k=5
)

# Rebuild indexes from markdown (after manual edits)
await memory_rebuild_index()
```

### REST API

```bash
# Start server
seeking-context-api

# Search memories
curl -X POST http://localhost:9377/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python", "top_k": 5}'
```

---

## Markdown Storage Format

Each memory is a `.md` file with YAML frontmatter:

```markdown
---
id: "a1b2c3d4-..."
category: entities
user_id: "claude-code:default"
agent_id: "claude-code:default"
created_at: "2026-03-15T10:30:00+00:00"
updated_at: "2026-03-15T10:30:00+00:00"
active_count: 3
metadata:
  source: claude-code-auto
---

# Abstract

User prefers uv over pip for Python dependency management.

# Overview

The user has explicitly stated preference for uv as the
Python package manager. All project setup should use
`uv init`, `uv add`, `uv run`.

# Content

During the session on 2026-03-15, the user said "always
use uv, never pip". This applies to all Python projects.
```

You can edit this file by hand, then run `seeking-context rebuild` to sync the indexes.

---

## CLI Commands

### Server

```bash
seeking-context run           # Start MCP server (stdio)
seeking-context run --all     # MCP (SSE) + REST API combined
```

### Markdown Management

```bash
# Rebuild vector + FTS indexes from .md files
# (proves markdown is the source of truth)
seeking-context rebuild

# Export existing SQLite data to .md files
# (one-time migration for existing users)
seeking-context export-markdown
```

### Framework Setup

```bash
seeking-context setup claude-code [--write] [--plugin]
seeking-context setup less-agent [--write]
seeking-context setup openviking [--write]
seeking-context setup openclaw
seeking-context setup rest
```

---

## Core Concepts

### Multi-granularity Storage

Each memory supports three granularity levels:

```python
client.add(
    content="Full content...",
    abstract="One-line summary",      # Quick identification
    overview="Structured overview"    # Decision reference
)

# Specify return level
results = client.search("query", level=0)  # Abstract only
results = client.search("query", level=1)  # Overview
results = client.search("query", level=2)  # Full content
```

### Six Memory Categories

| Category | Purpose |
|----------|---------|
| `profile` | User profile (append-only) |
| `preferences` | User preferences |
| `entities` | Named entities |
| `events` | Event records |
| `cases` | Specific cases |
| `patterns` | Reusable patterns |

### Namespace Isolation

Multiple frameworks sharing the same instance:

```python
# Framework A
client_a = SeekingContextClient(namespace="framework-a")

# Framework B
client_b = SeekingContextClient(namespace="framework-b")

# Same user_id won't conflict
client_a.add("Memory A", user_id="alice")
client_b.add("Memory B", user_id="alice")
```

Cross-namespace search:

```python
results = await memory_search_cross(
    query="Python",
    namespaces=["framework-a", "framework-b"],
    top_k=10
)
```

---

## Hybrid Search Algorithm

```python
# Combined score
combined_score = (
    vector_weight * vector_score +   # Default 0.7
    text_weight * text_score         # Default 0.3
)

# Temporal decay
decay_factor = 2 ** (-age_days / half_life_days)

# Recent boost
if age_days < boost_recent_days:
    decay_factor *= boost_factor

# MMR reranking
mmr_score = (
    lambda * relevance -
    (1 - lambda) * max_similarity_to_selected
)
```

---

## Running Modes

| Mode | Command | Protocol | Use Case |
|------|---------|----------|----------|
| MCP-only | `seeking-context` | stdio/SSE/streamable-http | MCP clients (Claude Code, Cursor) |
| REST-only | `seeking-context-api` | HTTP | HTTP clients, cross-language |
| Combined | `seeking-context run --all` | SSE + HTTP | Both MCP and REST |

---

## Configuration

Environment variables (prefix `SEEKING_CONTEXT_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `~/.seeking_context` | Data directory |
| `MARKDOWN_ENABLED` | `true` | Enable markdown source-of-truth storage |
| `VECTOR_WEIGHT` | `0.7` | Vector search weight |
| `TEXT_WEIGHT` | `0.3` | Keyword search weight |
| `TEMPORAL_DECAY_HALF_LIFE_DAYS` | `30.0` | Temporal decay half-life |
| `BOOST_RECENT_DAYS` | `7.0` | Recent boost days |
| `BOOST_FACTOR` | `1.2` | Recent boost factor |
| `REST_HOST` | `127.0.0.1` | REST API host |
| `REST_PORT` | `9377` | REST API port |
| `API_KEY` | `None` | API key (optional) |

Set `SEEKING_CONTEXT_MARKDOWN_ENABLED=false` to disable markdown storage and use ChromaDB + SQLite only (backward compatible).

---

## Storage Architecture

```
Write path:  memory_add() → .md file → ChromaDB + SQLite
Read path:   memory_get() → .md file (fallback: SQLite)
Rebuild:     seeking-context rebuild → walk .md → re-populate indexes
```

- **Markdown** (`memories/`): Source of truth. YAML frontmatter + sectioned body.
- **ChromaDB** (`chroma/`): Derived vector index (`all-MiniLM-L6-v2` embeddings). Rebuildable.
- **SQLite** (`metadata.db`): Derived metadata + FTS5 full-text index. Rebuildable.

Data location: `~/.seeking_context/`

---

## Development

```bash
# Clone
git clone https://github.com/yourusername/SeekingContext.git
cd SeekingContext

# Setup
uv venv .venv --python=3.12
source .venv/bin/activate
uv sync

# Test
uv run pytest

# Coverage
uv run pytest --cov=seeking_context
```

---

## Roadmap

- [x] MCP protocol support
- [x] REST API
- [x] Python SDK
- [x] Namespace isolation
- [x] CLI tools
- [x] Markdown-first storage (source of truth)
- [x] Auto-generated directory summaries
- [x] Index rebuild from markdown
- [x] Database-to-markdown migration
- [ ] More vector databases (Pinecone, Weaviate)
- [ ] Web UI
- [ ] Multi-tenancy
- [ ] Custom embedding models
- [ ] Memory quality scoring

---

## License

MIT License

---

## Contact

- **Author**: less
- **Email**: 3038880699@qq.com
- **GitHub**: https://github.com/yourusername/SeekingContext

---

## Acknowledgments

This project was inspired by the following excellent projects:

**Memory Frameworks:**
- [OpenViking](https://github.com/volcengine/OpenViking) - Context Database for AI Agents
- [mem0](https://github.com/mem0ai/mem0) - The Memory Layer for Personalized AI
- [mem9](https://github.com/mem0ai/mem9) - Memory management for AI applications

**Agent Frameworks:**
- [openclaw](https://docs.mem0.ai/integrations/openclaw) - AI agent framework with memory integration

**MCP Ecosystem:**
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - Model Context Protocol implementation
- [Claude Code Plugins](https://github.com/anthropics/claude-code) - MCP client integration examples

**Technical Support:**
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

**If this project helps you, please give it a Star!**
