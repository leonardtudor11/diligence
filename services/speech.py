"""Speechmatics batch transcription with speaker diarization.

Submits an audio file to the batch endpoint, polls until done, and
returns the json-v2 transcript (word-level start/end + per-word speaker
labels). One ~60 min call typically resolves in 4-10 min wall time.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from services.errors import TranscriptionFailed

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("SPEECHMATICS_API_KEY")
BASE = "https://asr.api.speechmatics.com/v2"
POLL_INTERVAL_SECONDS = 5
MAX_WAIT_SECONDS = 1800

log = logging.getLogger("speech")


def _headers() -> dict[str, str]:
    if not API_KEY:
        raise TranscriptionFailed("SPEECHMATICS_API_KEY not set in .env")
    return {"Authorization": f"Bearer {API_KEY}"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def _submit(audio_path: Path, language: str) -> str:
    config = {
        "type": "transcription",
        "transcription_config": {
            "language": language,
            "diarization": "speaker",
            "operating_point": "enhanced",
        },
    }
    with httpx.Client(timeout=120) as http, audio_path.open("rb") as f:
        r = http.post(
            f"{BASE}/jobs",
            headers=_headers(),
            files={
                "data_file": (audio_path.name, f, "audio/mpeg"),
                "config": (None, json.dumps(config), "application/json"),
            },
        )
        if r.status_code >= 400:
            raise TranscriptionFailed(
                f"Speechmatics submission HTTP {r.status_code}: {r.text[:300]}"
            )
        return r.json()["id"]


def _wait_for_done(job_id: str) -> None:
    deadline = time.time() + MAX_WAIT_SECONDS
    last_status = ""
    with httpx.Client(timeout=30) as http:
        while time.time() < deadline:
            r = http.get(f"{BASE}/jobs/{job_id}", headers=_headers())
            r.raise_for_status()
            status = r.json()["job"]["status"]
            if status != last_status:
                log.info("Speechmatics job %s: %s", job_id, status)
                last_status = status
            if status == "done":
                return
            if status == "rejected":
                raise TranscriptionFailed(f"Speechmatics rejected job {job_id}")
            time.sleep(POLL_INTERVAL_SECONDS)
    raise TranscriptionFailed(
        f"Speechmatics job {job_id} timed out after {MAX_WAIT_SECONDS}s"
    )


def _fetch_transcript(job_id: str) -> dict:
    with httpx.Client(timeout=60) as http:
        r = http.get(
            f"{BASE}/jobs/{job_id}/transcript?format=json-v2",
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


def transcribe(audio_path: Path, language: str = "en") -> dict:
    """Submit `audio_path`, poll until done, return the json-v2 transcript."""
    if not audio_path.exists():
        raise TranscriptionFailed(f"Audio file not found: {audio_path}")
    job_id = _submit(audio_path, language=language)
    log.info("Speechmatics job submitted: %s", job_id)
    _wait_for_done(job_id)
    return _fetch_transcript(job_id)
