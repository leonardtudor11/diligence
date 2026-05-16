"""Bear Agent — build the strongest reasoned SHORT case from the same
evidence the Filing + Call analysts already extracted.

Mirror of `agents.bull`: same Featherless Qwen3-32B client, same claim-
catalogue prompt format, same adversarial audit that every cited ID
must exist in the F + C union. Only the system prompt is inverted —
swing the model toward strongest bear, not strongest bull.

CLI:

    python -m agents.bear NVDA

Reads `analysis_filing.json` + `analysis_call.json`, writes the
validated `BearCase` to `data/{ticker}/analysis_bear.json`.
"""

from __future__ import annotations

import argparse
import asyncio
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
    BearCase,
    CallAnalysis,
    FilingAnalysis,
)


SYSTEM_PROMPT = """You are the Bear Agent on an institutional research desk.
Your job is to build the strongest reasoned SHORT investment case for the
ticker, using ONLY the evidence the Filing Analyst and Call Analyst have
already extracted.

## Hard constraints

1. You may cite ONLY claim IDs from the catalogue in the user message.
   Inventing a new ID, or pulling a fact not present in the catalogue,
   INVALIDATES the pillar and gets the run thrown out by the auditor.
2. You may quote the underlying text of cited claims, paraphrase them,
   or combine multiple claim IDs in one pillar's reasoning.
3. Bear-case reasoning is allowed (and expected) to draw out hedging
   language, accounting flags, concentration risks, regulatory risks,
   forward-guidance softness, and Q&A deflection. Lean on claims where
   `accounting_flag` was set by the upstream analyst, or where hedging
   examples / contradictions were noted in the call analysis.
4. You must NOT contradict the filings. If a claim says revenue rose
   65%, you cannot say revenue fell. The bear case is built on what
   the filings DO say plus what management did NOT say.
5. You must acknowledge bull-side concessions that the strongest bear
   case does NOT dispute. These go in `counter_arguments_acknowledged`.

## Output schema (strict JSON, no fences, no prose around it)

{
  "ticker": "<ticker>",
  "thesis": "<one-sentence top-line bear case>",
  "pillars": [
    {
      "headline": "<one-line risk, <=120 chars>",
      "reasoning": "<2-4 sentences. Cite F-### / C-### inline. No invented facts.>",
      "cited_claim_ids": ["F-007", "C-014"]
    }
    // 2-5 pillars total
  ],
  "counter_arguments_acknowledged": [
    "<specific bull-side strength the bear case does not deny>"
    // 0+ entries
  ]
}

## Tone

Institutional-research neutral. No marketing language. No alarmism.
Concrete risks tied to specific claim IDs. No emoji. No "AI summary"-
style preamble. /no_think when the answer is obvious; otherwise reason
inside <think> tags before producing the JSON."""


async def build_bear_case(
    ticker: str,
    data_dir: Path = Path("data"),
    *,
    save: bool = True,
) -> BearCase:
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
        "Build the strongest bear case. Return BearCase JSON only."
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

    if isinstance(raw, dict):
        raw["ticker"] = ticker

    result = BearCase.model_validate(raw)

    cited = {cid for p in result.pillars for cid in p.cited_claim_ids}
    fabricated = cited - legal_ids
    if fabricated:
        raise RuntimeError(
            f"Bear agent cited non-existent claim IDs: {sorted(fabricated)}. "
            "Refusing to save. Re-run, or downstream Reconciler will flag the "
            "pillar as uncited_claims_flag=True."
        )

    if save:
        (ticker_dir / "analysis_bear.json").write_text(
            result.model_dump_json(indent=2)
        )

    print(
        f"[bear] {ticker} {wall:.1f}s "
        f"pillars={len(result.pillars)} "
        f"cited_unique={len(cited)} "
        f"concessions={len(result.counter_arguments_acknowledged)}"
    )
    return result


def _main() -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.bear")
    ap.add_argument("ticker")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    try:
        result = asyncio.run(
            build_bear_case(args.ticker, args.data_dir, save=not args.no_save)
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
