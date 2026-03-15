---
title: claude-plugin — Claude Code hooks and skills
---

## Overview

Claude Code integration uses bash hooks plus two
skills. Hook scripts are small and deterministic;
shared HTTP helpers live in `hooks/common.sh`.

## Where to look

| Task | File |
|------|------|
| Shared curl/env helpers | `hooks/common.sh` |
| Session-start injection | `hooks/session-start.sh` |
| Prompt hint injection | `hooks/user-prompt-submit.sh` |
| Session stop capture | `hooks/stop.sh` |
| Plugin manifest | `.claude-plugin/plugin.json` |
| Hook definitions | `hooks/hooks.json` |
| On-demand recall | `skills/memory-recall/SKILL.md` |
| On-demand store | `skills/memory-store/SKILL.md` |

## Local conventions

- Every hook sources `hooks/common.sh`.
- Missing or unreachable API server should fail
  quietly so Claude Code still starts normally.
- JSON shaping uses inline Python, not `jq`.
- Namespace via `X-Namespace` header, defaults
  to `claude-code`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SEEKING_CONTEXT_API_URL` | `http://127.0.0.1:9377` | REST API URL |
| `SEEKING_CONTEXT_NAMESPACE` | `claude-code` | Namespace for isolation |
| `SEEKING_CONTEXT_API_KEY` | (none) | Optional API key |

## Anti-patterns

- Do NOT add complex state to hooks.
- Do NOT use `jq` in hooks; keep Python-based
  parsing consistent.
- Do NOT store sensitive credentials automatically.
