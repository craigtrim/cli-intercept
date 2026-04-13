#!/usr/bin/env bash
# Removes the cli-intercepts PreToolUse hook from ~/.claude/settings.json.
set -euo pipefail
SETTINGS="$HOME/.claude/settings.json"
[[ -f "$SETTINGS" ]] || { echo "No settings at $SETTINGS"; exit 0; }

python3 - "$SETTINGS" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text() or "{}")
pre = data.get("hooks", {}).get("PreToolUse", [])
for e in pre:
    e["hooks"] = [h for h in e.get("hooks", []) if "cmd-guard.sh" not in h.get("command","")]
data.get("hooks", {})["PreToolUse"] = [e for e in pre if e.get("hooks")]
p.write_text(json.dumps(data, indent=2) + "\n")
print("Uninstalled cmd-guard hook.")
PY
