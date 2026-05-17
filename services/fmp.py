"""Financial Modeling Prep client — /stable/ endpoints, free-tier safe.

FMP migrated all endpoints from /api/v3/ to /stable/. New free-tier keys
return 403 on /api/v3/. Pull just enough to power Bull/Bear: profile
(price, market cap, sector), ratios + key metrics (TTM), and the three
core financial statements (last 4 periods).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from services.errors import FundamentalsUnavailable

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("FMP_API_KEY")
BASE = "https://financialmodelingprep.com/stable"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _get(endpoint: str, **params: Any) -> list | dict:
    if not API_KEY:
        raise FundamentalsUnavailable("FMP_API_KEY not set in .env")
    with httpx.Client(timeout=30) as http:
        r = http.get(f"{BASE}/{endpoint}", params={**params, "apikey": API_KEY})
        if r.status_code == 403:
            raise FundamentalsUnavailable(
                f"FMP {endpoint!r} returned 403 — endpoint is paid-tier or key inactive."
            )
        if r.status_code == 429:
            raise FundamentalsUnavailable(
                f"FMP {endpoint!r} rate-limited (429). Free tier = 250 calls/day."
            )
        # raise_for_status() puts the full request URL — including the
        # apikey query param — into the exception message, which would
        # leak the key into systemd journal via logger.exception. Catch
        # any other 4xx/5xx and re-raise with the URL stripped.
        if r.status_code >= 400:
            raise FundamentalsUnavailable(
                f"FMP {endpoint!r} HTTP {r.status_code}"
            )
        return r.json()


def fetch_fundamentals(ticker: str) -> dict:
    """Pull profile + ratios + statements. Per-endpoint 403s collected as warnings.

    Returns dict keyed by friendly name; missing pieces become None and an
    entry is appended to _warnings.

    Raises FundamentalsUnavailable if even profile is unavailable, which
    usually means the ticker isn't supported by FMP free tier at all.
    """
    out: dict[str, Any] = {"ticker": ticker.upper()}
    endpoints = {
        "profile": ("profile", {"symbol": ticker}),
        "ratios_ttm": ("ratios-ttm", {"symbol": ticker}),
        "key_metrics_ttm": ("key-metrics-ttm", {"symbol": ticker}),
        "income_statement": ("income-statement", {"symbol": ticker, "limit": 4}),
        "balance_sheet": ("balance-sheet-statement", {"symbol": ticker, "limit": 4}),
        "cash_flow_statement": ("cash-flow-statement", {"symbol": ticker, "limit": 4}),
    }
    for key, (ep, params) in endpoints.items():
        try:
            out[key] = _get(ep, **params)
        except FundamentalsUnavailable as e:
            out[key] = None
            out.setdefault("_warnings", []).append(f"{key}: {e}")

    if not out.get("profile"):
        raise FundamentalsUnavailable(
            f"FMP returned no profile for {ticker}. Either the ticker is "
            f"unsupported on FMP free tier or the key is inactive."
        )
    return out
