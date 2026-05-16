"""Probe — confirm Financial Modeling Prep free-tier returns fundamentals."""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("FMP_API_KEY")
BASE = "https://financialmodelingprep.com/stable"
TICKER = os.getenv("PROBE_TICKER", "NVDA")


def main() -> None:
    if not API_KEY:
        print("ERROR: FMP_API_KEY not set in .env")
        sys.exit(1)

    with httpx.Client(timeout=30) as http:
        try:
            r = http.get(
                f"{BASE}/profile",
                params={"symbol": TICKER, "apikey": API_KEY},
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f"ERROR: FMP returned HTTP {e.response.status_code} on /stable/profile")
            print("Hint: free-tier keys may need email-verification + 5-10 min activation.")
            sys.exit(1)
        rows = r.json()

    if not rows:
        print(f"ERROR: empty response for ticker {TICKER}")
        sys.exit(1)

    p = rows[0]
    print(f"TICKER  : {TICKER}")
    print(f"NAME    : {p.get('companyName')}")
    print(f"SECTOR  : {p.get('sector')}")
    print(f"MARKETCAP: {p.get('mktCap')}")
    print(f"PRICE   : {p.get('price')}")
    print()
    print("OK — FMP free tier verified.")


if __name__ == "__main__":
    main()
