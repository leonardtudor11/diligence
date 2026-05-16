"""CLI runner — orchestrate the full Diligence agent graph for a ticker.

Usage:

    python -m agents.run NVDA                  # full run, no cache reuse
    python -m agents.run NVDA --reuse-cache    # skip any agent whose output
                                               # already exists on disk
    python -m agents.run NVDA --data-dir data  # override cache root

The graph reads `data/{ticker}/{10k,10q,transcript}.json` (produced by
`services.ingest`) and writes:

    data/{ticker}/analysis_filing.json
    data/{ticker}/analysis_call.json
    data/{ticker}/analysis_bull.json
    data/{ticker}/analysis_bear.json
    data/{ticker}/reconciliation.json

With `--reuse-cache`, every node that finds its output JSON on disk skips
its model call. Useful for iterating on the reconciler prompt without
re-spending Gemini + Featherless credits on filing/call/bull/bear.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.graph import run_for_ticker  # noqa: E402


def _main() -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.run")
    ap.add_argument("ticker", help="e.g. NVDA")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument(
        "--reuse-cache",
        action="store_true",
        help="skip any agent whose output JSON already exists on disk",
    )
    args = ap.parse_args()

    ticker_dir = args.data_dir / args.ticker
    if not ticker_dir.exists():
        print(f"error: {ticker_dir} does not exist")
        print(f"hint: run `python -m services.ingest {args.ticker}` first")
        return 2

    t0 = time.monotonic()
    final_state = asyncio.run(
        run_for_ticker(args.ticker, args.data_dir, reuse_cache=args.reuse_cache)
    )
    wall = time.monotonic() - t0

    agents = final_state.get("agents", {})
    print(
        f"\n[run] {args.ticker} graph complete in {wall:.1f}s. "
        f"agents written: {sorted(agents.keys())}"
    )

    reconciliation = agents.get("reconciliation")
    if reconciliation:
        disputed = reconciliation.get("disputed_facts", [])
        warnings = reconciliation.get("integrity_warnings", [])
        downgrade = reconciliation.get("confidence_downgrade_reason")
        print(f"\ndisputed_facts: {len(disputed)} (top materiality first)")
        for i, f in enumerate(disputed[:3], 1):
            print(f"  {i}. [{f['materiality_score']}/10] {f['topic']}")
        if warnings:
            print(f"\nintegrity_warnings ({len(warnings)}):")
            for w in warnings:
                print(f"  ⚠ {w}")
        if downgrade:
            print(f"\nconfidence_downgrade_reason:\n  {downgrade}")

    out_path = ticker_dir / "reconciliation.json"
    print(f"\nwrote: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
