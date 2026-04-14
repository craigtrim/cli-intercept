"""Unit tests for cli_intercepts.gain (no AWS, no Claude, no filesystem side-effects)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cli_intercepts.gain import (
    BlockEvent,
    _parse_since,
    _parse_ts,
    _rel_time,
    build_summary,
    parse_log,
    render_default,
    render_history,
    render_pattern_detail,
)


def _fixture_log(now: datetime) -> str:
    """Build a synthetic blocked.log payload with events at known offsets."""

    def row(offset: timedelta, cwd: str, pattern: str, cmd: str) -> str:
        ts = (now - offset).strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"{ts}\tcwd={cwd}\tpattern={pattern}\tcmd={cmd}"

    lines = [
        # 3 of pattern A, two projects
        row(timedelta(minutes=5),  "/u/a/cli-intercepts", "pat-A", "cmd1"),
        row(timedelta(hours=3),    "/u/a/cli-intercepts", "pat-A", "cmd2"),
        row(timedelta(days=2),     "/u/a/demos",          "pat-A", "cmd3"),
        # 2 of pattern B
        row(timedelta(days=1),     "/u/a/cli-intercepts", "pat-B", "cmdX"),
        row(timedelta(days=5),     "/u/a/cli-intercepts", "pat-B", "cmdY"),
        # 1 very old event, outside a 7d window
        row(timedelta(days=30),    "/u/a/sandbox",        "pat-C", "cmdZ"),
        # malformed line
        "this is garbage not tab delimited",
        # blank line
        "",
    ]
    return "\n".join(lines) + "\n"


def test_parse_log_tolerates_malformed():
    now = datetime.now(timezone.utc)
    events, malformed = parse_log(_fixture_log(now))
    assert len(events) == 6
    assert malformed == 1


def test_parse_ts_utc_z():
    ts = _parse_ts("2026-04-13T23:36:14Z")
    assert ts.tzinfo is not None
    assert ts.utcoffset() == timedelta(0)


def test_parse_since_valid_units():
    assert _parse_since("1h") == timedelta(hours=1)
    assert _parse_since("2d") == timedelta(days=2)
    assert _parse_since("1w") == timedelta(weeks=1)
    assert _parse_since("30d") == timedelta(days=30)


def test_parse_since_rejects_junk():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_since("banana")


def test_build_summary_aggregates():
    now = datetime.now(timezone.utc)
    events, _ = parse_log(_fixture_log(now))
    summary = build_summary(events, now=now)
    assert summary.total == 6
    assert summary.unique_patterns == 3
    assert summary.unique_projects == 3
    # pat-A is most common
    assert summary.rows[0].pattern == "pat-A"
    assert summary.rows[0].count == 3
    # top cwd for pat-A is cli-intercepts (appears twice)
    assert summary.rows[0].top_cwd == "cli-intercepts"


def test_build_summary_top_last_week():
    now = datetime.now(timezone.utc)
    events, _ = parse_log(_fixture_log(now))
    summary = build_summary(events, now=now)
    # pat-A has 3 recent hits, pat-B has 2, pat-C is 30d old (excluded)
    assert summary.top_last_week is not None
    assert summary.top_last_week[0] == "pat-A"
    assert summary.top_last_week[1] == 3


def test_since_filter_narrows_events():
    now = datetime.now(timezone.utc)
    events, _ = parse_log(_fixture_log(now))
    cutoff = now - timedelta(days=1, hours=1)
    recent = [e for e in events if e.ts >= cutoff]
    # Events within ~1 day: the 5m, 3h ones for pat-A, and the 1d one for pat-B
    assert len(recent) == 3
    patterns = {e.pattern for e in recent}
    assert patterns == {"pat-A", "pat-B"}


def test_pattern_filter_narrows():
    now = datetime.now(timezone.utc)
    events, _ = parse_log(_fixture_log(now))
    output = render_pattern_detail(events, "pat-A")
    assert "pat-A" in output
    assert "pat-B" not in output
    assert "cmd1" in output


def test_empty_log_summary():
    summary = build_summary([])
    assert summary.total == 0
    assert summary.unique_patterns == 0
    out = render_default(summary)
    assert "no blocks recorded yet" in out


def test_rel_time_buckets():
    now = datetime.now(timezone.utc)
    assert _rel_time(now - timedelta(seconds=5), now) == "5s ago"
    assert _rel_time(now - timedelta(minutes=5), now) == "5m ago"
    assert _rel_time(now - timedelta(hours=3), now) == "3h ago"
    assert _rel_time(now - timedelta(days=1, hours=2), now) == "yesterday"
    assert _rel_time(now - timedelta(days=5), now) == "5d ago"


def test_render_history_returns_tail():
    now = datetime.now(timezone.utc)
    events, _ = parse_log(_fixture_log(now))
    out = render_history(events, 2)
    # exactly two events described
    assert out.count("BLOCK") == 2


def _run_cli(tmp_path: Path, log_contents: str, *args: str) -> subprocess.CompletedProcess:
    log = tmp_path / "blocked.log"
    log.write_text(log_contents)
    cmd = [sys.executable, "-m", "cli_intercepts.gain", "--log", str(log), *args]
    env = {**os.environ, "NO_COLOR": "1"}  # strip ANSI for assertions
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def test_cli_default_exits_zero(tmp_path):
    now = datetime.now(timezone.utc)
    proc = _run_cli(tmp_path, _fixture_log(now))
    assert proc.returncode == 0
    assert "total blocks:" in proc.stdout
    assert "pat-A" in proc.stdout


def test_cli_json_emits_valid_json(tmp_path):
    now = datetime.now(timezone.utc)
    proc = _run_cli(tmp_path, _fixture_log(now), "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["total"] == 6
    assert payload["unique_patterns"] == 3
    assert any(r["pattern"] == "pat-A" for r in payload["rows"])


def test_cli_empty_log_message(tmp_path):
    proc = _run_cli(tmp_path, "")
    assert proc.returncode == 0
    assert "no blocks recorded yet" in proc.stdout


def test_cli_since_filter(tmp_path):
    now = datetime.now(timezone.utc)
    proc = _run_cli(tmp_path, _fixture_log(now), "--since", "1d", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    # With --since 1d, pat-C (30d old) and one pat-B (5d) are excluded.
    patterns = {r["pattern"] for r in payload["rows"]}
    assert "pat-C" not in patterns


def test_cli_pattern_deep_dive(tmp_path):
    now = datetime.now(timezone.utc)
    proc = _run_cli(tmp_path, _fixture_log(now), "--pattern", "pat-A")
    assert proc.returncode == 0
    assert "pat-A" in proc.stdout
    assert "cmd1" in proc.stdout
    assert "pat-B" not in proc.stdout
