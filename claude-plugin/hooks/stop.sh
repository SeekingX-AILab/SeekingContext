#!/usr/bin/env bash
# stop.sh — Capture the last assistant turn and save it
# as a memory before session ends.
# Hook: Stop (async, timeout: 120s)
# Async means this runs in the background and won't
# block Claude from responding.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

read_stdin

# If server not reachable, exit silently.
if ! sc_check_server 2>/dev/null; then
  exit 0
fi

# Prevent recursion and extract last assistant message.
eval "$(echo "$HOOK_INPUT" | python3 -c "
import json, sys, shlex

data = json.load(sys.stdin)

# Check recursion guard.
active = str(
    data.get(
        'stopHookActive',
        data.get('stop_hook_active', False)
    )
).lower()
print(f'stop_hook_active={shlex.quote(active)}')

# Extract last assistant message from transcript.
transcript = data.get('transcript', [])
msg = ''
for turn in reversed(transcript):
    if turn.get('role') == 'assistant':
        msg = turn.get('content', '')
        break
# Fallback: try legacy field name.
if not msg:
    msg = data.get('last_assistant_message', '')
if len(msg) > 8000:
    msg = msg[:8000] + '...'
print(f'last_message={shlex.quote(msg)}')
" 2>/dev/null)" \
  || { stop_hook_active="false"; last_message=""; }

if [[ "$stop_hook_active" == "true" ]]; then
  exit 0
fi

if [[ -z "$last_message" \
  || ${#last_message} -lt 50 ]]; then
  # Too short to be worth saving.
  exit 0
fi

# Truncate to a reasonable memory size.
summary=$(echo "$last_message" | python3 -c "
import sys
msg = sys.stdin.read().strip()
if len(msg) > 1000:
    msg = msg[:1000] + '...'
print(msg)
" 2>/dev/null || echo "")

if [[ -z "$summary" || ${#summary} -lt 10 ]]; then
  exit 0
fi

# Determine project name from working directory.
project_name=$(
  basename "${CLAUDE_PROJECT_DIR:-$(pwd)}" \
    2>/dev/null || echo "unknown"
)

# Save to SeekingContext.
metadata=$(python3 -c "
import json, os
print(json.dumps({
    'source': 'claude-code-auto',
    'project': os.environ.get(
        'SC_PROJECT', 'unknown'
    )
}))
" 2>/dev/null)

sc_store "$summary" "events" "$metadata" \
  >/dev/null 2>&1 || true
