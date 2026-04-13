# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`cli-intercepts` installs a deterministic `PreToolUse` hook into Claude Code's `~/.claude/settings.json`. The hook inspects every `Bash` tool call against a regex denylist and blocks matches before execution. The point is *harness-enforced* guardrails: rules that cannot be forgotten by a prompt.

If you're editing this repo, you're working on the guardrail system itself. Be deliberate. A regression in the denylist or hook logic means destructive commands reach the shell.

Roadmap: extend the denylist to cover AWS CLI footguns (S3, IAM, ECS, etc.) with tuned patterns.

## Commands

```bash
./guards/install.sh      # Register hook in ~/.claude/settings.json (idempotent, backs up prior file)
./guards/uninstall.sh    # Remove hook
./guards/test-guard.sh   # Smoke test denylist patterns against sample commands
```

There is no Python build/test runner wired up yet. [pyproject.toml](pyproject.toml) declares a Poetry package but [src/cli_intercepts/](src/cli_intercepts/) and [tests/](tests/) are empty scaffolds. The functional code lives in [guards/](guards/) as shell plus inline Python.

After changing [guards/denylist.txt](guards/denylist.txt) or [guards/cmd-guard.sh](guards/cmd-guard.sh), always run `./guards/test-guard.sh` before committing.

## Architecture

**Hook contract.** Claude Code invokes the hook with the tool-call JSON on stdin. Exit `0` allows the command; exit `2` blocks it and shows stderr to Claude as the refusal reason. No other exit codes are part of the contract.

**Flow** ([guards/cmd-guard.sh](guards/cmd-guard.sh)):
1. Read JSON from stdin, extract `.tool_input.command` via inline `python3`.
2. Normalize whitespace (tabs/newlines to spaces, collapse runs) so `aws  s3   sync` still matches `aws s3 sync`.
3. Iterate [guards/denylist.txt](guards/denylist.txt); each non-blank, non-`#` line is a bash regex tested with `[[ =~ ]]`.
4. On first match: log to `~/.claude/guards/blocked.log`, print reason to stderr, exit `2`.

**Installer** ([guards/install.sh](guards/install.sh)) edits `~/.claude/settings.json` via inline Python: finds or creates the `hooks.PreToolUse` entry with `matcher: "Bash"`, removes any prior `cmd-guard.sh` registration, appends the new one. Always writes a timestamped `.bak.<epoch>` next to settings.json before overwriting. Re-running yields a single hook entry.

**Denylist override.** `CMD_GUARD_DENYLIST=/path/to/list` swaps in a different file per-shell. `CMD_GUARD_LOG` overrides the log location.

## Editing the denylist

Patterns are bash `[[ =~ ]]` regex (POSIX ERE-ish, *not* PCRE). Mind these:
- `\s` does not work; use literal spaces or `[[:space:]]`.
- Input is whitespace-normalized before matching, so match a single space.
- Goal is zero false-negatives on destructive ops. False positives are cheap (Claude sees the reason and picks another path).
- Add a test case to [guards/test-guard.sh](guards/test-guard.sh) for every new pattern: one `block` and one `allow` that proves the boundary.

## Design rationale (do not regress)

The guard is intentionally regex-based, not LLM-based: deterministic, zero-latency, zero-cost, offline, auditable. The failure mode being defended against is the model making a bad call. Delegating gatekeeping to another model reintroduces the same class of failure. Proposals to "make the guard smarter" by calling out to a model should be rejected.
