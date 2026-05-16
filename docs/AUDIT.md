# Day-1 adversarial audit

Run by an adversarial-review subagent on 2026-05-16 against commit `1e32c29`, immediately before public release. Severity legend: 🔴 critical, 🟡 risk, ❓ open design question.

## Findings + remediation

| Sev | Location | Problem | Status |
|-----|----------|---------|--------|
| 🔴 | `services/speech.py:62` | `r.json()["id"]` unguarded — malformed Speechmatics response → uncaught `KeyError`/`JSONDecodeError` | ✅ Fixed (wrapped in try/except, raises `TranscriptionFailed`) |
| 🔴 | `services/speech.py:72` | `r.json()["job"]["status"]` unguarded nested key access | ✅ Fixed (same wrapping pattern) |
| 🟡 | `services/fmp.py:39` | No explicit 429 rate-limit handling. Persistent 429 propagates as raw `httpx.HTTPStatusError` | ✅ Fixed (429 raises `FundamentalsUnavailable`) |
| 🟡 | `services/edgar.py:43` | No explicit 429 handling on SEC EDGAR (10 req/sec ceiling) | ✅ Fixed (raises internal `_EdgarRateLimited` → caught by ingest as `DiligenceError`) |
| 🟡 | `services/audio.py:74` | yt-dlp stderr tail (300 chars) logged on error — could expose local paths | ✅ Fixed (only last stderr line surfaced) |
| 🟡 | `services/speech.py:60` | `r.text[:300]` logged on Speechmatics 4xx — response body may echo request metadata | ✅ Fixed (logs status + reason phrase only) |
| 🟡 | `services/ingest.py:144` | No post-write content validation. Silent write failure → agents get empty file | ⏳ Day-2: add schema validation in `agents/schemas.py` when reading cached JSON |
| 🟡 | `services/speech.py:62` | No `job_id` format validation. Malformed ID → silent 404 loop until timeout | ⏳ Low priority — Speechmatics never returned malformed ID in any of our runs |
| ❓ | `services/audio.py:32` | `ytsearch1` is unauthenticated. Any uploader can publish a fake earnings call → yt-dlp grabs it → agents analyze fake content | ⏳ **Day-2 design priority** — see "Open design question" below |

## Open design question: YouTube source authentication

`ytsearch1` returns the top YouTube hit. There is no signal that the audio is the actual issuer's call. Mitigation surface area for Day-2 agents:

1. Capture `webpage_url` + `uploader` + `title` + `duration` at fetch time → write to `data/{ticker}/audio_source.json` alongside the MP3.
2. UI surfaces source URL + uploader prominently. Judge or end-user clicks through to verify.
3. Agents tag any claim sourced from this audio with `confidence_band: "unverified_audio"` until an authoritative source is wired in.
4. Production swap to Quartr API (paid, catalogued) when budget allows.

This is **not** a Day-1 blocker — the demo runs on a single curated ticker (NVDA) and the source can be eyeballed once. It becomes critical the moment we let arbitrary users type in any ticker.

## Findings NOT fixed (intentional)

- 🟡 `services/speech.py` job_id format validation — Speechmatics IDs are 10-char alphanumeric per observation; no published spec to validate against; defer until we see a real malformed ID in the wild.
- 🟡 `services/ingest.py` post-write content validation — better solved at the agent layer by Pydantic schemas reading the cached JSON; will be implemented Day-2 in `agents/schemas.py`.

## Counts

| Severity | Found | Fixed | Deferred |
|----------|-------|-------|----------|
| 🔴 critical | 2 | 2 | 0 |
| 🟡 risk | 6 | 4 | 2 (both have clear Day-2 paths) |
| ❓ design | 1 | 0 | 1 (tracked as Day-2 priority) |

All critical issues resolved before public-repo push. Day-1 ingestion pipeline considered safe for the public repo and ready for Day-2 agent integration.
