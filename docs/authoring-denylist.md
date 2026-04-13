# Authoring Denylist Patterns

The guard matches with bash's `[[ string =~ regex ]]`. That engine is POSIX
ERE-ish, not PCRE. The gotchas below bite anyone coming from `grep -P`,
Python `re`, or JavaScript regex.

## Input preprocessing

Before matching, the command is normalized:

- Tabs and newlines become single spaces.
- Runs of spaces collapse to one.

So your pattern should assume single-space separators. Write `aws s3 sync`,
not `aws\s+s3\s+sync`.

## Pattern syntax cheatsheet

| Works                              | Does not work                    |
|------------------------------------|----------------------------------|
| `[[:space:]]`                      | `\s`                             |
| `[a-zA-Z0-9_]`                     | `\w`                             |
| `( \|$)` (space or end of string)  | `\b` (no word boundaries)        |
| `[^ ]+`                            | `.+?` (no lazy quantifiers)      |
| Parentheses for grouping           | Named groups, lookahead/behind   |

Anchors `^` and `$` work. Alternation `|` works. Character classes work.

## Writing a pattern

Template: match the **verb** of the destructive action plus the flag or
target that makes it destructive. Avoid matching a mere *mention* of the
verb inside a quoted string or a comment.

Examples from [guards/denylist.txt](../guards/denylist.txt):

```
aws s3 sync .* --delete         # verb + destructive flag
rm -rf +/( |$)                  # rm -rf rooted at / and nothing else
git push .* --force( |$)        # force flag at end or followed by space
git branch -D +(main|master)    # protected branch names explicitly
```

Notice `( |$)` as a poor-man's word boundary for flags. Without it,
`--force-with-lease` would also match `--force`, which is a false positive.

## False positives vs false negatives

- **False negative** (destructive command slips through) is the failure
  mode the project exists to prevent. Treat it as a bug.
- **False positive** (benign command blocked) is cheap: Claude sees the
  reason, picks another path, or asks the user. Prefer an over-broad rule
  to an under-broad one.

## Test every pattern

Every addition to `denylist.txt` gets at least two test cases in
[guards/test-guard.sh](../guards/test-guard.sh): one `block` that proves
it fires, and one `allow` that proves the boundary of what it does
**not** match. Run:

```bash
./guards/test-guard.sh
```

A pattern without matching tests is not committed.

## When regex is not enough

If a class of destructive commands cannot be expressed cleanly with bash
regex (for instance, "block any `aws` call whose resolved account is
production"), the correct move is **not** to add an LLM call. Options in
order of preference:

1. Expand the guard to shell out to a deterministic helper (e.g. `jq`
   against a static allowlist of account IDs).
2. Extend the input parsing so the regex has a richer normalized form
   to match against.
3. Add a second hook entry with its own script focused on that class.

Keep the hot path deterministic, offline, and sub-millisecond.
