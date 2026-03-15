#!/usr/bin/env bash
# common.sh — Shared helpers for SeekingContext hooks.
# Sourced by all hook scripts.
#
# SEEKING_CONTEXT_API_URL defaults to http://127.0.0.1:9377.
# SEEKING_CONTEXT_NAMESPACE defaults to "claude-code".
# Optional SEEKING_CONTEXT_API_KEY for authenticated access.

set -euo pipefail

SC_API_URL="${SEEKING_CONTEXT_API_URL:-http://127.0.0.1:9377}"
SC_NAMESPACE="${SEEKING_CONTEXT_NAMESPACE:-claude-code}"
SC_API_KEY="${SEEKING_CONTEXT_API_KEY:-}"

# sc_check_server — Verify the REST API is reachable.
sc_check_server() {
  curl -sf --max-time 3 \
    "${SC_API_URL}/v1/status" >/dev/null 2>&1
}

# sc_headers — Build common HTTP headers.
sc_headers() {
  local headers=(-H "Content-Type: application/json")
  headers+=(-H "X-Namespace: ${SC_NAMESPACE}")
  if [[ -n "$SC_API_KEY" ]]; then
    headers+=(-H "Authorization: Bearer ${SC_API_KEY}")
  fi
  echo "${headers[@]}"
}

# sc_get <path> — GET request to SeekingContext API.
sc_get() {
  local path="$1"
  eval curl -sf --max-time 8 \
    "$(sc_headers)" \
    "\"${SC_API_URL}${path}\""
}

# sc_post <path> <json_body> — POST request.
sc_post() {
  local path="$1"
  local body="$2"
  eval curl -sf --max-time 8 \
    "$(sc_headers)" \
    -d "'${body}'" \
    "\"${SC_API_URL}${path}\""
}

# sc_search <query> [limit] — Search memories.
sc_search() {
  local query="$1"
  local limit="${2:-10}"
  local body
  body=$(python3 -c "
import json, sys
print(json.dumps({
    'query': sys.argv[1],
    'top_k': int(sys.argv[2]),
    'level': 2
}))
" "$query" "$limit" 2>/dev/null)
  sc_post "/v1/memories/search" "$body"
}

# sc_store <content> <category> [metadata_json] — Store.
sc_store() {
  local content="$1"
  local category="${2:-entities}"
  local metadata="${3:-{}}"
  local body
  body=$(python3 -c "
import json, sys
print(json.dumps({
    'content': sys.argv[1],
    'category': sys.argv[2],
    'metadata': json.loads(sys.argv[3])
}))
" "$content" "$category" "$metadata" 2>/dev/null)
  sc_post "/v1/memories" "$body"
}

# read_stdin — Read stdin into \$HOOK_INPUT.
read_stdin() {
  local input=""
  if read -t 2 -r input 2>/dev/null; then
    HOOK_INPUT="$input"
  else
    HOOK_INPUT="{}"
  fi
}
