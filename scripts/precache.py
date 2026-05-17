"""Pre-cache curated tickers end-to-end with adversarial audit per stage.

Goal
====

Before the Day-3 demo, populate ``data/{TICKER}/`` for a handful of
big-cap tickers so the dashboard responds instantly when judges pick
from the curated chips. Every step writes a log entry to
``scripts/precache_audit.md`` so we can prove the pipeline ran cleanly.

Usage::

    python -m scripts.precache TSLA                # one ticker, with confirms
    python -m scripts.precache TSLA AAPL PLTR AMD  # several, sequential
    python -m scripts.precache TSLA --dry-run      # pre-flight only, no spend
    python -m scripts.precache TSLA --yes          # skip "are you sure" prompt

Adversarial checks per ticker (before any paid call):

  1. EDGAR resolves the symbol → CIK with a recent 10-K **and** 10-Q.
  2. yt-dlp probe returns a candidate ≥ 1200s with a plausible uploader
     (warns on AI-summary channels, fake reposts, off-topic clips).
  3. FMP ``/stable/profile`` returns 200 (free-tier daily quota check).

If any step fails, the ticker is skipped and the reason is logged.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Mute httpx INFO — leaks query-string FMP key on 4xx. SECURITY.md §4.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import audio, edgar, fmp  # noqa: E402

DATA = ROOT / "data"
AUDIT_PATH = ROOT / "scripts" / "precache_audit.md"

# Channels we expect to see for legit big-cap earnings calls. Anything
# else is allowed but flagged so a human can eyeball the result.
TRUSTED_UPLOADER_HINTS = (
    "investor",
    "earnings",
    "official",
    "corporation",
    "corp",
    "inc",
    "ir ",
    " ir",
    "yahoo finance",  # routine repost of full call
    "bloomberg",
    "cnbc",
)

log = logging.getLogger("precache")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _audit_append(line: str) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a") as f:
        f.write(line.rstrip() + "\n")


def _audit_header(ticker: str) -> None:
    _audit_append(f"\n## {ticker} — {_now()}\n")


def _audit_kv(key: str, value) -> None:
    _audit_append(f"- **{key}**: {value}")


def _looks_trusted(uploader: str | None, channel: str | None) -> bool:
    blob = " ".join(filter(None, [uploader, channel])).lower()
    return any(hint in blob for hint in TRUSTED_UPLOADER_HINTS)


def preflight(ticker: str) -> dict:
    """Run cheap, free checks. Return result dict (no paid API calls)."""
    result: dict = {"ticker": ticker, "ok": True, "skip_reason": None, "checks": {}}

    # ---- 1. EDGAR resolution + recent filings ----
    try:
        t, cik, name = edgar.resolve_ticker(ticker)
        filings = edgar.fetch_recent_filings(cik)
        # EDGAR's `recent` array is newest-first by filingDate. We want the
        # FIRST match per form (the newest), not the last. Plain dict
        # comprehension would clobber to the oldest — production ingest
        # avoids this by using ``candidates[0]`` instead.
        latest_by_form: dict[str, dict] = {}
        for f in filings:
            latest_by_form.setdefault(f["form"], f)
        has_10k = "10-K" in latest_by_form
        has_10q = "10-Q" in latest_by_form
        result["checks"]["edgar"] = {
            "ok": has_10k and has_10q,
            "ticker": t,
            "cik": cik,
            "name": name,
            "has_10k": has_10k,
            "has_10q": has_10q,
            "10k_filed": latest_by_form.get("10-K", {}).get("filed"),
            "10q_filed": latest_by_form.get("10-Q", {}).get("filed"),
        }
        if not (has_10k and has_10q):
            result["ok"] = False
            result["skip_reason"] = f"EDGAR missing 10-K ({has_10k}) or 10-Q ({has_10q})"
            return result
        # Sanity: skip anything older than 18 months — issuer is delisted or weird.
        from datetime import date
        k_date = latest_by_form["10-K"].get("filed")
        if k_date:
            y, m, d = (int(x) for x in k_date.split("-"))
            age_days = (date.today() - date(y, m, d)).days
            if age_days > 540:
                result["ok"] = False
                result["skip_reason"] = f"10-K is {age_days}d old — likely delisted"
                return result
    except Exception as e:
        result["ok"] = False
        result["skip_reason"] = f"EDGAR error: {e}"
        result["checks"]["edgar"] = {"ok": False, "error": str(e)}
        return result

    # ---- 2. YouTube probe (no download, no Speechmatics) ----
    yt = audio.probe_youtube_source(ticker)
    if yt is None:
        result["ok"] = False
        result["skip_reason"] = "yt-dlp: no candidate ≥1200s for this ticker"
        result["checks"]["youtube"] = {"ok": False}
        return result
    yt["trusted_uploader"] = _looks_trusted(yt.get("uploader"), yt.get("channel"))
    yt["ok"] = True
    result["checks"]["youtube"] = yt

    # ---- 3. FMP free-tier quota ping ----
    try:
        fund = fmp.fetch_fundamentals(ticker)
        result["checks"]["fmp"] = {
            "ok": True,
            "profile_companyName": (fund.get("profile") or {}).get("companyName"),
            "warnings": fund.get("_warnings", []),
        }
    except Exception as e:
        # Non-fatal — FMP is the only optional source, ingestion tolerates
        # it being absent. Still flag so we know what we got.
        result["checks"]["fmp"] = {"ok": False, "error": str(e)}

    return result


async def run_pipeline(ticker: str) -> dict:
    """Execute ingestion then agent graph for one ticker. Returns audit dict."""
    from services.ingest import ingest as run_ingest
    from agents.graph import run_for_ticker

    t0 = time.monotonic()
    manifest = run_ingest(ticker, force=False)
    t_ingest = time.monotonic() - t0

    t1 = time.monotonic()
    final_state = await run_for_ticker(ticker, DATA, reuse_cache=False)
    t_agents = time.monotonic() - t1

    rec = final_state.get("agents", {}).get("reconciliation", {})
    return {
        "manifest_warnings": manifest.get("warnings", []),
        "wall_ingest_s": round(t_ingest, 1),
        "wall_agents_s": round(t_agents, 1),
        "wall_total_s": round(t_ingest + t_agents, 1),
        "disputed_count": len(rec.get("disputed_facts", [])),
        "top_materiality": (
            rec["disputed_facts"][0]["materiality_score"]
            if rec.get("disputed_facts") else None
        ),
        "integrity_warnings": rec.get("integrity_warnings", []),
        "confidence_downgrade": rec.get("confidence_downgrade_reason"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.precache")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--dry-run", action="store_true",
                    help="Pre-flight only; do not call paid APIs or download anything.")
    ap.add_argument("--yes", action="store_true",
                    help="Skip the 'about to spend money' confirmation prompt.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not AUDIT_PATH.exists():
        AUDIT_PATH.write_text("# Precache audit log\n")

    results = []
    for raw in args.tickers:
        ticker = raw.strip().upper()
        log.info("=" * 60)
        log.info("Pre-flight: %s", ticker)
        _audit_header(ticker)

        pf = preflight(ticker)
        for k, v in pf["checks"].items():
            _audit_kv(f"preflight.{k}", json.dumps(v, default=str))
        if not pf["ok"]:
            log.error("SKIP %s — %s", ticker, pf["skip_reason"])
            _audit_kv("skipped", pf["skip_reason"])
            results.append({"ticker": ticker, "ok": False, "reason": pf["skip_reason"]})
            continue

        yt = pf["checks"]["youtube"]
        log.info("  yt-dlp candidate: %s | %s (%ss) — trusted=%s",
                 yt.get("title"), yt.get("uploader"),
                 yt.get("duration_seconds"), yt.get("trusted_uploader"))
        log.info("  EDGAR: %s (CIK %s) 10-K %s · 10-Q %s",
                 pf["checks"]["edgar"]["ticker"],
                 pf["checks"]["edgar"]["cik"],
                 pf["checks"]["edgar"]["10k_filed"],
                 pf["checks"]["edgar"]["10q_filed"])

        if args.dry_run:
            log.info("DRY-RUN — skipping ingest + agents.")
            _audit_kv("status", "dry-run, preflight only")
            results.append({"ticker": ticker, "ok": True, "dry_run": True})
            continue

        if not args.yes:
            answer = input(
                f"\nProceed with paid ingestion for {ticker}? "
                f"(~$0.51 Vertex + Speechmatics, ~5–8 min) [y/N] "
            ).strip().lower()
            if answer != "y":
                log.info("Aborted by user.")
                _audit_kv("status", "user aborted")
                results.append({"ticker": ticker, "ok": False, "reason": "user aborted"})
                continue

        try:
            stats = asyncio.run(run_pipeline(ticker))
        except Exception as e:
            log.exception("Pipeline crashed for %s", ticker)
            _audit_kv("status", f"CRASHED: {e}")
            results.append({"ticker": ticker, "ok": False, "reason": str(e)})
            continue

        for k, v in stats.items():
            _audit_kv(f"result.{k}", json.dumps(v, default=str))
        log.info(
            "DONE %s — %ss total, %d disputed, top=%s, integrity=%s",
            ticker, stats["wall_total_s"], stats["disputed_count"],
            stats["top_materiality"], len(stats["integrity_warnings"]),
        )
        results.append({"ticker": ticker, "ok": True, "stats": stats})

    print("\n" + "=" * 60)
    print("Precache summary:")
    for r in results:
        if r["ok"] and not r.get("dry_run"):
            s = r["stats"]
            print(f"  ✓ {r['ticker']:6} {s['wall_total_s']:>5}s  "
                  f"{s['disputed_count']} disputed  top={s['top_materiality']}")
        elif r["ok"] and r.get("dry_run"):
            print(f"  · {r['ticker']:6} dry-run pre-flight OK")
        else:
            print(f"  ✗ {r['ticker']:6} {r.get('reason')}")
    print(f"\nFull audit log: {AUDIT_PATH}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
