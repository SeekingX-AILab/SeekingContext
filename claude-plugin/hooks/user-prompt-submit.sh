#!/usr/bin/env bash
# user-prompt-submit.sh — Lightweight hint that shared
# memory is available via skills.
# Hook: UserPromptSubmit (sync, timeout: 5s)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

read_stdin

# If server not reachable, do nothing.
if ! sc_check_server 2>/dev/null; then
  exit 0
fi

# Inject system hint so Claude knows memory is available.
cat <<'EOF'
{"systemMessage":"[seeking-context] Persistent memory is available. Use /memory-store to save information the user wants to remember. Use /memory-recall to search past memories when context would help."}
EOF
