"""Vertex AI client factory for the Diligence project.

Org policy `constraints/iam.disableServiceAccountKeyCreation` is enforced on
mirel-leonard-org, so SA JSON keys cannot be created. Application Default
Credentials (ADC) cannot be used either because the laptop's well-known ADC
file is owned by the RobotBoy production project — overwriting it would
re-route RobotBoy billing.

Solution: mint a short-lived OAuth access token by shelling out to
`gcloud auth print-access-token` against the active gcloud configuration
(set to `hackathon` for this work). The token never touches disk, the ADC
well-known file is never read or modified, and RobotBoy continues to work.

Tokens expire after ~1 hour. `get_client()` caches the token in-process and
re-fetches when it is within REFRESH_SKEW_SECONDS of expiry.

Active gcloud configuration must point at the hackathon account/project:

    gcloud config configurations activate hackathon

before any Python entrypoint imports this module.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

from google.oauth2.credentials import Credentials
from google import genai

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "project-2be42b84-14e0-421a-b3a")
LOCATION = os.getenv("GCP_LOCATION", "global")
ACCESS_TOKEN_TTL_SECONDS = 3500
REFRESH_SKEW_SECONDS = 120


@dataclass
class _TokenCache:
    token: str
    expires_at: float


_cache: Optional[_TokenCache] = None
_lock = threading.Lock()


def _fetch_access_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _get_token() -> str:
    global _cache
    with _lock:
        now = time.time()
        if _cache and (_cache.expires_at - REFRESH_SKEW_SECONDS) > now:
            return _cache.token
        token = _fetch_access_token()
        _cache = _TokenCache(token=token, expires_at=now + ACCESS_TOKEN_TTL_SECONDS)
        return token


def get_credentials() -> Credentials:
    """Build google.oauth2 Credentials backed by the gcloud access token."""
    return Credentials(token=_get_token(), quota_project_id=PROJECT_ID)


def get_client(location: Optional[str] = None) -> genai.Client:
    """Return a configured genai.Client bound to the hackathon project.

    Gemini text and image both work at location='global'. Veo video would
    need location='us-central1' (not used in this project's scope).
    """
    return genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=location or LOCATION,
        credentials=get_credentials(),
    )


if __name__ == "__main__":
    client = get_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Say 'vertex_client.py works' and nothing else.",
    )
    print(response.text)
