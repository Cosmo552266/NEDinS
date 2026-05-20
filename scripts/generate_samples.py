"""Generate N sample campaigns (default 3) in dry-run mode.

Used to seed the repo with example artifacts so reviewers can read the
output shape without API keys. With real GEMINI_API_KEY (and NEDINS_DRY_RUN
unset) the same script produces real campaigns.

Usage:
    PYTHONPATH=src python scripts/generate_samples.py --count 3 --dry-run
"""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start", type=str, default="",
                        help="ISO start date; defaults to today")
    parser.add_argument("--step-days", type=int, default=3)
    args = parser.parse_args()

    if args.dry_run:
        os.environ["NEDINS_DRY_RUN"] = "true"

    # Import after env so dry-run flag is honoured.
    from nedins.orchestrator import run as run_pipeline

    start = date.fromisoformat(args.start) if args.start else date.today()
    for i in range(args.count):
        target = start + timedelta(days=i * args.step_days)
        print(f"\n=== sample {i+1}/{args.count} target={target} ===")
        run_pipeline(
            dry_run=args.dry_run,
            target=target.isoformat(),
            resume="",
            skip="",
        )


if __name__ == "__main__":
    main()
