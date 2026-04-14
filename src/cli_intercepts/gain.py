"""
`gain` — RTK-style summary of cmd-guard blocks.

Reads ~/.claude/guards/blocked.log (tab-delimited rows written by
guards/cmd-guard.sh) and prints per-pattern aggregates.

Wired via pyproject.toml as `gain = "cli_intercepts.gain:main"`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .colors import bold_, dim_, fail_, info_, pass_, warn_

DEFAULT_LOG = Path.home() / ".claude" / "guards" / "blocked.log"

LINE_RE = re.compile(
    r"^(?P<ts>\S+)\tcwd=(?P<cwd>[^\t]*)\tpattern=(?P<pattern>[^\t]*)\tcmd=(?P<cmd>.*)$"
)

SINCE_RE = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)
SINCE_UNITS = {
    "s": timedelta(seconds=1),
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
}


# -- data model -----------------------------------------------------------


@dataclass(frozen=True)
class BlockEvent:
    ts: datetime
    cwd: str
    pattern: str
    cmd: str


@dataclass
class Summary:
    total: int
    unique_patterns: int
    unique_projects: int
    since: str | None  # "14 days" etc.
    first_seen: str | None
    rows: list["PatternRow"] = field(default_factory=list)
    top_last_week: tuple[str, int] | None = None  # (pattern, count)


@dataclass
class PatternRow:
    pattern: str
    count: int
    last_fired_rel: str
    last_fired_abs: str
    top_cwd: str


# -- parsing --------------------------------------------------------------


def parse_log(text: str) -> tuple[list[BlockEvent], int]:
    """Return (events, malformed_line_count)."""
    events: list[BlockEvent] = []
    malformed = 0
    for raw in text.splitlines():
        if not raw.strip():
            continue
        m = LINE_RE.match(raw)
        if not m:
            malformed += 1
            continue
        try:
            ts = _parse_ts(m.group("ts"))
        except ValueError:
            malformed += 1
            continue
        events.append(
            BlockEvent(
                ts=ts,
                cwd=m.group("cwd"),
                pattern=m.group("pattern"),
                cmd=m.group("cmd"),
            )
        )
    return events, malformed


def _parse_ts(s: str) -> datetime:
    # Log format is ISO-8601 UTC with trailing 'Z'.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _parse_since(spec: str) -> timedelta:
    m = SINCE_RE.match(spec.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"--since expects like 1h, 2d, 1w, 30d — got {spec!r}"
        )
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * SINCE_UNITS[unit]


# -- rendering helpers ----------------------------------------------------


def _short_cwd(cwd: str) -> str:
    # Show the leaf directory, not the full path — keeps the table compact.
    if not cwd:
        return "-"
    return Path(cwd).name or cwd


def _rel_time(ts: datetime, now: datetime) -> str:
    delta = now - ts
    s = int(delta.total_seconds())
    if s < 0:
        return "just now"
    if s < 60:
        return f"{s}s ago"
    m = s // 60
    if m < 60:
        return f"{m}m ago"
    h = m // 60
    if h < 24:
        return f"{h}h ago"
    d = h // 24
    if d < 2:
        return "yesterday"
    if d < 60:
        return f"{d}d ago"
    return ts.astimezone().strftime("%Y-%m-%d")


# -- summary construction -------------------------------------------------


def build_summary(events: list[BlockEvent], now: datetime | None = None) -> Summary:
    now = now or datetime.now(tz=timezone.utc)
    if not events:
        return Summary(
            total=0, unique_patterns=0, unique_projects=0,
            since=None, first_seen=None,
        )

    counts = Counter(e.pattern for e in events)
    last_seen: dict[str, datetime] = {}
    cwd_per_pattern: dict[str, Counter[str]] = defaultdict(Counter)
    for e in events:
        if e.ts > last_seen.get(e.pattern, datetime.min.replace(tzinfo=timezone.utc)):
            last_seen[e.pattern] = e.ts
        cwd_per_pattern[e.pattern][_short_cwd(e.cwd)] += 1

    rows: list[PatternRow] = []
    for pat, n in counts.most_common():
        last = last_seen[pat]
        top_cwd = cwd_per_pattern[pat].most_common(1)[0][0]
        rows.append(PatternRow(
            pattern=pat,
            count=n,
            last_fired_rel=_rel_time(last, now),
            last_fired_abs=last.isoformat(timespec="seconds"),
            top_cwd=top_cwd,
        ))

    first = min(e.ts for e in events)
    since_days = max(1, (now - first).days)
    since = f"{since_days} day" + ("s" if since_days != 1 else "")

    # Top pattern in last 7 days.
    cutoff = now - timedelta(days=7)
    last_week = Counter(e.pattern for e in events if e.ts >= cutoff)
    top_week = last_week.most_common(1)[0] if last_week else None

    return Summary(
        total=len(events),
        unique_patterns=len(counts),
        unique_projects=len({e.cwd for e in events if e.cwd}),
        since=since,
        first_seen=first.astimezone().strftime("%Y-%m-%d"),
        rows=rows,
        top_last_week=top_week,
    )


# -- rendering ------------------------------------------------------------


def render_default(summary: Summary, pattern_col_w: int = 36) -> str:
    if summary.total == 0:
        return dim_("no blocks recorded yet")

    lines: list[str] = []
    top = "╭─ cli-intercepts guard — block summary " + "─" * 28 + "╮"
    bot = "╰" + "─" * (len(top) - 2) + "╯"
    lines.append(info_(bold_(top)))
    lines.append(f"  since first block:  {info_(summary.first_seen)}"
                 f"  ({dim_(summary.since)})")
    lines.append(f"  total blocks:       {pass_(str(summary.total))}")
    lines.append(f"  unique patterns:    {info_(str(summary.unique_patterns))}")
    lines.append(f"  unique projects:    {info_(str(summary.unique_projects))}")
    lines.append(info_(bold_(bot)))
    lines.append("")

    header = f"{'pattern':<{pattern_col_w}s} {'blocks':>6s}   {'last fired':<14s}  top cwd"
    lines.append(bold_(header))
    lines.append(dim_("─" * (pattern_col_w + 40)))

    for row in summary.rows:
        pat = row.pattern
        if len(pat) > pattern_col_w:
            pat = pat[: pattern_col_w - 1] + "…"
        lines.append(
            f"{info_(f'{pat:<{pattern_col_w}s}')} "
            f"{pass_(f'{row.count:>6d}')}   "
            f"{dim_(f'{row.last_fired_rel:<14s}')}  "
            f"{row.top_cwd}"
        )

    if summary.top_last_week:
        lines.append("")
        pat, n = summary.top_last_week
        lines.append(
            f"most-blocked last 7 days:  "
            f"{info_(pat)} {dim_(f'({n} hits)')}"
        )

    return "\n".join(lines)


def render_pattern_detail(events: list[BlockEvent], needle: str) -> str:
    matched = [e for e in events if needle in e.pattern]
    if not matched:
        return warn_(f"no blocks matched pattern filter: {needle!r}")
    lines = [bold_(f"pattern filter: {info_(needle)}  ({len(matched)} hit(s))"), ""]
    for e in sorted(matched, key=lambda x: x.ts, reverse=True):
        lines.append(
            f"{dim_(e.ts.astimezone().strftime('%Y-%m-%d %H:%M:%S'))}  "
            f"{info_(e.pattern)}"
        )
        lines.append(f"  {dim_('cwd:')} {e.cwd}")
        lines.append(f"  {dim_('cmd:')} {e.cmd[:200]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_history(events: list[BlockEvent], n: int) -> str:
    if not events:
        return dim_("no blocks recorded yet")
    tail = events[-n:]
    lines = [bold_(f"last {len(tail)} block(s):"), ""]
    for e in tail:
        lines.append(
            f"{dim_(e.ts.astimezone().strftime('%Y-%m-%d %H:%M:%S'))}  "
            f"{fail_('BLOCK')}  {info_(e.pattern)}"
        )
        lines.append(f"  {dim_(e.cwd)}")
        lines.append(f"  {e.cmd[:200]}")
    return "\n".join(lines)


# -- clear -----------------------------------------------------------------


def archive_log(log_path: Path) -> Path:
    """Rename the log to blocked.log.<ts>. Return the archive path."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = log_path.with_name(log_path.name + f".{ts}")
    log_path.rename(dest)
    return dest


# -- CLI -------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="gain",
        description=(
            "Summarize cmd-guard blocked-command history "
            f"(reads {DEFAULT_LOG})"
        ),
    )
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG,
                    help=f"path to blocked.log (default {DEFAULT_LOG})")
    ap.add_argument("--since", type=_parse_since, default=None,
                    help="only include blocks within this window (e.g. 7d, 24h)")
    ap.add_argument("--pattern", type=str, default=None,
                    help="deep-dive mode: show all blocks for patterns "
                         "containing this substring")
    ap.add_argument("--history", nargs="?", type=int, const=20, default=None,
                    help="show the last N raw entries (default 20)")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of the colored summary")
    ap.add_argument("--clear", action="store_true",
                    help="archive the log to blocked.log.<ts> and exit")
    args = ap.parse_args()

    log_path: Path = args.log

    if args.clear:
        if not log_path.exists():
            print(f"nothing to archive (no log at {log_path})")
            return 0
        dest = archive_log(log_path)
        print(f"archived → {dest}")
        return 0

    if not log_path.exists():
        print(dim_(f"no log at {log_path} — guard has not fired yet"))
        return 0

    text = log_path.read_text()
    events, malformed = parse_log(text)
    if malformed:
        print(warn_(f"warning: skipped {malformed} malformed line(s)"), file=sys.stderr)

    # Apply --since filter before anything else.
    if args.since is not None:
        cutoff = datetime.now(tz=timezone.utc) - args.since
        events = [e for e in events if e.ts >= cutoff]

    if args.pattern is not None:
        print(render_pattern_detail(events, args.pattern))
        return 0

    if args.history is not None:
        print(render_history(events, args.history))
        return 0

    summary = build_summary(events)

    if args.json:
        payload = asdict(summary)
        print(json.dumps(payload, default=str, indent=2))
        return 0

    print(render_default(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
