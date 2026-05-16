# Handoff — read this at the start of every new Claude session

Last updated: 2026-05-16 (Day 1 of the 3-day hackathon).

If you are a fresh Claude session, read this file first, then `docs/CONTEXT.md`, then `SECURITY.md`. Do not rerun the Day-1 probes — they all passed and the ingestion pipeline is live.

---

## Status at handoff

**Day-1 foundation: COMPLETE.** All 5 service probes pass. Full ingestion pipeline runs end-to-end on NVDA.

```
data/NVDA/
├── 10k.json              381 KB  — 364,373 chars stripped 10-K text
├── 10q.json              184 KB  — 170,652 chars 10-Q text
├── fundamentals.json      30 KB  — FMP profile + ratios + 3 statements
├── earnings_call.mp3      43 MB  — Q4 FY26 full call (~60 min)
├── transcript.json       2.6 MB  — 10,449 word-level tokens, 13 speakers
└── manifest.json         344 B   — 0 warnings, all stages green
```

Day-1 wall time end-to-end on a fresh NVDA run: ~2:50.

---

## "What's next" — exact next step

**Day 2 = agent layer.** Five agents reading from `data/{ticker}/` JSON, no live API calls during agent dev. Build order:

1. **Filing Analyst** (Gemini 2.5 Pro) — reads `10k.json` + `10q.json`, extracts claims with citations, flags accounting language.
2. **Call Analyst** (Gemini 2.5 Pro) — reads `transcript.json`, identifies hedging, deflection, contradictions between prepared remarks (S1/S2) and Q&A.
3. **Bull Agent** (Featherless Qwen3) — strongest investment case from the same evidence.
4. **Bear Agent** (Featherless Qwen3) — strongest counter-case from the same evidence. Bull + Bear run in parallel via `asyncio.gather`.
5. **Reconciler** (Gemini 2.5 Pro) — disputed-fact extraction, materiality ranking.

All five emit Pydantic-validated JSON. Stack pins:
- `google-genai` Client with `vertexai=True, location="global"`, model `gemini-2.5-pro` (1M ctx, 65K output, structured-output supported).
- Featherless OpenAI-compatible `/v1/chat/completions`, model `Qwen/Qwen3-32B`, `chat_template_kwargs.enable_thinking` per-call.
- Orchestration: LangGraph state machine, parallel Bull/Bear inside one node with `asyncio.gather` (per 2026 best-practice research notes in `docs/RESEARCH.md` — write this if it doesn't exist yet).

---

## What blocks on Mirel (founder) input

Nothing blocking right now. Day-2 agent work can start immediately on the cached NVDA data. Open items, not blockers:

1. **FMP key rotation** — deferred until ~12 h after Day-1 keying (per Mirel's note 2026-05-16 evening). Defensive only; the key surfaced briefly in a local 403 traceback, never pushed to git.
2. **Vultr region** — defaults to Frankfurt unless told otherwise. Not needed until Day-3 deploy.
3. **Additional demo tickers** — only NVDA used in Day-2; TSLA/PLTR optional polish on Day-3.

---

## Hard rules — do not violate

1. Never run `gcloud auth application-default login` or `gcloud auth application-default set-quota-project` on this machine — overwrites the RobotBoy production ADC. See `feedback_robotboy_adc` memory and `SECURITY.md` §4.
2. Never `git add -A` or `git add .`. Always stage specific files. `.env` is gitignored but be paranoid.
3. Never log API keys. httpx INFO must be silenced in any new module (see `services/ingest.py` lines that mute `httpx`/`httpcore` loggers — copy that pattern).
4. Never use the `vertexai.generative_models` legacy SDK. Use `google-genai`. Model ID `gemini-2.5-pro`, location `global` for text.
5. Never enable Veo (out of scope).

---

## Quick verification at session start

```bash
cd ~/diligence
source .venv/bin/activate
gcloud config configurations activate hackathon
python -c "from vertex_client import get_client; print(get_client().models.generate_content(model='gemini-2.5-flash', contents='Reply OK').text)"
```

If that prints "OK" (or similar), auth still works. No need to re-run probes.

---

## Architecture pins (for Day-2 builders)

- Per-agent module under `agents/` — `filing.py`, `call.py`, `bull.py`, `bear.py`, `reconciler.py`. Each exports one async function taking the relevant cached JSON and returning a Pydantic model.
- Shared Pydantic schemas in `agents/schemas.py` — `Claim`, `BullCase`, `BearCase`, `DisputedFact`, etc. Every claim has a `source` field with citation pointer (`{"type": "10-K", "section": "...", "char_range": [start, end]}` for filings, `{"type": "call", "speaker": "S2", "start_time": 1423.7, "end_time": 1431.2}` for transcript).
- Orchestration in `orchestrator.py` (or `agents/graph.py`). LangGraph `StateGraph`, single node fanout for Bull+Bear via `asyncio.gather`. State fields that get parallel writes must use `Annotated[list, operator.add]`.
- No RAG. Full 10-K fits in Gemini's 1M context easily (NVDA 10-K = 364 K chars ≈ 90 K tokens).

---

## Day-3 preview

FastAPI backend + React 3-column UI (Bull / Bear / Reconciler) + audio player with click-to-jump diarized transcript + Vultr deploy + 3-min demo video.

Audio player: `wavesurfer.js` v7 + `@wavesurfer/react` for click-to-seek. Transcript word objects already carry `start_time`/`end_time`/`speaker` from Speechmatics json-v2 — frontend can render highlighted spans that scroll-sync to playback.

Vultr instance: High-Frequency 4 vCPU / 8 GB enough (no GPU; all inference is hosted Gemini + Featherless + Speechmatics). Frankfurt region.

---

## Where to find things

- `docs/CONTEXT.md` — original project briefing (don't paste anymore; HANDOFF.md replaces it for ongoing sessions).
- `SECURITY.md` — full secret-handling + git-hygiene + deployment rules.
- `services/` — production ingestion pipeline.
- `scripts/` — Day-1 throwaway probes + `fetch_audio.py` standalone CLI.
- `vertex_client.py` — auth helper, do not touch.
- `~/.claude/projects/-Users-mirel-leonardtudor-diligence/memory/` — Claude memory file backing.

---

## Lessons learned (Day 1)

- **FMP migrated `/api/v3/` → `/stable/`**. New free-tier keys 403 on v3. Endpoint pattern changed from `/profile/{ticker}` to `/profile?symbol={ticker}`. See `reference_fmp_stable_migration` memory.
- **Qwen3 default = thinking mode**. With low `max_tokens` the entire budget is consumed by `<think>` tokens and the answer is empty. Toggle off via `chat_template_kwargs: {enable_thinking: false}` and/or `/no_think` suffix in user message. See `reference_qwen3_thinking_toggle` memory.
- **httpx INFO logs leak query-string secrets**. The FMP key surfaced in a 403 traceback. Mitigation: `logging.getLogger("httpx").setLevel(logging.WARNING)` at the top of any entrypoint. Done in `services/ingest.py`.
- **SEC primary docs are inline XBRL, not plain HTML**. bs4 emits `XMLParsedAsHTMLWarning`; suppress per-module. Text extraction works fine with `lxml` parser.
- **YouTube + yt-dlp** works for big tickers (NVDA confirmed) but `--match-filter "duration > 1200"` is necessary to filter out short clips. May not work for small-cap or non-US tickers — fall back to manual MP3 placement at `data/{TICKER}/earnings_call.mp3`.
- **Gemini 2.5 Pro model ID is plain `gemini-2.5-pro`** at `location="global"` (verified from official Google docs page, not Claude's guess). Trust the Vertex Model Garden, not training data.
