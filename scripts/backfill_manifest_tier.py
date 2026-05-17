"""Backfill `sources.audio.{tier, score, candidates_considered, queries}`
into manifests written before the autonomous tiered selector landed.

Pre-Day-4 manifests recorded only `{url, uploader, channel, title,
duration_seconds, upload_date}` for `sources.audio`. The Day-4 dashboard
expects the tier/score fields and the candidates_considered list to
power the Audit tab + transcript header. Re-ingesting would re-spend
Speechmatics + Gemini credits unnecessarily; this script just scores
the existing winner against the current rubric and writes the
breakdown back.

Usage:
    python -m scripts.backfill_manifest_tier NVDA TSLA
    python -m scripts.backfill_manifest_tier --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.audio import score_audio_candidate  # noqa: E402

DATA = ROOT / "data"


def backfill(ticker: str) -> str:
    t = ticker.upper()
    manifest_path = DATA / t / "manifest.json"
    if not manifest_path.exists():
        return f"{t}: SKIP — no manifest at {manifest_path}"
    manifest = json.loads(manifest_path.read_text())
    sources = manifest.setdefault("sources", {})
    audio = sources.get("audio")
    if audio is None:
        return f"{t}: SKIP — sources.audio is null (filing-only ingest)"
    if audio.get("tier"):
        return f"{t}: SKIP — already has tier={audio['tier']}"

    issuer = manifest.get("company") or t
    target_date = (
        (sources.get("10q") or {}).get("filed")
        or (sources.get("10k") or {}).get("filed")
    )
    scored = score_audio_candidate(
        audio, issuer_name=issuer, target_date_iso=target_date, ticker=t,
    )
    audio["tier"] = scored["tier"]
    audio["score"] = scored["total"]
    audio["score_breakdown"] = [
        {"factor": label, "delta": delta}
        for label, delta in scored["breakdown"]
    ]
    # No other candidates were scored at original ingest time; record the
    # winner as the only entry so the Audit tab table renders something
    # rather than a blank panel.
    audio["candidates_considered"] = [
        {
            "url": audio.get("url"),
            "uploader": audio.get("uploader"),
            "title": audio.get("title"),
            "duration_seconds": audio.get("duration_seconds"),
            "upload_date": audio.get("upload_date"),
            "score": scored["total"],
            "tier": scored["tier"],
        }
    ]
    audio["queries"] = audio.get("queries") or [
        f"(backfilled — original ingest did not record query)"
    ]
    sources["audio"] = audio

    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, default=str))
    tmp.replace(manifest_path)
    return f"{t}: OK — tier={scored['tier']} score={scored['total']}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.backfill_manifest_tier")
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--all", action="store_true",
                    help="Backfill every ticker dir under data/")
    args = ap.parse_args()

    if args.all:
        tickers = sorted(
            d.name for d in DATA.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        )
    else:
        tickers = [t.upper() for t in args.tickers]
    if not tickers:
        print("nothing to do (no tickers given, --all not set)")
        return 0
    for t in tickers:
        print(backfill(t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
