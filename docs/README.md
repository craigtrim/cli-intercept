# docs

Study notes for how `cli-intercepts` plugs into Claude Code's hook system.

- [claude-code-hooks.md](claude-code-hooks.md): reference for Claude Code's hook
  system itself (events, matchers, exit codes, stdin payloads, settings.json
  shape, advanced JSON output).
- [integration.md](integration.md): how this repo wires into that system:
  what the installer writes, what the guard reads, and the exact contract
  between hook and harness.
- [authoring-denylist.md](authoring-denylist.md): practical notes for writing
  and testing regex patterns against the bash `[[ =~ ]]` matcher used here.

Canonical upstream references:
- https://code.claude.com/docs/en/hooks.md
- https://code.claude.com/docs/en/hooks-guide.md
