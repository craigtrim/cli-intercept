# cli-intercepts

![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Ubuntu-blue)
![shell](https://img.shields.io/badge/shell-bash-green)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-MIT-lightgrey)
![status](https://img.shields.io/badge/status-alpha-orange)

Deterministic guardrails for Claude Code. A `PreToolUse` hook checks every
`Bash` tool call against a regex denylist and blocks matches before they run.
The harness enforces the rule, not a prompt Claude can forget.

Initial focus is filesystem, git, and infra footguns. The roadmap extends the
denylist to cover AWS CLI operations (S3, IAM, ECS, and friends) with tuned
patterns for destructive or high blast-radius calls.

## Install

```bash
./guards/install.sh
```

Registers [guards/cmd-guard.sh](guards/cmd-guard.sh) as a `PreToolUse` / `Bash`
hook in `~/.claude/settings.json` (prior file is backed up). Idempotent.
Restart your Claude Code session after install.

## Uninstall

```bash
./guards/uninstall.sh
```

## How it works

1. Claude Code pipes the tool call as JSON to the hook on stdin.
2. [guards/cmd-guard.sh](guards/cmd-guard.sh) extracts `.tool_input.command`,
   normalizes whitespace, and tests each pattern in
   [guards/denylist.txt](guards/denylist.txt).
3. On a match: exits `2`, logs to `~/.claude/guards/blocked.log`, and prints
   the reason to stderr. Claude sees the reason and picks a different path.
4. No match: exits `0`, command runs normally.

## Tuning the denylist

Edit [guards/denylist.txt](guards/denylist.txt). One bash-regex per line.
Blanks and `#` lines are ignored. The input is whitespace-normalized before
matching.

After edits, test with:

```bash
./guards/test-guard.sh
```

Point the guard at a different denylist per-shell with
`CMD_GUARD_DENYLIST=/path/to/list`.

## Why regex, not an LLM check?

Deterministic, zero-latency, zero-cost, offline, auditable. The failure mode
being defended against is the model making a bad call. Asking another model to
gatekeep reintroduces the same class of failure.
