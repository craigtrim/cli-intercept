"""Wraps `claude -p` and parses the stream-json output into ToolCall objects."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .config import AWS_PROFILE
from .result import ToolCall


class ClaudeInvoker:
    def __init__(self, timeout_s: int = 240):
        self.timeout_s = timeout_s

    def invoke(self, prompt: str, stream_path: Path) -> int:
        """Run claude -p. Returns the exit code. stream_path holds the JSONL."""
        with stream_path.open("w") as out:
            proc = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--allowedTools", "Bash",
                    "--output-format", "stream-json",
                    "--verbose",
                ],
                stdout=out,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_s,
                env={**os.environ, "AWS_PROFILE": AWS_PROFILE},
            )
        return proc.returncode

    @staticmethod
    def parse_stream(stream_path: Path) -> tuple[list[ToolCall], str]:
        """Return (tool_calls_in_order, final_assistant_text)."""
        uses: dict[str, ToolCall] = {}
        order: list[str] = []
        final_text = ""

        for line in stream_path.open():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            t = d.get("type")
            if t == "assistant":
                for c in d.get("message", {}).get("content", []):
                    if c.get("type") == "tool_use":
                        tid = c["id"]
                        if tid not in uses:
                            uses[tid] = ToolCall(
                                tool_use_id=tid,
                                name=c.get("name", ""),
                                command=(c.get("input") or {}).get("command", ""),
                                is_error=None,
                                result_text="",
                            )
                            order.append(tid)
                    elif c.get("type") == "text":
                        final_text = c.get("text", "")
            elif t == "user":
                for c in d.get("message", {}).get("content", []):
                    if c.get("type") == "tool_result":
                        tid = c.get("tool_use_id", "")
                        out = c.get("content", "")
                        if isinstance(out, list):
                            out = " | ".join(
                                x.get("text", "") for x in out if isinstance(x, dict)
                            )
                        if tid in uses:
                            uses[tid].is_error = c.get("is_error", False)
                            uses[tid].result_text = out or ""

        return [uses[tid] for tid in order], final_text
