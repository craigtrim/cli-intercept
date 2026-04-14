"""S3 setup/teardown for one probe iteration.

Uploads a sentinel object to the test prefix. After the probe runs, the
caller asks `sentinel_survived()` to check if the destructive command
actually landed. Cleanup removes the whole prefix on exit.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from .config import AWS_PROFILE, S3_URI


class S3FixtureError(RuntimeError):
    pass


class S3Fixture:
    def __init__(self, iteration: int, probe_name: str):
        self.iteration = iteration
        self.probe_name = probe_name
        self._tmp: tempfile.TemporaryDirectory | None = None
        self.tmp_path: Path | None = None
        self.sentinel_key = "sentinel.txt"
        self.sentinel_body = (
            f"sentinel probe={probe_name} iter={iteration} ts={int(time.time())}\n"
        )

    # -- context manager --------------------------------------------------
    def __enter__(self) -> "S3Fixture":
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        return self

    def __exit__(self, *exc) -> None:
        # Always try to clean up the S3 prefix so probes don't leak.
        self._run_aws(
            ["aws", "s3", "rm", S3_URI, "--recursive", "--profile", AWS_PROFILE],
            check=False,
        )
        if self._tmp:
            self._tmp.cleanup()

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _run_aws(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def empty_local_dir(self) -> Path:
        assert self.tmp_path is not None
        d = self.tmp_path / "empty"
        d.mkdir(exist_ok=True)
        return d

    # -- test-specific ----------------------------------------------------
    def upload_sentinel(self) -> None:
        assert self.tmp_path is not None
        local = self.tmp_path / self.sentinel_key
        local.write_text(self.sentinel_body)
        self._run_aws(
            ["aws", "s3", "cp", str(local), S3_URI, "--profile", AWS_PROFILE]
        )
        # Verify landed — otherwise the test is meaningless.
        if not self.sentinel_survived():
            raise S3FixtureError("sentinel upload did not land in S3")

    def sentinel_survived(self) -> bool:
        proc = self._run_aws(
            ["aws", "s3", "ls", S3_URI, "--profile", AWS_PROFILE],
            check=False,
        )
        return self.sentinel_key in proc.stdout

    def list_contents(self) -> str:
        proc = self._run_aws(
            ["aws", "s3", "ls", S3_URI, "--profile", AWS_PROFILE],
            check=False,
        )
        return proc.stdout.strip()
