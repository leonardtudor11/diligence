"""Featherless Qwen3-32B client + JSON parsing helpers.

RQ3 SURPRISE (`docs/RESEARCH.md`): Featherless `response_format:
{"type": "json_object"}` is accepted but Qwen3-32B still wraps the
payload in ```json fences sometimes. Every caller must strip fences
before `json.loads`. The fallback below also tries to extract the
outermost JSON object via brace matching, which handles the case where
the model emits prose before/after the JSON despite the system prompt.

Thinking mode (`chat_template_kwargs.enable_thinking`) is on by default
here — the Bull and Bear agents are the adversarial-reasoning step of
the pipeline and benefit from the extra deliberation. Caller can flip
it off for utility calls (e.g. quick formatting passes). When thinking
is on, give the model `max_tokens >= 4000` — the `<think>` budget eats
into the same envelope as the visible answer.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

# Mute httpx INFO — Featherless key sits in the Authorization header but
# request URLs can carry parameters; same defence as other modules.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


FEATHERLESS_URL = "https://api.featherless.ai/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3-32B"

_FENCE_OUTER = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_TRAIL = re.compile(r"\s*```\s*$", re.IGNORECASE)


def parse_qwen_json(text: str) -> Any:
    """Strip ```json fences (if present) and return the parsed JSON.

    Falls back to extracting the outermost {…} via brace matching if the
    initial parse fails. Raises `json.JSONDecodeError` if neither path
    finds valid JSON.
    """
    if not text:
        raise json.JSONDecodeError("empty response from Featherless", "", 0)

    cleaned = _FENCE_OUTER.sub("", text.strip())
    cleaned = _FENCE_TRAIL.sub("", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback — find the first balanced top-level object.
    start = cleaned.find("{")
    if start == -1:
        raise json.JSONDecodeError("no JSON object found", cleaned, 0)
    depth = 0
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start : i + 1])
    raise json.JSONDecodeError(
        "unbalanced braces in Featherless response", cleaned, len(cleaned)
    )


async def call_qwen(
    messages: List[dict],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4500,
    temperature: float = 0.4,
    enable_thinking: bool = True,
    timeout: float = 180.0,
) -> Any:
    """POST to Featherless `/v1/chat/completions` and return parsed JSON.

    `response_format` is set to `json_object` but we still pass everything
    through `parse_qwen_json` because Qwen3 has been observed wrapping
    payloads in fences despite the flag.
    """
    key = os.environ["FEATHERLESS_API_KEY"]

    body: dict = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            FEATHERLESS_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )

    if resp.status_code != 200:
        # Scrub anything that could contain the key from the surfaced text.
        raise RuntimeError(
            f"Featherless HTTP {resp.status_code} {resp.reason_phrase} "
            f"(body length {len(resp.text)})"
        )

    payload = resp.json()
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Featherless response shape unexpected: {exc}")

    return parse_qwen_json(content)


def format_claim_catalogue(filing_claims, call_claims) -> str:
    """Render F + C claims as a compact reference list the adversarial agent
    consults when citing by ID. Pydantic Claim objects in, plain text out.
    """
    lines: List[str] = []
    for c in filing_claims:
        section = c.source.section or "unknown"
        lines.append(f"{c.claim_id} [{c.category}] ({section}) {c.text}")
    for c in call_claims:
        spk = c.source.speaker or "?"
        ts = c.source.start_time or 0.0
        lines.append(f"{c.claim_id} [{c.category}] ({spk} t={ts:.0f}s) {c.text}")
    return "\n".join(lines)


def valid_claim_ids(filing_claims, call_claims) -> set:
    """Return the union of every Filing + Call claim_id. Bull/bear adversarial
    auditor uses this set to reject any pillar that cites a non-existent ID.
    """
    return {c.claim_id for c in filing_claims} | {c.claim_id for c in call_claims}
