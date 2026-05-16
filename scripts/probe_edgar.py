"""Probe — confirm SEC EDGAR returns the most recent 10-K / 10-Q.

EDGAR has no API key — only a User-Agent requirement. Submissions endpoint
takes the 10-digit CIK (zero-padded).
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

USER_AGENT = os.getenv("SEC_USER_AGENT", "Diligence Hackathon contact@example.com")
TICKER = os.getenv("PROBE_TICKER", "NVDA")


def main() -> None:
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(headers=headers, timeout=30) as http:
        r = http.get("https://www.sec.gov/files/company_tickers.json")
        r.raise_for_status()
        tickers = r.json()
        match = next(
            (row for row in tickers.values() if row["ticker"] == TICKER.upper()),
            None,
        )
        if not match:
            print(f"ERROR: ticker {TICKER} not found in EDGAR")
            sys.exit(1)
        cik = str(match["cik_str"]).zfill(10)
        print(f"TICKER : {TICKER}")
        print(f"CIK    : {cik}")
        print(f"NAME   : {match['title']}")

        r = http.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
        r.raise_for_status()
        sub = r.json()
        recent = sub["filings"]["recent"]
        forms = recent["form"]
        latest = next(
            (i for i, f in enumerate(forms) if f in ("10-K", "10-Q")),
            None,
        )
        if latest is None:
            print("ERROR: no recent 10-K or 10-Q")
            sys.exit(1)
        print(f"LATEST : {forms[latest]} filed {recent['filingDate'][latest]}")
        print(f"ACCN   : {recent['accessionNumber'][latest]}")

    print()
    print("OK — EDGAR access verified.")


if __name__ == "__main__":
    main()
