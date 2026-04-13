#!/usr/bin/env bash
# Smoke-tests cmd-guard.sh against a few commands. Run directly.
set -u
GUARD="$(cd "$(dirname "$0")" && pwd)/cmd-guard.sh"

check() {
  local expect="$1" cmd="$2"
  local payload
  payload=$(python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.argv[1]}}))' "$cmd")
  echo "$payload" | bash "$GUARD" >/dev/null 2>&1
  local rc=$?
  if [[ "$expect" == "block" && $rc -eq 2 ]] || [[ "$expect" == "allow" && $rc -eq 0 ]]; then
    echo "PASS  [$expect] $cmd"
  else
    echo "FAIL  [$expect got rc=$rc] $cmd"
  fi
}

check block "aws s3 sync dist/ s3://craigtrim.com/demos/ --delete"
check block "aws  s3   sync  dist/ s3://foo/ --delete"
check block "git push origin main --force"
check block "rm -rf /"
check block "terraform destroy -auto-approve"
check allow "aws s3 sync dist/ s3://craigtrim.com/demos/"
check allow "git status"
check allow "ls -la"
check allow "echo 'rm -rf /' # harmless quoted"
