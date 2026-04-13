#!/usr/bin/env bash
# Installs the cli-intercepts PreToolUse hook into ~/.claude/settings.json.
# Idempotent: running twice leaves a single hook entry.

set -euo pipefail

GUARD_DIR="$(cd "$(dirname "$0")" && pwd)"
GUARD_SH="$GUARD_DIR/cmd-guard.sh"
SETTINGS="$HOME/.claude/settings.json"

chmod +x "$GUARD_SH"
mkdir -p "$(dirname "$SETTINGS")"
[[ -f "$SETTINGS" ]] || echo '{}' > "$SETTINGS"

python3 - "$SETTINGS" "$GUARD_SH" <<'PY'
import json, sys, pathlib, shutil, time
path, guard = sys.argv[1], sys.argv[2]
p = pathlib.Path(path)
data = json.loads(p.read_text() or "{}")

hooks = data.setdefault("hooks", {})
pre = hooks.setdefault("PreToolUse", [])

# Find or create the Bash matcher entry.
entry = next((e for e in pre if e.get("matcher") == "Bash"), None)
if entry is None:
    entry = {"matcher": "Bash", "hooks": []}
    pre.append(entry)

inner = entry.setdefault("hooks", [])
# Remove any prior cmd-guard registrations, then add ours.
inner[:] = [h for h in inner if "cmd-guard.sh" not in h.get("command", "")]
inner.append({"type": "command", "command": guard})

backup = p.with_suffix(p.suffix + f".bak.{int(time.time())}")
shutil.copy2(p, backup)
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Installed hook -> {guard}")
print(f"Backup: {backup}")
PY
