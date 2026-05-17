"""Audio acquisition via yt-dlp — autonomous tiered selection from
multiple YouTube candidates, with transparent score breakdown.

YouTube isn't the official IR source, but many financial channels mirror
earnings calls within hours of broadcast. Rather than trust the top
``ytsearch1`` hit blindly, we pull N candidates across two query forms
(ticker-based + issuer-name-based), score each on five orthogonal
dimensions, and pick the highest-scoring candidate above a minimum
threshold. If no candidate clears the threshold the pipeline records why
in ``manifest.warnings`` and skips Speechmatics — the agent graph still
runs on EDGAR + FMP evidence, just with a confidence downgrade.

Scoring rubric (rough weights — see ``score_audio_candidate``):

    duration in earnings-call typical band  +30
    duration in acceptable band             +10
    title positive keyword(s)               +10..+30
    title negative keyword(s)               -30 each
    uploader matches issuer (T1)            +50
    uploader is trusted aggregator (T2)     +25
    uploader is editorial aggregator (T3)   +10
    upload date within 90d of target        +25
    upload date within 1y of target         +10
    upload date >2y from target             -20

A candidate must clear ``MIN_CANDIDATE_SCORE`` to be picked. Below that,
the selector returns ``selected=None`` and the pipeline skips audio.

Provenance: ``find_best_audio_candidate`` returns the winner *and* every
loser with their score breakdown so the dashboard can show "why this
video over these 7 others". See HANDOFF.md confidence-downgrade band.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from services.errors import AudioNotAvailable

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MIN_AUDIO_BYTES = 1_000_000  # 1 MB floor — anything smaller is a failed fetch
MIN_CANDIDATE_SCORE = 50
DEFAULT_CANDIDATES_PER_QUERY = 8
# Wall-clock cap on any single yt-dlp invocation. Without this, a hung
# YouTube response would pin one thread-pool worker forever and
# eventually exhaust uvicorn's `asyncio.to_thread` pool.
YT_DLP_PROBE_TIMEOUT_S = 120
YT_DLP_DOWNLOAD_TIMEOUT_S = 600
# Only download from these hosts. Defence-in-depth against a poisoned
# yt-dlp result or future caller error: if `webpage_url` resolves to
# anything else, refuse rather than handing yt-dlp an arbitrary URL.
ALLOWED_AUDIO_HOSTS = frozenset({
    "www.youtube.com", "youtube.com", "youtu.be", "m.youtube.com",
})


# ---------------------------------------------------------------------------
# Issuer-name normalisation + uploader tier rubric
# ---------------------------------------------------------------------------

# Strip trailing legal-entity tokens so EDGAR's "TESLA, INC." matches
# uploader "Tesla". Keeps the brand portion; loses the suffix only.
LEGAL_SUFFIX_RE = re.compile(
    r"[,\s]*(?:Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|Limited|LLC|"
    r"Holdings|Co\.?|Company|Group|plc|N\.V\.|S\.A\.|AG|SE)\s*$",
    re.IGNORECASE,
)

# Trusted aggregator allowlist — audit-class publishers. Lowercase
# substring match against uploader+channel. Tier 2.
TRUSTED_AGGREGATORS: tuple[str, ...] = (
    "bloomberg", "reuters", "wall street journal", "wsj",
    "morningstar", "s&p global", "s&p capital iq",
)

# Editorial aggregators — typically host accurate audio but may edit
# segments or overlay commentary. Tier 3 (medium trust).
EDITORIAL_AGGREGATORS: tuple[str, ...] = (
    "yahoo finance", "cnbc", "benzinga", "seeking alpha", "marketwatch",
    "the motley fool",
)

# Title tokens that suggest a full earnings-call recording.
POSITIVE_TITLE_TOKENS: tuple[str, ...] = (
    "earnings call", "conference call", "webcast", "q&a",
    "earnings results", "financial results", "earnings webcast",
    "investor conference",
)

# Title tokens that suggest a derivative product (summary, reaction,
# AI-generated, etc.) rather than the actual call.
NEGATIVE_TITLE_TOKENS: tuple[str, ...] = (
    "summary", "highlights", "reaction", "review", "explained",
    "ai generated", "ai-generated", "ai-narrated", "breakdown",
    "recap", "key takeaways", "in 5 minutes", "in 3 minutes",
    "preview", "what to expect", "predictions",
)


def _normalize_issuer(name: str | None) -> str:
    if not name:
        return ""
    cleaned = LEGAL_SUFFIX_RE.sub("", name).strip().strip(",.")
    return cleaned


# Generic legal/structural tokens — drop these from issuer-name tokenisation
# so issuer-vs-uploader matching only fires on salient brand tokens.
_GENERIC_ISSUER_TOKENS = frozenset({
    "the", "and", "corp", "inc", "ltd", "group", "holdings", "company",
    "limited", "incorporated", "corporation", "plc", "trust", "fund",
})


def _issuer_token_match(
    issuer_norm: str,
    ticker: str,
    uploader_blob: str,
) -> tuple[bool, str | None]:
    """Word-boundary match between issuer name tokens (or the ticker itself)
    and uploader/channel tokens.

    Asymmetric substring matching was brittle: "Palantir Technologies"
    (normalised issuer) was NOT a substring of "palantir palantir"
    (uploader+channel of the real Palantir IR channel), so the official
    earnings webcast was mis-classified as T4. Tokenising both sides and
    intersecting on word boundary fixes that *and* handles the inverse
    problem (uploader "AMD" with issuer "ADVANCED MICRO DEVICES" via the
    ticker fallback).

    Returns (matched, matched_token_or_None).
    """
    if not uploader_blob:
        return False, None
    candidate_tokens: set[str] = set()
    if ticker:
        candidate_tokens.add(ticker.lower())
    if issuer_norm:
        for tok in issuer_norm.lower().split():
            tok = tok.strip(",.&|@#$")
            if len(tok) >= 4 and tok not in _GENERIC_ISSUER_TOKENS:
                candidate_tokens.add(tok)
    if not candidate_tokens:
        return False, None
    blob_tokens = {
        tok.strip(",.&|@#$()[]")
        for tok in re.split(r"[\s/\-_]+", uploader_blob.lower())
    }
    common = candidate_tokens & blob_tokens
    if common:
        return True, sorted(common)[0]
    return False, None


def _need(binary: str) -> None:
    if not shutil.which(binary):
        raise AudioNotAvailable(
            f"`{binary}` is not on PATH. Install it: brew install {binary}"
        )


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------


def score_audio_candidate(
    candidate: dict,
    issuer_name: str | None,
    target_date_iso: str | None,
    *,
    ticker: str | None = None,
) -> dict:
    """Return a scored dict for one yt-dlp candidate.

    Output keys:
      total          int   — aggregate score (can be negative)
      tier           str   — T1_verified_primary | T2_trusted_aggregator |
                             T3_editorial_aggregator | T4_unverified
      breakdown      list  — [(label, delta), ...] explaining the score
      candidate      dict  — the original probe row
    """
    breakdown: list[tuple[str, int]] = []
    total = 0
    title = (candidate.get("title") or "").lower()
    uploader_blob = " ".join(
        filter(None, [candidate.get("uploader"), candidate.get("channel")])
    ).lower()
    duration = candidate.get("duration_seconds") or 0
    upload_date = candidate.get("upload_date") or ""  # YYYYMMDD

    # 1. Duration band — typical earnings call is 40-90 min.
    if 2400 <= duration <= 5400:
        total += 30
        breakdown.append(("duration_typical_40-90min", 30))
    elif 1200 <= duration <= 7200:
        total += 10
        breakdown.append(("duration_acceptable_20-120min", 10))
    else:
        breakdown.append(("duration_out_of_range", 0))

    # 2. Title positives (cap at +30 so one keyword-heavy title can't
    # paper over a bad uploader).
    pos_hits = [k for k in POSITIVE_TITLE_TOKENS if k in title]
    if pos_hits:
        bonus = min(30, 10 * len(pos_hits))
        total += bonus
        breakdown.append((f"title_positive:{'+'.join(pos_hits)}", bonus))

    # 3. Title negatives — derivative content.
    neg_hits = [k for k in NEGATIVE_TITLE_TOKENS if k in title]
    if neg_hits:
        penalty = 30 * len(neg_hits)
        total -= penalty
        breakdown.append((f"title_negative:{'+'.join(neg_hits)}", -penalty))

    # 4. Uploader tier — T1 issuer-match dominates; aggregator
    # allowlists are mutually exclusive; everything else is T4.
    issuer_norm = _normalize_issuer(issuer_name)
    matched, hit_token = _issuer_token_match(
        issuer_norm, ticker or "", uploader_blob,
    )
    tier = "T4_unverified"
    if matched:
        total += 50
        tier = "T1_verified_primary"
        breakdown.append((f"uploader_matches_issuer:{hit_token!r}", 50))
    elif any(t in uploader_blob for t in TRUSTED_AGGREGATORS):
        matched = next(t for t in TRUSTED_AGGREGATORS if t in uploader_blob)
        total += 25
        tier = "T2_trusted_aggregator"
        breakdown.append((f"uploader_trusted_aggregator:{matched}", 25))
    elif any(t in uploader_blob for t in EDITORIAL_AGGREGATORS):
        matched = next(t for t in EDITORIAL_AGGREGATORS if t in uploader_blob)
        total += 10
        tier = "T3_editorial_aggregator"
        breakdown.append((f"uploader_editorial_aggregator:{matched}", 10))
    else:
        breakdown.append(("uploader_unverified", 0))

    # 5. Recency — distance from target_date (latest 10-Q/10-K filed).
    # Earnings call diligence is quarter-specific. A correctly-attributed
    # but stale call (e.g., issuer's first earnings call from 5 years ago)
    # is functionally useless — fundamentals have rotated, claims about
    # forward guidance refer to a long-ago window. Penalise hard so a
    # tier-1 stale candidate cannot beat the threshold on its own.
    if target_date_iso and len(upload_date) == 8:
        try:
            ty, tm, td = (int(x) for x in target_date_iso.split("-"))
            uy, um, ud = (
                int(upload_date[:4]),
                int(upload_date[4:6]),
                int(upload_date[6:8]),
            )
            delta_days = abs((date(ty, tm, td) - date(uy, um, ud)).days)
            if delta_days <= 90:
                total += 25
                breakdown.append((f"recent_within_90d({delta_days}d)", 25))
            elif delta_days <= 180:
                total += 10
                breakdown.append((f"recent_within_180d({delta_days}d)", 10))
            elif delta_days <= 365:
                breakdown.append((f"recency_neutral({delta_days}d)", 0))
            elif delta_days <= 730:
                total -= 30
                breakdown.append((f"stale_1-2y({delta_days}d)", -30))
            else:
                total -= 60
                breakdown.append((f"stale_>2y({delta_days}d)", -60))
        except (ValueError, TypeError):
            breakdown.append(("date_parse_failed", 0))

    return {
        "total": total,
        "tier": tier,
        "breakdown": breakdown,
        "candidate": candidate,
    }


# ---------------------------------------------------------------------------
# yt-dlp probe + download primitives
# ---------------------------------------------------------------------------


def _yt_dlp_probe(
    query: str,
    n: int,
    *,
    min_duration_seconds: int = 1200,
) -> list[dict]:
    """Return up to n yt-dlp candidate dicts for one query. Empty on failure.

    Uses ``--dump-json`` (one JSON object per line) instead of a custom
    ``--print`` template. The previous template used ``%(uploader)j``
    which is yt-dlp's *shell*-escape format, not JSON-escape — uploaders
    or titles with apostrophes or quotes silently failed json.loads and
    the candidate was dropped. --dump-json emits proper JSON.

    Bounded by YT_DLP_PROBE_TIMEOUT_S so a hung YouTube response cannot
    pin a thread-pool worker. ``--ignore-config`` prevents per-user
    yt-dlp configs from injecting proxies / plugins / extra args.
    """
    _need("yt-dlp")
    cmd = [
        "yt-dlp",
        "--ignore-config",
        "--simulate",
        "--no-playlist",
        "--no-cache-dir",
        "--match-filter", f"duration > {min_duration_seconds}",
        "--dump-json",
        f"ytsearch{n}:{query}",
    ]
    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True,
            timeout=YT_DLP_PROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return []
    if result.returncode != 0:
        return []
    out: list[dict] = []
    for line in result.stdout.strip().splitlines():
        try:
            full = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append({
            "url": full.get("webpage_url"),
            "uploader": full.get("uploader"),
            "channel": full.get("channel"),
            "title": full.get("title"),
            "duration_seconds": full.get("duration"),
            "upload_date": full.get("upload_date"),
        })
    return out


def find_best_audio_candidate(
    ticker: str,
    issuer_name: str | None,
    target_date_iso: str | None,
    *,
    quarter: str | None = None,
    year: str | None = None,
    n_per_query: int = DEFAULT_CANDIDATES_PER_QUERY,
    min_score: int = MIN_CANDIDATE_SCORE,
) -> dict:
    """Search YouTube across multiple queries, score every candidate, pick the
    best. Returns a decision dict regardless of outcome.

    Output keys:
      selected               dict or None — winner candidate (url, uploader, …)
      selected_score         int          — winner total
      selected_tier          str          — winner tier label
      selected_breakdown     list         — winner score reasons
      candidates_considered  list         — every unique probe row, scored,
                                            sorted desc by total
      queries                list[str]    — queries actually run
      reason                 str          — human-readable explanation
    """
    queries: list[str] = [f"{ticker} earnings call"]
    issuer_norm = _normalize_issuer(issuer_name)
    if issuer_norm and issuer_norm.upper() != ticker.upper():
        queries.append(f"{issuer_norm} earnings call")
    if quarter and year:
        queries.append(f"{ticker} {quarter} FY{year} earnings call")

    raw: list[dict] = []
    seen_urls: set[str] = set()
    for q in queries:
        for c in _yt_dlp_probe(q, n_per_query):
            url = c.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            raw.append(c)

    if not raw:
        return {
            "selected": None,
            "selected_score": 0,
            "selected_tier": None,
            "selected_breakdown": [],
            "candidates_considered": [],
            "queries": queries,
            "reason": (
                f"yt-dlp returned 0 candidates across {len(queries)} queries "
                f"({queries}) — no YouTube earnings-call audio is discoverable "
                f"for {ticker}."
            ),
        }

    scored = [
        score_audio_candidate(c, issuer_name, target_date_iso, ticker=ticker)
        for c in raw
    ]
    scored.sort(key=lambda s: s["total"], reverse=True)
    top = scored[0]
    top_candidate = top["candidate"]

    if top["total"] < min_score:
        return {
            "selected": None,
            "selected_score": top["total"],
            "selected_tier": top["tier"],
            "selected_breakdown": top["breakdown"],
            "candidates_considered": scored,
            "queries": queries,
            "reason": (
                f"No YouTube candidate cleared min_score={min_score}. Top "
                f"candidate was {top_candidate.get('title')!r} by "
                f"{top_candidate.get('uploader')!r} (score={top['total']}, "
                f"tier={top['tier']}). Skipping audio for {ticker}."
            ),
        }

    return {
        "selected": top_candidate,
        "selected_score": top["total"],
        "selected_tier": top["tier"],
        "selected_breakdown": top["breakdown"],
        "candidates_considered": scored,
        "queries": queries,
        "reason": (
            f"Picked {top_candidate.get('title')!r} by "
            f"{top_candidate.get('uploader')!r} "
            f"(tier={top['tier']}, score={top['total']}; "
            f"{len(scored)-1} other candidate(s) considered)."
        ),
    }


def download_audio_by_url(url: str, out_path: Path) -> Path:
    """Download a specific YouTube URL to ``out_path`` as MP3. Idempotent.

    Enforces ``ALLOWED_AUDIO_HOSTS`` — refuses to download from anything
    that isn't a known YouTube hostname. Defence-in-depth against a
    poisoned candidate URL (or a future caller passing user input):
    without this, yt-dlp would happily fetch from the cloud-metadata
    service or any internal HTTP endpoint via its generic extractor.

    Wall-clock cap via YT_DLP_DOWNLOAD_TIMEOUT_S.
    """
    from urllib.parse import urlparse
    _need("yt-dlp")
    _need("ffmpeg")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise AudioNotAvailable(
            f"refusing non-https audio URL (scheme={parsed.scheme!r})"
        )
    if parsed.hostname not in ALLOWED_AUDIO_HOSTS:
        raise AudioNotAvailable(
            f"refusing audio host {parsed.hostname!r} (allowed: "
            f"{sorted(ALLOWED_AUDIO_HOSTS)})"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > MIN_AUDIO_BYTES:
        return out_path
    cmd = [
        "yt-dlp",
        "--ignore-config",
        "--no-cache-dir",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", str(out_path.with_suffix(".%(ext)s")),
        url,
    ]
    try:
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True,
            timeout=YT_DLP_DOWNLOAD_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise AudioNotAvailable(
            f"yt-dlp download exceeded {YT_DLP_DOWNLOAD_TIMEOUT_S}s wall clock"
        )
    if result.returncode != 0:
        stderr_last = (result.stderr or "").strip().splitlines()
        hint = stderr_last[-1] if stderr_last else "(no stderr)"
        raise AudioNotAvailable(
            f"yt-dlp exited {result.returncode} downloading {url!r}. {hint}"
        )
    if not out_path.exists() or out_path.stat().st_size < MIN_AUDIO_BYTES:
        raise AudioNotAvailable(
            f"Download produced no usable file at {out_path}"
        )
    return out_path


# ---------------------------------------------------------------------------
# Back-compat shim — kept for any caller still using the old single-shot API.
# New code should use ``find_best_audio_candidate`` + ``download_audio_by_url``.
# ---------------------------------------------------------------------------


def probe_youtube_source(
    ticker: str,
    quarter: str | None = None,
    year: str | None = None,
    *,
    min_duration_seconds: int = 1200,
) -> dict | None:
    """Legacy single-candidate probe (kept for pre-flight back-compat).

    Returns the top yt-dlp hit's metadata dict or None. Does NOT score or
    filter for uploader trust — callers must do their own validation.
    """
    query = _build_search_query(ticker, quarter, year)
    cands = _yt_dlp_probe(
        query, n=1, min_duration_seconds=min_duration_seconds
    )
    return cands[0] if cands else None


def _build_search_query(ticker: str, quarter: str | None, year: str | None) -> str:
    if quarter and year:
        return f"{ticker} {quarter} FY{year} earnings call"
    if quarter:
        return f"{ticker} {quarter} earnings call"
    return f"{ticker} latest earnings call full audio"


def fetch_earnings_audio(
    ticker: str,
    quarter: str | None = None,
    year: str | None = None,
    *,
    min_duration_seconds: int = 1200,
) -> Path:
    """Legacy single-shot download (top yt-dlp hit). Prefer the
    candidate-aware pipeline via ``find_best_audio_candidate`` +
    ``download_audio_by_url``. Kept for callers that haven't been migrated.
    """
    _need("yt-dlp")
    _need("ffmpeg")
    out_dir = DATA / ticker.upper()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "earnings_call.mp3"
    if out_file.exists() and out_file.stat().st_size > MIN_AUDIO_BYTES:
        return out_file
    query = _build_search_query(ticker, quarter, year)
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "--match-filter", f"duration > {min_duration_seconds}",
        "-o", str(out_file.with_suffix(".%(ext)s")),
        f"ytsearch1:{query}",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr_last = (result.stderr or "").strip().splitlines()
        hint = stderr_last[-1] if stderr_last else "(no stderr)"
        raise AudioNotAvailable(
            f"yt-dlp exited {result.returncode} searching for {query!r}. {hint}"
        )
    if not out_file.exists() or out_file.stat().st_size < MIN_AUDIO_BYTES:
        raise AudioNotAvailable(
            f"No suitable YouTube result for {query!r} "
            f"(need duration > {min_duration_seconds}s)."
        )
    return out_file


def slice_clip(
    source: Path,
    dest: Path,
    start: str = "00:05:00",
    duration: str = "10",
) -> Path:
    """Encode a short slice of `source` to `dest` for quick probe/testing."""
    _need("ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(source),
            "-ss", start, "-t", duration,
            "-acodec", "libmp3lame", "-b:a", "128k",
            str(dest),
        ],
        check=True,
    )
    return dest
