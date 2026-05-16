"""Audio acquisition via yt-dlp — best-effort earnings call MP3.

YouTube isn't the official IR source, but many financial channels mirror
earnings calls within hours of broadcast. Good enough for hackathon
demos and POCs; swap to Quartr or an IR-page scraper for production.

The function is idempotent: if a sized MP3 already exists at the target
path, it's returned without re-fetching.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from services.errors import AudioNotAvailable

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MIN_AUDIO_BYTES = 1_000_000  # 1 MB floor — anything smaller is a failed fetch


def _need(binary: str) -> None:
    if not shutil.which(binary):
        raise AudioNotAvailable(
            f"`{binary}` is not on PATH. Install it: brew install {binary}"
        )


def fetch_earnings_audio(
    ticker: str,
    quarter: str | None = None,
    year: str | None = None,
    *,
    min_duration_seconds: int = 1200,
) -> Path:
    """Ensure data/{ticker}/earnings_call.mp3 exists, downloading if needed.

    Raises AudioNotAvailable if no YouTube result above min_duration_seconds
    matches the search. Search query is constructed from quarter/year if
    provided, otherwise falls back to "latest earnings call full audio".

    SECURITY/CORRECTNESS CAVEAT: ytsearch1 returns the top YouTube hit. Any
    uploader can publish a fake or AI-generated earnings-call clip. The
    duration > 1200s filter blocks summaries and clips but does not
    authenticate the speaker or content. Day-2 agents should surface the
    source URL + uploader in the UI and tag claims sourced from this audio
    as `confidence=unverified` until manually approved. See HANDOFF.md.
    """
    _need("yt-dlp")
    _need("ffmpeg")

    out_dir = DATA / ticker.upper()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "earnings_call.mp3"
    if out_file.exists() and out_file.stat().st_size > MIN_AUDIO_BYTES:
        return out_file

    if quarter and year:
        query = f"{ticker} {quarter} FY{year} earnings call"
    elif quarter:
        query = f"{ticker} {quarter} earnings call"
    else:
        query = f"{ticker} latest earnings call full audio"

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
        # yt-dlp stderr can include absolute local paths; surface only the last line.
        stderr_last = (result.stderr or "").strip().splitlines()
        hint = stderr_last[-1] if stderr_last else "(no stderr)"
        raise AudioNotAvailable(
            f"yt-dlp exited {result.returncode} searching for {query!r}. {hint}"
        )
    if not out_file.exists() or out_file.stat().st_size < MIN_AUDIO_BYTES:
        raise AudioNotAvailable(
            f"No suitable YouTube result for {query!r} (need duration > "
            f"{min_duration_seconds}s). Drop the MP3 manually at {out_file} "
            f"and re-run."
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
