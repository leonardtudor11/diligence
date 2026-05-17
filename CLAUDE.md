# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**Diligence** — adversarial multi-agent due-diligence pipeline for public-company tickers, built for the lablab.ai Milan AI Week '26 hackathon (sponsors: Vertex AI, Featherless, Speechmatics, Vultr). User submits a ticker; system fetches 10-K + 10-Q (EDGAR) + earnings-call audio (yt-dlp → Speechmatics) + fundamentals (FMP), then runs five agents (Filing, Call, Bull, Bear, Reconciler) to surface materiality-ranked disputed facts. Frontend live at `http://80.240.26.175`.

**Read `HANDOFF.md` at the start of every session.** It carries the current Day-N critical path, deferred research items, and per-stage status — sources of truth that change faster than this file.

## Auth — every session

`mirel-leonard-org` GCP project forbids SA-key creation, and the laptop's default ADC belongs to a **separate production project (RobotBoy)** — overwriting it re-routes that project's billing. Auth runs through `vertex_client.get_client()`, which mints a short-lived gcloud OAuth token in-process.

```bash
cd ~/diligence
source .venv/bin/activate
gcloud config configurations activate hackathon
python -c "from vertex_client import get_client; c = get_client(); print(c.models.generate_content(model='gemini-2.5-flash', contents='Reply OK').text)"
```

The cosmetic "active project does not match quota project" warning is **expected**; ignore it. `vertex_client.py` does not read the ADC file.

**Hard rules** (full list in `SECURITY.md` §4 + §8):
- **Never** run `gcloud auth application-default login` or `gcloud auth application-default set-quota-project` — overwrites RobotBoy ADC.
- **Never** `git add -A` / `git add .`. Stage specific paths.
- Mute `httpx` + `httpcore` INFO loggers in any module that hits a query-string API (FMP key would leak on 4xx tracebacks). Pattern is at the top of `services/ingest.py`, `services/fmp.py`, `scripts/precache.py`.

## Common commands

### End-to-end paid pipeline (single ticker)
```bash
python -m services.ingest TICKER              # EDGAR + FMP + audio + Speechmatics → data/TICKER/*
python -m agents.run TICKER                   # 5-agent graph → analysis_*.json + reconciliation.json
python -m agents.run TICKER --reuse-cache     # re-run reconciler etc. without re-spending Gemini/Featherless
```

### Pre-flight only (no paid spend)
```bash
python -m scripts.precache TICKER --dry-run   # EDGAR + FMP probe + yt-dlp candidate scoring
python -m scripts.precache TICKER --yes       # full paid pipeline, skip confirmation
```
Pre-flight writes to `scripts/precache_audit.md` (append-only log).

### Backend / frontend dev servers
```bash
.venv/bin/python -m uvicorn backend.api:app --reload --port 8000
cd frontend && npm run dev                     # http://localhost:3000
```

### Vultr deploy
SSH: `ssh root@80.240.26.175`. systemd units `diligence-api.service` + `diligence-frontend.service` defined under `deploy/`; nginx routes `/api/` to `127.0.0.1:8000`. Per-stage rsync targets `/srv/diligence/data/TICKER/` (chown to uid 999).

## Architecture — the bits that span files

```
services/ingest.py
    ├─ services/edgar.py     SEC filings → data/T/{10k,10q}.json
    ├─ services/fmp.py       /stable/* endpoints → data/T/fundamentals.json
    ├─ services/audio.py     yt-dlp multi-candidate scoring + download → data/T/earnings_call.mp3
    └─ services/speech.py    Speechmatics batch + diarization audit → data/T/transcript.json
                                                                      → data/T/manifest.json

agents/graph.py (LangGraph)
    START ──► filing ─┐
              call   ─┤── (implicit join)
                       │
                       ├─► bull ─┐
                       │  bear  ─┤── (implicit join)
                       │         │
                       │         ▼
                       └────► reconciler ──► END
```

**Pydantic schemas in `agents/schemas.py` are the I/O contract for every node.** Citation → Claim → FilingAnalysis / CallAnalysis → BullCase / BearCase → Reconciliation. Vertex enforces `response_schema=<PydanticModel>` on Gemini; Featherless responses pass through `agents/_qwen.py` which strips markdown JSON fences before parsing.

**Parallel-write state** uses a module-scope `TypedDict` with `Annotated[dict, _merge_agents]` reducer (Python 3.14 strict forward-ref eval forces this — see `agents/graph.py:State`). Bull and Bear write disjoint keys (`agents.bull`, `agents.bear`) into `state["agents"]` so the reducer composes them losslessly.

**Cache reuse**: every node short-circuits on `state["reuse_cache"]` + presence of its `analysis_*.json` cache file. Lets you iterate on reconciler prompts without re-spending upstream credits.

**Audio candidate scoring** (`services/audio.py:find_best_audio_candidate`): probes N yt-dlp candidates across two queries (ticker-based + issuer-name-based), scores each on duration / title-positive / title-negative / uploader-tier (T1 issuer-match → T2 trusted aggregator → T3 editorial aggregator → T4 unverified) / recency-vs-target-date. Winner-or-None decision with full per-candidate breakdown in `manifest.sources.audio.candidates_considered`. Below threshold, manifest warning + pipeline continues filing-only.

**Diarization audit** (`services/speech.py:audit_speaker_coverage`): hard-fails the transcript on <20% word-level speaker coverage or 0 distinct speakers (call analyst depends on attribution); soft-warns at <80% or single-speaker, surfaced via `manifest.warnings`.

## Frontend pin

Frontend uses **Next.js 16.2** + React 19.2 + Tailwind 4. This is NOT the Next.js in training data; conventions and APIs have shifted. Read `frontend/AGENTS.md` and `node_modules/next/dist/docs/` before writing frontend code. JavaScript (not TypeScript) by author preference. Spline + GSAP for hero accents; Recharts for the disputed-facts bar; wavesurfer.js v7 for the click-to-jump transcript player.

## Model + API quirks

- **`google-genai` 2.3 GC race**: bind the client to a variable before `.models.generate_content(...)`. One-liner triggers a crash. Always `c = get_client(); c.models.generate_content(...)`.
- **Don't use `vertexai.generative_models`** — replaced by `google-genai`. Model ID `gemini-2.5-pro`, `location="global"` for 1 M context.
- **Featherless Qwen3-32B** wraps JSON output in markdown fences even with `response_format: {"type": "json_object"}`. `agents/_qwen.py` strips them. Thinking mode: pass `chat_template_kwargs: {enable_thinking: false}` plus `/no_think` suffix in the user prompt to disable.
- **FMP free tier**: only `/stable/*` works (v3 returns 403). Daily quota 250 calls. `/stable/profile` returns a **list** of one dict, not a dict — accessing `.get("companyName")` on the result throws.
- **EDGAR `recent` arrays are newest-first.** A dict comprehension keyed by form (`{f["form"]: f for f in filings}`) clobbers to the **oldest** filing because dict comprehensions keep the **last** value. Use `setdefault()` or `candidates[0]`.

## Repo layout

```
services/      production ingestion clients (EDGAR, FMP, audio, Speechmatics)
agents/        Pydantic schemas + 5 agent modules + LangGraph orchestrator + CLI runner
backend/       FastAPI service (GET/POST/SSE on /api/research/{ticker}, ranged audio)
frontend/      Next.js 16.2 landing + /research/[ticker] dashboard
scripts/       Day-1 probes + precache (pre-flight + paid pipeline batch runner)
deploy/        systemd units + nginx snippet for Vultr
data/{T}/     per-ticker cache (10k.json, 10q.json, fundamentals.json,
              earnings_call.mp3, transcript.json, analysis_*.json,
              reconciliation.json, manifest.json)
docs/          AUDIT.md (Day-1 review), RESEARCH.md (locked architecture pins),
              CONTEXT.md (project briefing)
HANDOFF.md    living per-session handoff — read first
SECURITY.md   hard rules + audit checklist
```

## User communication conventions

- `AskUserQuestion` dropdowns are **broken in the user's Claude Code UI**. Ask in plain prose ("A) … B) … C) — which?").
- Mirel asks for **WHY before changes**, flags security issues immediately, prefers surgical fixes over rebuilds, JavaScript over TypeScript, short sentences and tables for comparisons.
- Caveman mode is persistent across sessions via SessionStart hook (`/caveman lite|full|ultra` to switch, "stop caveman" / "normal mode" to disable). Code, commits, security warnings always normal English.
