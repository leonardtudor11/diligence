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
            # Avoid logging raw response body — Speechmatics may echo request metadata.
            raise TranscriptionFailed(
                f"Speechmatics submission HTTP {r.status_code} (reason: {r.reason_phrase!r})"
            )
        try:
            return r.json()["id"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise TranscriptionFailed(
                f"Speechmatics returned malformed submission response: {type(e).__name__}"
            ) from e


def _wait_for_done(job_id: str) -> None:
    deadline = time.time() + MAX_WAIT_SECONDS
    last_status = ""
    with httpx.Client(timeout=30) as http:
        while time.time() < deadline:
            r = http.get(f"{BASE}/jobs/{job_id}", headers=_headers())
            r.raise_for_status()
            try:
                status = r.json()["job"]["status"]
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                raise TranscriptionFailed(
                    f"Speechmatics returned malformed status payload for job {job_id} "
                    f"({type(e).__name__})"
                ) from e
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


# Diarization quality thresholds. Below HARD, the transcript is unusable
# for the call analyst (silent failure mode flagged in the Day-4
# adversarial review). Below SOFT, the pipeline still runs but ingest.py
# surfaces a manifest warning so the dashboard can show a confidence band.
DIARIZATION_HARD_COVERAGE = 0.20
DIARIZATION_SOFT_COVERAGE = 0.80


def audit_speaker_coverage(transcript: dict) -> dict:
    """Inspect json-v2 ``results`` for diarization quality.

    Returns an audit dict with ``coverage`` (0..1), ``distinct_speakers``,
    and a ``warnings`` list. Raises ``TranscriptionFailed`` if the
    transcript is unusable (no word results, no speakers, or coverage
    below ``DIARIZATION_HARD_COVERAGE``) — the call analyst depends on
    speaker attribution and silent degradation would poison the agent
    layer.
    """
    results = transcript.get("results") or []
    word_results = [r for r in results if r.get("type") == "word"]
    total = len(word_results)
    if total == 0:
        raise TranscriptionFailed("Speechmatics transcript has 0 word results")

    speakers: set[str] = set()
    with_speaker = 0
    for r in word_results:
        alt = (r.get("alternatives") or [{}])[0]
        sp = alt.get("speaker")
        if sp:
            with_speaker += 1
            speakers.add(sp)
    coverage = with_speaker / total

    if not speakers or coverage < DIARIZATION_HARD_COVERAGE:
        raise TranscriptionFailed(
            f"Diarization unusable: {with_speaker}/{total} words labeled "
            f"({coverage:.1%}), distinct_speakers={sorted(speakers)}. Call "
            f"Analyst requires speaker attribution."
        )

    warnings: list[str] = []
    if coverage < DIARIZATION_SOFT_COVERAGE:
        warnings.append(
            f"low speaker coverage: {coverage:.1%} "
            f"(<{DIARIZATION_SOFT_COVERAGE:.0%} threshold)"
        )
    if len(speakers) < 2:
        warnings.append(
            f"single-speaker transcript ({sorted(speakers)}) — diarization "
            f"likely degraded"
        )
    return {
        "word_count": total,
        "speaker_word_count": with_speaker,
        "coverage": round(coverage, 4),
        "distinct_speakers": sorted(speakers),
        "warnings": warnings,
    }


def transcribe(audio_path: Path, language: str = "en") -> dict:
    """Submit `audio_path`, poll until done, return the json-v2 transcript.

    Adds a ``_diarization_audit`` key to the returned dict; raises
    ``TranscriptionFailed`` if diarization is pathologically bad. See
    ``audit_speaker_coverage`` for thresholds.
    """
    if not audio_path.exists():
        raise TranscriptionFailed(f"Audio file not found: {audio_path}")
    job_id = _submit(audio_path, language=language)
    log.info("Speechmatics job submitted: %s", job_id)
    _wait_for_done(job_id)
    transcript = _fetch_transcript(job_id)
    audit = audit_speaker_coverage(transcript)
    log.info(
        "Speechmatics diarization: %.1f%% coverage, %d distinct speakers %s",
        audit["coverage"] * 100,
        len(audit["distinct_speakers"]),
        audit["distinct_speakers"],
    )
    for w in audit["warnings"]:
        log.warning("Speechmatics: %s", w)
    transcript["_diarization_audit"] = audit
    return transcript
