"""Fetch earnings-call audio for a ticker from YouTube via yt-dlp.

Usage:
    python scripts/fetch_audio.py NVDA            # latest call
    python scripts/fetch_audio.py NVDA Q4 2026    # specific quarter
    python scripts/fetch_audio.py NVDA --slice    # also create data/probe_clip.mp3

Strategy:
    yt-dlp YouTube search for "{ticker} Q{q} FY{y} earnings call"
    Downloads top result as MP3 to data/{ticker}/earnings_call.mp3
    Optional 10s slice for Speechmatics probe.

Requires: yt-dlp + ffmpeg (brew install yt-dlp ffmpeg).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _need(binary: str) -> None:
    if not shutil.which(binary):
        sys.exit(f"ERROR: `{binary}` not on PATH. brew install {binary}")


def fetch(ticker: str, quarter: str | None, year: str | None) -> Path:
    _need("yt-dlp")
    _need("ffmpeg")

    out_dir = DATA / ticker.upper()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "earnings_call.mp3"

    if quarter and year:
        query = f"{ticker} {quarter} FY{year} earnings call"
    elif quarter:
        query = f"{ticker} {quarter} earnings call latest"
    else:
        query = f"{ticker} latest earnings call full audio"

    print(f"Searching YouTube: {query!r}")

    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "--match-filter", "duration > 1200",  # >20 min — filters out clips
        "-o", str(out_file.with_suffix(".%(ext)s")),
        f"ytsearch1:{query}",
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(f"ERROR: yt-dlp failed (exit {result.returncode})")
    if not out_file.exists():
        sys.exit(f"ERROR: expected output at {out_file} not found")

    size_mb = out_file.stat().st_size / 1_048_576
    print(f"\nDownloaded: {out_file}  ({size_mb:.1f} MB)")
    return out_file


def slice_probe(full: Path, start: str = "00:05:00", duration: str = "10") -> Path:
    """Create data/probe_clip.mp3 (10 sec slice) for Speechmatics probe."""
    _need("ffmpeg")
    probe = DATA / "probe_clip.mp3"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(full),
        "-ss", start, "-t", duration,
        "-acodec", "libmp3lame", "-b:a", "128k",
        str(probe),
    ]
    subprocess.run(cmd, check=True)
    print(f"Sliced: {probe} ({start} + {duration}s)")
    return probe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker", help="e.g. NVDA")
    ap.add_argument("quarter", nargs="?", help="e.g. Q4")
    ap.add_argument("year", nargs="?", help="e.g. 2026")
    ap.add_argument("--slice", action="store_true",
                    help="also produce data/probe_clip.mp3")
    args = ap.parse_args()

    full = fetch(args.ticker, args.quarter, args.year)
    if args.slice:
        slice_probe(full)


if __name__ == "__main__":
    main()
