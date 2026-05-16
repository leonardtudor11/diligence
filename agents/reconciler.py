"""Reconciler Agent — adjudicate Bull vs Bear into a ranked DisputedFacts list.

Reads four upstream JSON artefacts cached on disk:

    data/{ticker}/analysis_filing.json   (FilingAnalysis)
    data/{ticker}/analysis_call.json     (CallAnalysis)
    data/{ticker}/analysis_bull.json     (BullCase)
    data/{ticker}/analysis_bear.json     (BearCase)

Produces:

    data/{ticker}/reconciliation.json    (Reconciliation)

Behaviour (HANDOFF.md "Next session = reconciler + graph + runner"):

* Gemini 2.5 Pro, `response_schema=Reconciliation` (RQ2 PASS).
* `uncited_claims_flag` on each DisputedFact is set deterministically here
  *after* the model returns — we trust the catalogue, not the model's
  self-report. Bull/Bear already audited their own pillars, so this is
  belt-and-suspenders for the rare case the upstream audit was disabled.
* `confidence_downgrade_reason` populated if ANY upstream output set
  `injection_detected=true` OR any Call claim's confidence is
  `"unverified_audio"` (which today is every Call claim — see
  docs/AUDIT.md open design question).

CLI:

    python -m agents.reconciler NVDA
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import List

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.genai import types  # noqa: E402

from agents.schemas import (  # noqa: E402
    BearCase,
    BullCase,
    CallAnalysis,
    FilingAnalysis,
    Reconciliation,
)
from vertex_client import get_client  # noqa: E402


MODEL = "gemini-2.5-pro"

SYSTEM_PROMPT = """You are the Reconciler on an institutional research desk.
You receive the Bull and Bear cases for a ticker, plus the underlying
Filing and Call claim catalogues they were built from. Your job is to
identify the points where Bull and Bear materially disagree and rank
them by how much each disagreement would change a fundamental investor's
decision.

## Hard constraints

1. Every position you write MUST reference one or more claim_ids that
   appear in the catalogue (`F-###` from the filings or `C-###` from the
   call). If a side argued without citing, surface that in
   `integrity_warnings`, do not invent supporting claims.
2. Treat claim_ids as atomic — do not invent new IDs. If the Bull case
   cited `F-099` and that ID does not appear in the catalogue, list a
   string like "Bull pillar 2 cites non-existent F-099" in
   `integrity_warnings`.
3. Materiality is on a 1–10 scale:
   * 10 = changes whether a fundamental long/short investor takes the
     position at all
   * 7–9 = changes sizing or time horizon
   * 4–6 = changes confidence interval on the thesis
   * 1–3 = stylistic / framing / non-material
   List `disputed_facts` sorted DESCENDING by `materiality_score`.
4. `shared_ground` captures claims both sides explicitly conceded (the
   bull's `counter_arguments_acknowledged` AND any bear claim the bull
   did not contest in their pillars). Bullet-point sentences, not full
   paragraphs.
5. `integrity_warnings` is for citation hygiene only — non-existent
   claim_ids, pillars with empty `cited_claim_ids`, fundamental
   contradictions where one side asserted a fact the other side's
   claim catalogue *directly disproves*. Empty list if all clean.
6. Do NOT set `confidence_downgrade_reason` — the orchestrator sets
   this deterministically based on upstream `injection_detected` flags
   and the unverified_audio confidence band on Call claims.

## Output

Strict JSON conforming to the Reconciliation schema. No markdown fences.
No prose around the JSON. Sort `disputed_facts` descending by
`materiality_score`.
"""


def _format_claim_catalogue(filing: FilingAnalysis, call: CallAnalysis) -> str:
    """One line per claim — same format Bull/Bear saw (see agents/_qwen.py)."""
    lines: List[str] = []
    for c in filing.claims:
        section = c.source.section or "unknown"
        flag = " [ACCT]" if c.accounting_flag else ""
        lines.append(f"{c.claim_id} [{c.category}] ({section}){flag} {c.text}")
    for c in call.claims:
        spk = c.source.speaker or "?"
        ts = c.source.start_time or 0.0
        flag = " [ACCT]" if c.accounting_flag else ""
        lines.append(f"{c.claim_id} [{c.category}] ({spk} t={ts:.0f}s){flag} {c.text}")
    return "\n".join(lines)


def _format_case(label: str, case) -> str:
    """Render a Bull/Bear case as a compact prompt block."""
    out = [f"## {label} thesis", case.thesis, ""]
    out.append(f"## {label} pillars")
    for i, p in enumerate(case.pillars, 1):
        cited = ", ".join(p.cited_claim_ids)
        out.append(f"{i}. {p.headline}")
        out.append(f"   cites: {cited}")
        out.append(f"   reasoning: {p.reasoning}")
    if case.counter_arguments_acknowledged:
        out.append(f"\n## {label} concessions")
        for c in case.counter_arguments_acknowledged:
            out.append(f"- {c}")
    return "\n".join(out)


def _build_user_message(
    ticker: str,
    filing: FilingAnalysis,
    call: CallAnalysis,
    bull: BullCase,
    bear: BearCase,
) -> str:
    catalogue = _format_claim_catalogue(filing, call)
    return (
        f"Ticker: {ticker}\n\n"
        f"## Claim catalogue (cite by ID only — these are the legal references)\n"
        f"{catalogue}\n\n"
        f"{_format_case('Bull', bull)}\n\n"
        f"{_format_case('Bear', bear)}\n\n"
        "Produce the Reconciliation JSON. Sort disputed_facts descending by "
        "materiality_score."
    )


def _audit_uncited(
    df_bull_ids: List[str],
    df_bear_ids: List[str],
    legal_ids: set,
) -> bool:
    """Return True if either side cited a non-existent claim_id in this fact."""
    return bool(
        (set(df_bull_ids) - legal_ids) or (set(df_bear_ids) - legal_ids)
    )


def _compute_downgrade_reason(
    filing: FilingAnalysis,
    call: CallAnalysis,
) -> str | None:
    """Deterministic confidence downgrade — orchestrator-side, not model-side.

    See docs/AUDIT.md open design question on unverified_audio.
    """
    reasons: List[str] = []
    if filing.injection_detected:
        reasons.append("Filing analyst flagged prompt-injection attempt in filings")
    if call.injection_detected:
        reasons.append("Call analyst flagged prompt-injection attempt in transcript")
    unverified = [c for c in call.claims if c.confidence == "unverified_audio"]
    if unverified:
        reasons.append(
            f"{len(unverified)} call claim(s) sourced from unverified_audio "
            "(yt-dlp). Treat call-only positions with caution."
        )
    return "; ".join(reasons) if reasons else None


async def reconcile(
    ticker: str,
    data_dir: Path = Path("data"),
    *,
    save: bool = True,
) -> Reconciliation:
    ticker_dir = data_dir / ticker
    filing = FilingAnalysis.model_validate_json(
        (ticker_dir / "analysis_filing.json").read_text()
    )
    call = CallAnalysis.model_validate_json(
        (ticker_dir / "analysis_call.json").read_text()
    )
    bull = BullCase.model_validate_json(
        (ticker_dir / "analysis_bull.json").read_text()
    )
    bear = BearCase.model_validate_json(
        (ticker_dir / "analysis_bear.json").read_text()
    )

    legal_ids = {c.claim_id for c in filing.claims} | {c.claim_id for c in call.claims}

    user_msg = _build_user_message(ticker, filing, call, bull, bear)

    client = get_client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=Reconciliation,
        temperature=0.2,
        max_output_tokens=8000,
    )

    t0 = time.monotonic()
    resp = await client.aio.models.generate_content(
        model=MODEL,
        contents=user_msg,
        config=config,
    )
    wall = time.monotonic() - t0

    raw = resp.text or ""
    if not raw.strip():
        raise RuntimeError(
            f"Empty response from {MODEL}. finish_reason="
            f"{getattr(resp, 'candidates', [{}])[0].get('finish_reason')}"
        )
    result = Reconciliation.model_validate_json(raw)

    if result.ticker != ticker:
        result = result.model_copy(update={"ticker": ticker})

    # Re-sort defensively — the model usually sorts, but enforce it.
    sorted_facts = sorted(
        result.disputed_facts, key=lambda f: f.materiality_score, reverse=True
    )

    # Deterministic uncited-claim audit (overrides model self-report).
    integrity_extra: List[str] = []
    for f in sorted_facts:
        had_uncited = _audit_uncited(f.bull_claim_ids, f.bear_claim_ids, legal_ids)
        f.uncited_claims_flag = had_uncited
        if had_uncited:
            bad_bull = sorted(set(f.bull_claim_ids) - legal_ids)
            bad_bear = sorted(set(f.bear_claim_ids) - legal_ids)
            if bad_bull:
                integrity_extra.append(
                    f"DisputedFact '{f.topic}': bull cites non-existent {bad_bull}"
                )
            if bad_bear:
                integrity_extra.append(
                    f"DisputedFact '{f.topic}': bear cites non-existent {bad_bear}"
                )

    # Confidence downgrade is purely orchestrator-driven (the prompt forbids
    # the model from setting this).
    downgrade = _compute_downgrade_reason(filing, call)

    result = result.model_copy(
        update={
            "disputed_facts": sorted_facts,
            "integrity_warnings": list(result.integrity_warnings) + integrity_extra,
            "confidence_downgrade_reason": downgrade,
        }
    )

    if save:
        (ticker_dir / "reconciliation.json").write_text(
            result.model_dump_json(indent=2)
        )

    usage = getattr(resp, "usage_metadata", None)
    if usage:
        print(
            f"[reconciler] {ticker} {wall:.1f}s "
            f"disputed={len(result.disputed_facts)} "
            f"shared={len(result.shared_ground)} "
            f"warnings={len(result.integrity_warnings)} "
            f"prompt={usage.prompt_token_count} "
            f"output={usage.candidates_token_count}"
        )

    return result


def _main() -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.reconciler")
    ap.add_argument("ticker")
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    try:
        result = asyncio.run(
            reconcile(args.ticker, args.data_dir, save=not args.no_save)
        )
    except FileNotFoundError as exc:
        print(f"error: missing input file {exc.filename}")
        print(
            f"hint: run filing → call → bull → bear for {args.ticker} first"
        )
        return 2

    print(f"\ndisputed_facts ({len(result.disputed_facts)}, sorted by materiality):")
    for i, f in enumerate(result.disputed_facts, 1):
        flag = " [⚠ uncited]" if f.uncited_claims_flag else ""
        print(f"  {i}. [{f.materiality_score}/10]{flag} {f.topic}")
        print(f"     bull: {f.bull_position[:120]}")
        print(f"     bear: {f.bear_position[:120]}")
    if result.shared_ground:
        print(f"\nshared_ground ({len(result.shared_ground)}):")
        for s in result.shared_ground[:3]:
            print(f"  · {s}")
    if result.integrity_warnings:
        print(f"\nintegrity_warnings ({len(result.integrity_warnings)}):")
        for w in result.integrity_warnings:
            print(f"  ⚠ {w}")
    if result.confidence_downgrade_reason:
        print(f"\nconfidence_downgrade_reason:\n  {result.confidence_downgrade_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
