#!/usr/bin/env bash
# Loom PreToolUse hook — the Context Router.
#
# Env vars:
#   LOOM_LOG_ONLY=1  (default): log decisions, never block.
#   LOOM_LOG_ONLY=0           : enforce — exit 2 with a message when blocked.
#   LOOM_BYPASS=1             : skip Loom entirely for this tool call.
#
# Always passes through on any error; never block Claude due to a Loom bug.

set -uo pipefail

LOOM_HOME="${LOOM_HOME:-$HOME/loom}"

if [[ "${LOOM_BYPASS:-0}" == "1" ]]; then
    exit 0
fi

# Read tool name from stdin payload (Claude Code hook contract: JSON)
TOOL_PAYLOAD="$(cat 2>/dev/null || true)"
TOOL_NAME="$(echo "$TOOL_PAYLOAD" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("tool_name",""))
except Exception:
    print("")' 2>/dev/null || echo "")"

if [[ -z "$TOOL_NAME" ]]; then
    exit 0
fi

# Decision script
DECISION="$(python3 "$LOOM_HOME/scripts/loom_lib.py" router "$TOOL_NAME" 2>/dev/null || echo "allow:error")"
ACTION="${DECISION%%:*}"
REASON="${DECISION#*:}"

if [[ "$ACTION" == "block" ]]; then
    if [[ "${LOOM_LOG_ONLY:-1}" == "1" ]]; then
        echo "loom: would-block $TOOL_NAME ($REASON) [LOG_ONLY]" >&2
        exit 0
    else
        echo "loom: blocked $TOOL_NAME — $REASON" >&2
        echo "Set LOOM_BYPASS=1 to override, or advance to a compatible stage." >&2
        exit 2
    fi
fi

exit 0
