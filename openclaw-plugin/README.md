# @seeking-context/openclaw

SeekingContext memory plugin for openclaw — hybrid
vector + keyword search with namespace isolation.

## Prerequisites

Start the SeekingContext REST API:

```bash
cd /path/to/SeekingContext
uv run seeking-context-api
```

## Installation

### Option 1: CLI setup

```bash
uv run seeking-context setup openclaw
```

### Option 2: Manual install

Add to your openclaw project:

```bash
npm install @seeking-context/openclaw
```

Or reference directly in your openclaw config:

```json
{
  "plugins": [
    {
      "id": "seeking-context",
      "package": "@seeking-context/openclaw",
      "config": {
        "apiUrl": "http://127.0.0.1:9377",
        "namespace": "openclaw"
      }
    }
  ]
}
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `apiUrl` | `http://127.0.0.1:9377` | REST API URL |
| `namespace` | `openclaw` | Namespace for isolation |
| `autoCapture` | `false` | Auto-capture key facts |
| `autoRecall` | `true` | Auto-inject relevant memories |
| `topK` | `5` | Max memories per search |
| `captureMaxChars` | `500` | Max msg length for capture |

## Tools

| Tool | Description |
|------|-------------|
| `memory_store` | Store information in long-term memory |
| `memory_search` | Search memories (hybrid vector + keyword) |
| `memory_get` | Retrieve a single memory by ID |
| `memory_update` | Update an existing memory |
| `memory_delete` | Delete a memory by ID |

## Lifecycle Hooks

| Hook | Trigger | Action |
|------|---------|--------|
| `before_prompt_build` | Each agent turn | Inject relevant memories |
| `agent_end` | After agent turn | Auto-capture key facts |
| `before_reset` | Before session wipe | Save session summary |

## CLI Commands

```bash
openclaw seeking-context search "query"
openclaw seeking-context stats
```

## Architecture

```
openclaw agent
  ├── before_prompt_build
  │   └── POST /v1/memories/search → <relevant-memories>
  ├── Tools (memory_store, memory_search, ...)
  │   └── POST/GET /v1/memories
  ├── agent_end
  │   └── shouldCapture() → POST /v1/memories
  └── before_reset
      └── POST /v1/memories (session summary)
```

All requests include `X-Namespace: openclaw` header
for cross-framework isolation. Memory stored by
openclaw won't collide with other frameworks.

## License

Apache-2.0
