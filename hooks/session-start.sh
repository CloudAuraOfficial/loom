#!/usr/bin/env bash
# Loom SessionStart hook — banner showing current workflow + stage.
# Composes with other SessionStart hooks (e.g. claude-mem).

set -uo pipefail

LOOM_HOME="${LOOM_HOME:-$HOME/loom}"

python3 "$LOOM_HOME/scripts/loom_lib.py" status 2>/dev/null | python3 -c '
import json, sys
try:
    s = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not s.get("loom"):
    sys.exit(0)
stage = s.get("current_stage") or "(none)"
owner = s.get("owner_agent") or "?"
wf = s.get("workflow")
cycle = s.get("cycle")
art = s.get("artifact_path") or ""
print(f"🧵 loom: {wf} · cycle {cycle} · stage `{stage}` (owner: {owner})")
if art:
    print(f"   artifact: {art}")
' || true

exit 0
