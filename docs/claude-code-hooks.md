# Claude Code Hooks: Reference

Upstream: https://code.claude.com/docs/en/hooks.md

Hooks are harness-executed shell commands, HTTP webhooks, prompts, or agents
that Claude Code fires at defined points in a session. Because the harness
runs them (not the model), they are deterministic: the model cannot skip,
forget, or reason its way past them.

## Events

**Session-level** (once per session)
- `SessionStart`, `SessionEnd`

**Turn-level** (once per Claude response)
- `UserPromptSubmit`, `Stop`, `StopFailure`

**Tool-level** (per tool call)
- `PreToolUse`, `PostToolUse`, `PermissionRequest`, `PermissionDenied`

**Async / notification** (fire without blocking)
- `FileChanged`, `ConfigChange`, `CwdChanged`, `WorktreeCreate`/`Remove`,
  `Notification`, `SubagentStart`/`Stop`, `TaskCreated`/`Completed`,
  `InstructionsLoaded`, `PreCompact`/`PostCompact`,
  `Elicitation`/`ElicitationResult`

All events pipe JSON on stdin with common fields: `session_id`,
`transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, `agent_id`,
`agent_type`.

## Matchers

The `matcher` field narrows which invocations trigger a hook. Semantics vary
by event:

| Event(s)                        | Matcher meaning                                                |
|---------------------------------|----------------------------------------------------------------|
| `PreToolUse`, `PostToolUse`     | Tool name. Literal (`"Bash"`), pipe-union (`"Edit\|Write"`), or regex when non-alphanumeric chars are present (`"mcp__memory__.*"`). |
| `SessionStart`                  | Session source: `startup`, `resume`, `clear`, `compact`.       |
| `Notification`                  | Notification type: `permission_prompt`, `idle_prompt`.         |
| `FileChanged`                   | Literal filename union (no regex).                             |
| `Stop`, `UserPromptSubmit`, ... | Matcher ignored.                                               |

## Exit codes

Command hooks signal decisions via exit code:

| Code       | Meaning                                                           |
|------------|-------------------------------------------------------------------|
| `0`        | Allow. Stdout is parsed as JSON if present (see advanced output). |
| `2`        | Block. Stderr is shown to Claude as the refusal reason.           |
| other != 0 | Non-blocking error. Execution continues; stderr is logged.        |

Rule of thumb: `2` is the only code that stops the action.

## PreToolUse stdin (Bash example)

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/current/working/directory",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "git push --force origin main"
  }
}
```

`tool_input` is the verbatim argument object for the tool. For `Bash`, the
command string lives at `.tool_input.command`. Other tools expose different
shapes (e.g. `Edit` exposes `file_path`, `old_string`, `new_string`).

## settings.json shape

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/abs/path/to/cmd-guard.sh",
            "timeout": 600
          }
        ]
      }
    ]
  }
}
```

Locations (later overrides earlier):
- `~/.claude/settings.json` (all projects)
- `<project>/.claude/settings.json` (checked in)
- `<project>/.claude/settings.local.json` (gitignored, personal)

Multiple entries for the same matcher compose in order; the first `exit 2`
blocks and the remainder are skipped.

## Hook types

| Type        | Use                                                                |
|-------------|--------------------------------------------------------------------|
| `command`   | Shell command. Receives JSON on stdin. Default timeout 600s.       |
| `http`      | Webhook POST. Default timeout 30s. Supports `headers`.             |
| `prompt`    | Ad-hoc LLM query. Default timeout 60s.                             |
| `agent`     | Dispatched to a named Claude agent. Default timeout 60s.           |

## Advanced: JSON output

An `exit 0` hook may write JSON to stdout for fine-grained control:

```json
{
  "continue": true,
  "decision": "block|allow|ask|defer",
  "reason": "Explanation shown to Claude",
  "hookSpecificOutput": {
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "why",
    "updatedInput": { "command": "rewritten command" },
    "additionalContext": "extra context injected into the turn"
  }
}
```

`updatedInput` is powerful: a `PreToolUse` hook can rewrite the tool input
before execution. `additionalContext` injects text Claude sees.

`cli-intercepts` deliberately does not use JSON output. Exit `2` plus a
stderr message is simpler, auditable, and sufficient for a pure denylist.
