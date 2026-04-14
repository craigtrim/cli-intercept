"""CLI entry point for the sandbox.

Invoked as `sandbox` via the poetry console script, or directly with
`python3 -m cli_intercepts.sandbox.cli`.

YOU run this. Claude does NOT run this.

Examples:
    sandbox --list
    sandbox --n 3
    sandbox --n 5 --probes direct,polite,guilt
    sandbox --n 3 --severity-min 6
    sandbox --n 3 --report reports/first-run.json

Exit 0 = every iteration BLOCKED or REFUSED (guard held).
Exit 1 = at least one BYPASS — see "BYPASS FINDINGS" section of the summary.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .probes import BaseProbe, load_all
from .runner import ProbeSelection, Runner, select_probes


def _default_report_path() -> Path:
    # Reports are build artefacts — go to repo root / reports/.
    repo_root = Path.cwd()
    return repo_root / "reports" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="sandbox",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-n", "--n", type=int, default=1,
                    help="iterations per probe (default 1)")
    ap.add_argument("--probes", type=str, default=None,
                    help="comma-separated probe names (default: all)")
    ap.add_argument("--severity-min", type=int, default=None)
    ap.add_argument("--severity-max", type=int, default=None)
    ap.add_argument("--report", type=str, default=None,
                    help="path to write JSON report "
                         "(default: reports/<timestamp>.json)")
    ap.add_argument("--no-report", action="store_true",
                    help="skip writing a JSON report")
    ap.add_argument("--list", action="store_true",
                    help="list registered probes and exit")
    args = ap.parse_args()

    if args.list:
        load_all()
        probes = sorted(BaseProbe.all_probes(), key=lambda p: (p.severity, p.name))
        print(f"{'name':20s} {'sev':>3s}  category")
        print("-" * 48)
        for p in probes:
            print(f"{p.name:20s} {p.severity:>3d}  {p.category}")
        return 0

    if args.n < 1:
        print("error: --n must be >= 1", file=sys.stderr)
        return 2

    names = [s.strip() for s in args.probes.split(",")] if args.probes else None
    probes = select_probes(names, args.severity_min, args.severity_max)
    if not probes:
        print("error: no probes matched selection", file=sys.stderr)
        return 2

    report_path: Path | None = None
    if args.no_report:
        report_path = None
    elif args.report:
        report_path = Path(args.report)
    else:
        report_path = _default_report_path()

    runner = Runner(ProbeSelection(probes=probes, n=args.n), report_path=report_path)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
