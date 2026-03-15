#!/usr/bin/env bash
# session-start.sh — Load relevant memories on session
# start and inject them as additionalContext.
# Hook: SessionStart (sync, timeout: 10s)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

read_stdin

# If server not reachable, exit silently.
if ! sc_check_server 2>/dev/null; then
  exit 0
fi

# Fetch the 20 most recent memories.
response=$(sc_get "/v1/memories?limit=20" \
  2>/dev/null || echo "")

if [[ -z "$response" ]]; then
  exit 0
fi

# Format memories into a readable context block.
context=$(echo "$response" | python3 -c "
import json, sys

try:
    data = json.load(sys.stdin)
    # Handle both list and dict response formats
    if isinstance(data, list):
        memories = data
    else:
        memories = data.get('memories', data)

    if not memories or not isinstance(memories, list):
        sys.exit(0)

    lines = [
        '[seeking-context] Recalled memories:',
        ''
    ]
    for m in memories[:20]:
        cat = m.get('category', 'entities')
        content = m.get('content', '')
        # Truncate long content for context injection.
        if len(content) > 500:
            content = content[:500] + '...'
        # Escape angle brackets to prevent injection.
        content = (
            content
            .replace('<', '&lt;')
            .replace('>', '&gt;')
        )
        lines.append(f'- [{cat}] {content}')
        lines.append('')
    print('\n'.join(lines))
except Exception:
    pass
" 2>/dev/null || echo "")

if [[ -z "$context" ]]; then
  exit 0
fi

# Return additionalContext for Claude's context.
SC_CONTEXT="$context" python3 -c "
import json, os
output = {
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': os.environ['SC_CONTEXT']
    }
}
print(json.dumps(output))
"
