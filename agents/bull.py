"""Bull Agent — build the strongest investment case from the same evidence
the Filing + Call analysts already extracted.

Runs on Featherless Qwen3-32B (OpenAI-compatible /v1/chat/completions).
Adversarial constraint: the model may cite ONLY claim IDs that exist in
the union of Filing + Call output. After parsing the response we audit
`cited_claim_ids` against the real set and refuse to save the result if
any pillar cites a non-existent ID — that would invalidate the entire
downstream reconciliation.

CLI:

    python -m agents.bull NVDA

Reads `data/{ticker}/analysis_filing.json` and `analysis_call.json` (the
upstream outputs from `agents.filing` and `agents.call`), writes the
validated `BullCase` to `data/{ticker}/analysis_bull.json`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents._qwen import (  # noqa: E402
    call_qwen,
    format_claim_catalogue,
    valid_claim_ids,
)
from agents.schemas import (  # noqa: E402
    BullCase,
    CallAnalysis,
    FilingAnalysis,
)


SYSTEM_PROMPT = """You are the Bull Agent on an institutional research desk.
Your job is to build the strongest reasoned LONG investment case for the
ticker, using ONLY the evidence the Filing Analyst and Call Analyst have
already extracted.

## Hard constraints

1. You may cite ONLY claim IDs from the catalogue in the user message.
   The IDs look like F-007 (filing) and C-014 (call). Inventing a new
   ID, or pulling a fact not present in the catalogue, INVALIDATES the
   pillar and gets the run thrown out by the auditor.
2. You may quote the underlying text of cited claims, paraphrase them,
   or combine multiple claim IDs in one pillar's reasoning.
3. You must NOT contradict the filings — if a claim says revenue fell,
   you cannot say revenue rose.
4. You must acknowledge bear-side concessions that the strongest bull
   case does NOT dispute. These go in `counter_arguments_acknowledged`.

## Output schema (strict JSON, no fences, no prose around it)

{
  "ticker": "<ticker>",
  "thesis": "<one-sentence top-line bull case>",
  "pillars": [
    {
      "headline": "<one-line thesis, <=120 chars>",
      "reasoning": "<2-4 sentences. Cite F-### / C-### inline. No invented facts.>",
      "cited_claim_ids": ["F-007", "C-014"]
    }
    // 2-5 pillars total
  ],
  "counter_arguments_acknowledged": [
    "<specific bear-side concession the bull case does not deny>"
    // 0+ entries
  ]
}

## Tone

Institutional-research neutral. No marketing language. No emoji. No
"AI summary"-style preamble. /no_think when the answer is obvious;
otherwise reason inside <think> tags before producing the JSON."""


async def build_bull_case(
    ticker: str,
    data_dir: Path = Path("data"),
    *,
    save: bool = True,
) -> BullCase:
    ticker_dir = data_dir / ticker
    filing = FilingAnalysis.model_validate_json(
        (ticker_dir / "analysis_filing.json").read_text()
    )
    call = CallAnalysis.model_validate_json(
        (ticker_dir / "analysis_call.json").read_text()
    )

    catalogue = format_claim_catalogue(filing.claims, call.claims)
    legal_ids = valid_claim_ids(filing.claims, call.claims)

    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"FILING SUMMARY:\n{filing.form_summary}\n\n"
        f"CALL SUMMARY:\n{call.call_summary}\n\n"
        f"CLAIM CATALOGUE (cite only these IDs):\n{catalogue}\n\n"
        "Build the strongest bull case. Return BullCase JSON only."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    t0 = time.monotonic()
    raw = await call_qwen(
        messages,
        max_tokens=4500,
        temperature=0.4,
        enable_thinking=True,
    )
    wall = time.monotonic() - t0

    # Force ticker before validation — model may echo it back wrong.
    if isinstance(raw, dict):
        raw["ticker"] = ticker

    result = BullCase.model_validate(raw)

    # Adversarial audit: every cited_claim_id must exist in the F+C union.
    cited = {cid for p in result.pillars for cid in p.cited_claim_ids}
    fabricated = cited - legal_ids
    if fabricated:
        raise RuntimeError(
            f"Bull agent cited non-existent claim IDs: {sorted(fabricated)}. "
            "Refusing to save. Re-run, or downstream Reconciler will flag the "
            "pillar as uncited_claims_flag=True."
        )

    if save:
        (ticker_dir / "analysis_bull.json").write_text(
            result.model_dump_json(indent=2)
        )

    print(
        f"[bull] {ticker} {wall:.1f}s "
        f"pillars={len(result.pillars)} "
        f"cited_unique={len(cited)} "
        f"concessions={len(result.counter_arguments_acknowledged)}"
    )
    return result


def _main() -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.bull")
    ap.add_argument("ticker")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    try:
        result = asyncio.run(
            build_bull_case(args.ticker, args.data_dir, save=not args.no_save)
        )
    except FileNotFoundError as exc:
        print(f"error: missing input file {exc.filename}")
        print(
            f"hint: run `python -m agents.filing {args.ticker}` and "
            f"`python -m agents.call {args.ticker}` first"
        )
        return 2

    print(f"\nthesis: {result.thesis}")
    print(f"\npillars ({len(result.pillars)}):")
    for i, p in enumerate(result.pillars, 1):
        print(f"  {i}. {p.headline}")
        print(f"     cites: {', '.join(p.cited_claim_ids)}")
    if result.counter_arguments_acknowledged:
        print(f"\nconcessions ({len(result.counter_arguments_acknowledged)}):")
        for c in result.counter_arguments_acknowledged[:3]:
            print(f"  · {c}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
