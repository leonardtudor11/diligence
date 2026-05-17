"""End-to-end ticker ingestion: EDGAR + FMP + audio + transcript → data/{ticker}/.

Usage:
    python -m services.ingest NVDA
    python -m services.ingest "NVIDIA CORP" --quarter Q4 --year 2026
    python -m services.ingest NVDA --skip-audio        # skip YouTube + Speechmatics
    python -m services.ingest NVDA --force             # ignore cached outputs

Output layout (per ticker):
    data/{TICKER}/
        manifest.json         status of each stage + paths
        10k.json              {form, accession, filed, text, ...}
        10q.json              same for the most recent 10-Q
        fundamentals.json     FMP profile + ratios + statements
        earnings_call.mp3     YouTube-sourced full call audio
        transcript.json       Speechmatics json-v2 (word-level + speakers)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services import audio, edgar, fmp, speech
from services.errors import (
    AudioNotAvailable,
    DiligenceError,
    FundamentalsUnavailable,
    NoRecentFiling,
    TickerNotFound,
    TranscriptionFailed,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
# httpx INFO logs the full URL including query-string secrets (FMP key).
# Suppress per SECURITY.md.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

log = logging.getLogger("ingest")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ingest(
    query: str,
    *,
    quarter: str | None = None,
    year: str | None = None,
    skip_audio: bool = False,
    force: bool = False,
) -> dict:
    """Run the full ingestion pipeline. Returns the manifest dict written to disk."""
    warnings: list[str] = []

    # ---- 1. EDGAR — resolve ticker + fetch 10-K / 10-Q ----
    log.info("EDGAR: resolving %r", query)
    filings = edgar.fetch_latest_filings(query)
    ticker = filings["ticker"]
    out_dir = DATA / ticker
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("EDGAR: %s (CIK %s) — %s", ticker, filings["cik"], filings["name"])
    for form in ("10-K", "10-Q"):
        if form in filings:
            f = filings[form]
            stem = form.lower().replace("-", "")
            _write_json(out_dir / f"{stem}.json", f)
            log.info("  %s filed %s — %d chars cached", form, f["filed"], f["text_chars"])
        else:
            warnings.append(f"EDGAR: no {form} found for {ticker}")

    # ---- 2. FMP fundamentals ----
    fund_path = out_dir / "fundamentals.json"
    fund: dict | None = None
    if fund_path.exists() and not force:
        log.info("FMP: cached at %s (use --force to refresh)", fund_path.name)
        fund = json.loads(fund_path.read_text())
    else:
        log.info("FMP: fetching fundamentals for %s", ticker)
        try:
            fund = fmp.fetch_fundamentals(ticker)
            _write_json(fund_path, fund)
            for w in fund.get("_warnings", []):
                log.warning("FMP: %s", w)
                warnings.append(f"FMP: {w}")
        except FundamentalsUnavailable as e:
            log.error("FMP: %s", e)
            warnings.append(f"FMP: {e}")

    # ---- 3. Audio acquisition ----
    audio_path: Path | None = None
    audio_provenance: dict | None = None
    if skip_audio:
        log.info("Audio: skipped (--skip-audio)")
    else:
        try:
            log.info("Audio: probing YouTube for %s", ticker)
            audio_provenance = audio.probe_youtube_source(
                ticker, quarter=quarter, year=year
            )
            if audio_provenance:
                log.info(
                    "Audio: candidate '%s' by %s (%ds) — %s",
                    audio_provenance.get("title"),
                    audio_provenance.get("uploader"),
                    audio_provenance.get("duration_seconds") or 0,
                    audio_provenance.get("url"),
                )

            log.info("Audio: downloading MP3")
            audio_path = audio.fetch_earnings_audio(
                ticker, quarter=quarter, year=year
            )
            size_mb = audio_path.stat().st_size / 1_048_576
            log.info("Audio: %s (%.1f MB)", audio_path.name, size_mb)
        except AudioNotAvailable as e:
            log.error("Audio: %s", e)
            warnings.append(f"Audio: {e}")
            # Clear the probe metadata too — the candidate URL/uploader
            # describe a video we ultimately failed to fetch, and writing
            # it into manifest.sources.audio would mislead the dashboard.
            audio_provenance = None

    # ---- 4. Speechmatics transcription ----
    transcript_path = out_dir / "transcript.json"
    if audio_path and (force or not transcript_path.exists()):
        log.info("Speechmatics: submitting (5-10 min for ~60-min audio)")
        try:
            tx = speech.transcribe(audio_path)
            _write_json(transcript_path, tx)
            results = tx.get("results", [])
            speakers = {
                w["alternatives"][0].get("speaker", "UNK")
                for w in results
                if w.get("alternatives")
            }
            log.info(
                "Speechmatics: %d tokens, %d speaker(s): %s",
                len(results), len(speakers), sorted(speakers),
            )
        except TranscriptionFailed as e:
            log.error("Speechmatics: %s", e)
            warnings.append(f"Speechmatics: {e}")
    elif transcript_path.exists():
        log.info("Speechmatics: cached at %s (use --force to re-transcribe)", transcript_path.name)
    elif not audio_path and not skip_audio:
        log.info("Speechmatics: skipped (no audio available)")

    # ---- 5. manifest ----
    sources: dict[str, dict | None] = {"10k": None, "10q": None, "audio": None}
    cik_int = int(filings["cik"])
    for form in ("10-K", "10-Q"):
        if form in filings:
            f = filings[form]
            accn_nodash = f["accession"].replace("-", "")
            sources_key = "10k" if form == "10-K" else "10q"
            sources[sources_key] = {
                "url": f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_int}/{accn_nodash}/{f['primary_doc']}",
                "accession": f["accession"],
                "filed": f["filed"],
                "report_date": f.get("report_date"),
            }
    if audio_provenance:
        sources["audio"] = audio_provenance

    manifest = {
        "ticker": ticker,
        "cik": filings["cik"],
        "company": filings["name"],
        "generated_at": _now_iso(),
        "query": query,
        "files": {
            "10k": "10k.json" if (out_dir / "10k.json").exists() else None,
            "10q": "10q.json" if (out_dir / "10q.json").exists() else None,
            "fundamentals": "fundamentals.json" if fund_path.exists() else None,
            "earnings_call_mp3": "earnings_call.mp3" if (out_dir / "earnings_call.mp3").exists() else None,
            "transcript": "transcript.json" if transcript_path.exists() else None,
        },
        "sources": sources,
        "warnings": warnings,
    }
    _write_json(out_dir / "manifest.json", manifest)
    log.info("Manifest written: data/%s/manifest.json", ticker)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(prog="ingest", description="Diligence ingestion pipeline")
    ap.add_argument("ticker_or_name",
                    help="Ticker (e.g. NVDA) or company name (e.g. 'NVIDIA CORP')")
    ap.add_argument("--quarter", help="e.g. Q4 — used in YouTube search query")
    ap.add_argument("--year", help="e.g. 2026 — used in YouTube search query")
    ap.add_argument("--skip-audio", action="store_true",
                    help="Skip YouTube fetch + Speechmatics (text-only ingestion)")
    ap.add_argument("--force", action="store_true",
                    help="Ignore cached outputs and re-run every stage")
    args = ap.parse_args()

    try:
        ingest(
            args.ticker_or_name,
            quarter=args.quarter,
            year=args.year,
            skip_audio=args.skip_audio,
            force=args.force,
        )
        return 0
    except TickerNotFound as e:
        log.error("Could not resolve ticker/name: %s", e)
        return 2
    except NoRecentFiling as e:
        log.error("EDGAR has no recent filings: %s", e)
        return 3
    except DiligenceError as e:
        log.error("Ingestion aborted: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
