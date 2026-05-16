"""Custom exception hierarchy for the Diligence ingestion pipeline.

Each exception type maps to a single failure mode so callers (CLI, FastAPI
backend) can render specific user-facing remediation hints.
"""

from __future__ import annotations


class DiligenceError(Exception):
    """Base class for all Diligence pipeline failures."""


class TickerNotFound(DiligenceError):
    """The supplied ticker or company name does not resolve on SEC EDGAR."""


class NoRecentFiling(DiligenceError):
    """EDGAR returned no recent 10-K or 10-Q for this issuer."""


class FundamentalsUnavailable(DiligenceError):
    """FMP returned no usable fundamentals (403, empty payload, rate limit)."""


class AudioNotAvailable(DiligenceError):
    """No earnings-call audio could be retrieved for this ticker/quarter."""


class TranscriptionFailed(DiligenceError):
    """Speechmatics rejected the job or returned an unusable transcript."""
