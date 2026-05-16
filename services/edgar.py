"""SEC EDGAR client — ticker resolution + recent 10-K / 10-Q text retrieval.

EDGAR has no API key. SEC ToS requires an identifying User-Agent header
with a real contact email; that lives in SEC_USER_AGENT in .env. Rate
limit is ~10 req/sec; we stay well under that.

Public surface:
    resolve_ticker(query)              -> (ticker, cik_10, name)
    fetch_recent_filings(cik_10)       -> list[dict]
    fetch_filing_text(...)             -> str
    fetch_latest_filings(query)        -> {ticker, cik, name, "10-K": {...}, "10-Q": {...}}
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from services.errors import DiligenceError, NoRecentFiling, TickerNotFound

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

USER_AGENT = os.getenv("SEC_USER_AGENT", "Diligence Hackathon contact@example.com")
SEC_BASE = "https://www.sec.gov"
EDGAR_DATA = "https://data.sec.gov"
_HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _client() -> httpx.Client:
    return httpx.Client(headers=_HEADERS, timeout=30, follow_redirects=True)


class _EdgarRateLimited(DiligenceError):
    """EDGAR returned 429 — we are hitting the 10 req/sec ceiling."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def _get_json(url: str) -> dict:
    with _client() as http:
        r = http.get(url)
        if r.status_code == 429:
            raise _EdgarRateLimited(f"EDGAR rate-limited on {url}")
        r.raise_for_status()
        return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def _get_text(url: str) -> str:
    with _client() as http:
        r = http.get(url)
        if r.status_code == 429:
            raise _EdgarRateLimited(f"EDGAR rate-limited on {url}")
        r.raise_for_status()
        return r.text


def resolve_ticker(query: str) -> tuple[str, str, str]:
    """Resolve a ticker symbol OR company name to (ticker, cik_10, title).

    Match priority: exact-ticker > exact-name > name-substring.
    Raises TickerNotFound if nothing in EDGAR's master list matches.
    """
    q = query.strip().upper()
    tickers = _get_json(f"{SEC_BASE}/files/company_tickers.json")
    rows = list(tickers.values())

    for row in rows:
        if row["ticker"].upper() == q:
            return row["ticker"], str(row["cik_str"]).zfill(10), row["title"]
    for row in rows:
        if row["title"].upper() == q:
            return row["ticker"], str(row["cik_str"]).zfill(10), row["title"]
    for row in rows:
        if q in row["title"].upper():
            return row["ticker"], str(row["cik_str"]).zfill(10), row["title"]

    raise TickerNotFound(
        f"No SEC EDGAR company matches '{query}'. Try the ticker symbol "
        f"(e.g. NVDA) or the full company name as listed on EDGAR "
        f"(e.g. 'NVIDIA CORP')."
    )


def fetch_recent_filings(
    cik_10: str, forms: tuple[str, ...] = ("10-K", "10-Q")
) -> list[dict]:
    """Return recent filings of the requested form types, newest first."""
    sub = _get_json(f"{EDGAR_DATA}/submissions/CIK{cik_10}.json")
    recent = sub["filings"]["recent"]
    report_dates = recent.get("reportDate", [])
    return [
        {
            "form": recent["form"][i],
            "accession": recent["accessionNumber"][i],
            "filed": recent["filingDate"][i],
            "primary_doc": recent["primaryDocument"][i],
            "report_date": report_dates[i] if i < len(report_dates) else None,
        }
        for i, form in enumerate(recent["form"])
        if form in forms
    ]


def fetch_filing_text(cik_10: str, accession: str, primary_doc: str) -> str:
    """Download a filing's primary document and return plain text."""
    accn_nodash = accession.replace("-", "")
    cik_int = int(cik_10)
    url = f"{SEC_BASE}/Archives/edgar/data/{cik_int}/{accn_nodash}/{primary_doc}"
    html = _get_text(url)
    return _strip_html(html)


def _strip_html(html: str) -> str:
    import warnings as _warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    # SEC filings are inline XBRL (XML with HTML elements) — silence the
    # informational warning; "lxml" still extracts text correctly.
    _warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_latest_filings(query: str) -> dict:
    """High-level: resolve ticker, download newest 10-K and 10-Q, return text+meta.

    Raises TickerNotFound if `query` cannot be resolved.
    Raises NoRecentFiling if EDGAR has no 10-K or 10-Q for this issuer.
    """
    ticker, cik_10, name = resolve_ticker(query)
    filings = fetch_recent_filings(cik_10)
    if not filings:
        raise NoRecentFiling(
            f"EDGAR has no recent 10-K or 10-Q for {ticker} (CIK {cik_10})."
        )

    result: dict = {"ticker": ticker, "cik": cik_10, "name": name}
    for form in ("10-K", "10-Q"):
        candidates = [f for f in filings if f["form"] == form]
        if not candidates:
            continue
        latest = candidates[0]
        text = fetch_filing_text(cik_10, latest["accession"], latest["primary_doc"])
        result[form] = {**latest, "text_chars": len(text), "text": text}
    return result
