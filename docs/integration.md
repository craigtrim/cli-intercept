# How cli-intercepts Integrates

Two moving parts: an **installer** that edits Claude Code's settings, and a
**guard script** that the harness invokes on every `Bash` tool call.

## The installer

[guards/install.sh](../guards/install.sh) mutates `~/.claude/settings.json`
so that Claude Code knows to call our guard. The install is pure JSON
surgery via inline `python3`:

1. Ensure `~/.claude/settings.json` exists (creates `{}` if missing).
2. Load it as JSON.
3. Descend to `hooks.PreToolUse`, creating the list if absent.
4. Find the entry whose `matcher == "Bash"`, creating one if absent.
5. Inside that entry's inner `hooks` array, drop any prior
   `cmd-guard.sh` registration, then append a fresh one pointing at the
   absolute path of [guards/cmd-guard.sh](../guards/cmd-guard.sh).
6. Write a timestamped backup (`settings.json.bak.<epoch>`) before
   overwriting.

The resulting settings.json fragment looks like:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "/Users/you/.../guards/cmd-guard.sh" }
        ]
      }
    ]
  }
}
```

Idempotency comes from step 5: prior registrations of the same script are
removed before append, so re-running leaves exactly one entry.

## The guard

[guards/cmd-guard.sh](../guards/cmd-guard.sh) implements the
`PreToolUse` contract:

1. **Read**: Claude Code pipes the tool-call JSON to stdin. We extract
   `.tool_input.command` with inline `python3`. No shell parsing of JSON.
2. **Normalize**: collapse tabs and newlines to spaces, then squeeze runs
   of spaces. This means `aws  s3   sync` matches a pattern written for
   `aws s3 sync`.
3. **Match**: iterate [guards/denylist.txt](../guards/denylist.txt). Each
   non-blank, non-`#` line is a bash `[[ =~ ]]` regex tested against the
   normalized command.
4. **Decide**: on first match, append a row to
   `~/.claude/guards/blocked.log`, print a multi-line reason to stderr,
   and `exit 2`. Otherwise `exit 0`.

The guard never calls out to a network, an LLM, or any external tool
beyond `python3` for stdin JSON extraction. This is the deterministic,
offline, zero-latency property the project depends on.

## Why `exit 2` is enough

Claude Code's hook contract surfaces a blocking hook's stderr directly to
the model as the refusal reason. That means we get structured
communication back to Claude without needing the richer JSON output
channel:

```
BLOCKED by cli-intercepts cmd-guard
Matched pattern: /git push .* --force( |$)/
Command: git push origin main --force
If this is a false positive, edit /path/to/denylist.txt.
```

Claude sees all four lines and typically picks a different approach.
If we ever need to **rewrite** a command instead of blocking it (for
example, inject `--dry-run`), we would switch to the JSON output channel
described in [claude-code-hooks.md](claude-code-hooks.md). That is an
explicit non-goal today.

## What the guard does not do

- **No `PostToolUse` hook.** We do not observe outputs. Prevention only.
- **No matcher beyond `"Bash"`.** Edits, writes, reads, and MCP tool
  calls pass through untouched. All of this project's surface area is
  "what shell command is about to run".
- **No per-project override logic.** The denylist path is global unless
  the user sets `CMD_GUARD_DENYLIST` in their shell.
- **No auto-update.** Installer pins the absolute path of the script at
  install time. Move the repo and you must reinstall.

## Uninstall

[guards/uninstall.sh](../guards/uninstall.sh) performs the inverse
surgery: walks `hooks.PreToolUse[*].hooks[*]` and removes any entry whose
`command` contains `cmd-guard.sh`, pruning empty parents as it goes.
Backup is written the same way as install.

## End-to-end trace of a blocked call

```
Claude decides to run:   aws s3 sync dist/ s3://bucket/ --delete
Harness fires:           PreToolUse hook (matcher "Bash")
Stdin to cmd-guard.sh:   {"tool_name":"Bash","tool_input":{"command":"aws s3 sync dist/ s3://bucket/ --delete"}, ...}
Guard extracts:          aws s3 sync dist/ s3://bucket/ --delete
Guard normalizes:        aws s3 sync dist/ s3://bucket/ --delete
Guard matches pattern:   aws s3 sync .* --delete
Guard logs to:           ~/.claude/guards/blocked.log
Guard stderr:            BLOCKED by cli-intercepts cmd-guard ...
Guard exits:             2
Harness reports to Claude:  refusal reason = stderr
Claude reconsiders:      tries a non-destructive sync or asks user
```

That flow is the entire product.
