"""Probe — confirm Speechmatics batch API accepts our key.

Submits a tiny audio sample, polls until done, prints transcript +
diarization. Replace AUDIO_PATH with a 5-10 sec local clip for the probe.
"""

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("SPEECHMATICS_API_KEY")
BASE = "https://asr.api.speechmatics.com/v2"
AUDIO_PATH = ROOT / "data" / "probe_clip.mp3"


def main() -> None:
    if not API_KEY:
        print("ERROR: SPEECHMATICS_API_KEY not set in .env")
        sys.exit(1)
    if not AUDIO_PATH.exists():
        print(f"ERROR: place a short MP3/WAV at {AUDIO_PATH} for the probe")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {API_KEY}"}

    config = {
        "type": "transcription",
        "transcription_config": {
            "language": "en",
            "diarization": "speaker",
            "operating_point": "enhanced",
        },
    }

    with httpx.Client(timeout=60) as http:
        with AUDIO_PATH.open("rb") as f:
            r = http.post(
                f"{BASE}/jobs",
                headers=headers,
                files={
                    "data_file": (AUDIO_PATH.name, f, "audio/mpeg"),
                    "config": (None, _json(config), "application/json"),
                },
            )
        r.raise_for_status()
        job_id = r.json()["id"]
        print(f"Job submitted: {job_id}")

        while True:
            r = http.get(f"{BASE}/jobs/{job_id}", headers=headers)
            r.raise_for_status()
            status = r.json()["job"]["status"]
            print(f"  status: {status}")
            if status == "done":
                break
            if status == "rejected":
                print("ERROR: job rejected")
                sys.exit(1)
            time.sleep(3)

        r = http.get(f"{BASE}/jobs/{job_id}/transcript?format=json-v2", headers=headers)
        r.raise_for_status()
        transcript = r.json()
        results = transcript.get("results", [])
        text = " ".join(
            w["alternatives"][0]["content"]
            for w in results
            if w.get("alternatives")
        )
        speakers = {
            w["alternatives"][0].get("speaker", "UNK")
            for w in results
            if w.get("alternatives")
        }
        print()
        print("TRANSCRIPT:", text[:300])
        print("SPEAKERS  :", speakers)
        print()
        print("OK — Speechmatics auth + diarization verified.")


def _json(obj):
    import json
    return json.dumps(obj)


if __name__ == "__main__":
    main()
