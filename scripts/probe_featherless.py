"""Probe — confirm Featherless serves Qwen3 family inference.

Featherless exposes an OpenAI-compatible /v1/chat/completions endpoint.
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("FEATHERLESS_API_KEY")
BASE = "https://api.featherless.ai/v1"
MODEL = os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen3-32B")


def main() -> None:
    if not API_KEY:
        print("ERROR: FEATHERLESS_API_KEY not set in .env")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": "Reply with one short sentence confirming you are a Qwen model running on Featherless. /no_think",
            }
        ],
        "max_tokens": 200,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    with httpx.Client(timeout=60) as http:
        r = http.post(f"{BASE}/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

    print("MODEL    :", data.get("model"))
    print("RESPONSE :", data["choices"][0]["message"]["content"].strip())
    print()
    print("OK — Featherless auth + Qwen3 inference verified.")


if __name__ == "__main__":
    main()
