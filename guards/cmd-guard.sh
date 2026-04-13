#!/usr/bin/env bash
# Claude Code PreToolUse hook — blocks Bash tool calls matching denylist patterns.
# Reads the tool call as JSON on stdin. Exits 0 to allow, 2 to block (stderr is
# shown to Claude as the reason).

set -u

GUARD_DIR="$(cd "$(dirname "$0")" && pwd)"
DENYLIST="${CMD_GUARD_DENYLIST:-$GUARD_DIR/denylist.txt}"
LOGFILE="${CMD_GUARD_LOG:-$HOME/.claude/guards/blocked.log}"

mkdir -p "$(dirname "$LOGFILE")"

# Extract .tool_input.command from the JSON payload on stdin.
cmd=$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("command",""))')

# Normalize whitespace so "aws  s3   sync" still matches "aws s3 sync".
normalized=$(printf '%s' "$cmd" | tr '\n\t' '  ' | tr -s ' ')

if [[ ! -f "$DENYLIST" ]]; then
  exit 0
fi

while IFS= read -r pattern || [[ -n "$pattern" ]]; do
  # Skip blanks and comments
  [[ -z "${pattern// }" ]] && continue
  [[ "$pattern" == \#* ]] && continue

  if [[ "$normalized" =~ $pattern ]]; then
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    printf '%s\tcwd=%s\tpattern=%s\tcmd=%s\n' "$ts" "$PWD" "$pattern" "$cmd" >> "$LOGFILE"
    reason="BLOCKED by cli-intercepts cmd-guard — matched pattern /$pattern/. If this is a false positive, edit $DENYLIST."
    # Emit an explicit deny decision. Per Claude Code hook merging rules, an
    # explicit "deny" beats another hook's "allow" — which plain exit 2 does not.
    python3 -c '
import json, sys
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": sys.argv[1],
  }
}))' "$reason"
    echo "$reason" >&2
    exit 2
  fi
done < "$DENYLIST"

exit 0
