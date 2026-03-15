# SeekingContext Claude Code Plugin

Persistent local memory for Claude Code powered by
the SeekingContext REST API. Auto-loads relevant
memories on session start, auto-saves on stop, with
on-demand store/recall skills.

## Prerequisites

Start the SeekingContext REST API:

```bash
cd /path/to/SeekingContext
uv run seeking-context-api
```

Or use the combined MCP + REST server:

```bash
uv run seeking-context-all
```

## Installation

### Option 1: CLI setup (recommended)

```bash
uv run seeking-context setup claude-code
```

### Option 2: Manual install

1. Copy the `claude-plugin/` directory to your
   desired location.

2. Install the plugin:

```bash
claude plugin install /path/to/claude-plugin
```

3. (Optional) Set environment variables in
   `~/.claude/settings.json`:

```json
{
  "env": {
    "SEEKING_CONTEXT_API_URL": "http://127.0.0.1:9377",
    "SEEKING_CONTEXT_NAMESPACE": "claude-code"
  }
}
```

4. Restart Claude Code.

## How It Works

### Automatic Hooks

| Hook | Trigger | Action |
|------|---------|--------|
| **SessionStart** | Session begins | Load recent memories into context |
| **UserPromptSubmit** | Each prompt | Inject hint about available skills |
| **Stop** | Session ends | Save last assistant turn as memory |

### On-Demand Skills

| Skill | Trigger | Action |
|-------|---------|--------|
| `/memory-store` | "remember X" | Save specific info to memory |
| `/memory-recall` | "recall X" | Search past memories |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SEEKING_CONTEXT_API_URL` | `http://127.0.0.1:9377` | REST API URL |
| `SEEKING_CONTEXT_NAMESPACE` | `claude-code` | Namespace for isolation |
| `SEEKING_CONTEXT_API_KEY` | (none) | Optional API key |

## Architecture

```
Claude Code
  ├── SessionStart hook
  │   └── GET /v1/memories → inject context
  ├── UserPromptSubmit hook
  │   └── hint: /memory-store, /memory-recall
  ├── Stop hook
  │   └── POST /v1/memories → save summary
  └── Skills
      ├── /memory-store → POST /v1/memories
      └── /memory-recall → POST /v1/memories/search
```

All requests include `X-Namespace: claude-code`
header for cross-framework isolation. Memories
stored by Claude Code won't collide with memories
from other frameworks (less-agent, openclaw, etc.).

## License

Apache-2.0
