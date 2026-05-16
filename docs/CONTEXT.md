# Diligence — Context briefing for a fresh Claude session

Paste this entire file into a new Claude Code session at `~/diligence` before asking for work. It captures everything the model needs to continue without re-discovering decisions.

---

## CURRENT STATUS (read this first)

**See `HANDOFF.md` at the repo root for the latest session-to-session status. This block is a snapshot of the original Day-1 briefing.**

### Day-1 complete ✅ (as of 2026-05-16 evening)
- Vertex AI auth helper (`vertex_client.py`) — `gcloud auth print-access-token` path, RobotBoy ADC untouched
- 5 service probes all PASS (Vertex, EDGAR, FMP, Featherless, Speechmatics)
- Full ingestion pipeline live: `python -m services.ingest <ticker_or_name>` → 10-K + 10-Q + fundamentals + earnings call MP3 + diarized transcript cached to `data/{ticker}/`
- Demo ticker NVDA fully ingested (364K char 10-K, 10,449-token transcript with 13 speakers)
- `SECURITY.md` rules in place; `.env` gitignored; httpx INFO secrets-leak fixed
- `HANDOFF.md` written for session continuity

### What is NOT built yet ❌
- Agents (Filing / Call / Bull / Bear / Reconciler) — `agents/` still empty
- LangGraph orchestration — not started
- FastAPI backend — not started
- React frontend — not started
- Vultr deployment — not started

About **20%** of the way to a submission-ready demo (foundation + ingestion done). 2 days remain.

### Why run the probe scripts before any agent code

Each agent depends on a sponsor's API: Vertex AI, Featherless (Qwen3), Speechmatics, Financial Modeling Prep, SEC EDGAR. If any of those keys is wrong or any endpoint behaves unexpectedly, we want to know **today**, not on Day 2 in the middle of writing the Bull agent.

A probe script does **one thing** — call the service in isolation with a tiny request and confirm it returns something sane. No agents, no orchestration, no UI. Just "does the credential work, does the endpoint exist, does the response look like what we expect?"

Day-1 discipline: **5 probes pass → agents are unblocked**. If a probe fails, fix the credential / endpoint / region before writing anything else.

The probes are throwaway. After Day 1 they will not be touched again. They exist purely so we never debug "is my key broken or is my agent code wrong?" in the middle of Day 2.

### What founder needs to do RIGHT NOW (Day 1, before any new Claude session)

1. `cp .env.example .env`
2. Open `.env`, fill in real keys for: `SPEECHMATICS_API_KEY`, `FEATHERLESS_API_KEY`, `FMP_API_KEY`. Update `SEC_USER_AGENT` to your real email.
3. Drop a short voice clip (5-10 sec MP3) at `data/probe_clip.mp3` for the Speechmatics probe. ANY clip works — say "this is a test" into the phone voice memo app and AirDrop it.
4. Run each probe one at a time. Paste the output if any fails.
   ```bash
   python scripts/probe_edgar.py
   python scripts/probe_fmp.py
   python scripts/probe_featherless.py
   python scripts/probe_speechmatics.py
   ```
5. Pick demo ticker (NVDA / TSLA / PLTR) — see "open questions" at the bottom.

Only after the 4 probes pass + ticker picked should a fresh Claude session start agent / ingestion work.

---

## What this project is

Diligence is an adversarial multi-agent investment due-diligence system built for the Milan AI Week / lablab.ai hackathon (Vultr, Gemini, Featherless, Speechmatics tracks, 3-day deadline). User picks a publicly-traded company → system ingests primary sources (SEC 10-K, earnings call MP3, fundamentals) → Bull and Bear agents independently build the strongest opposing cases from the same evidence → Reconciler surfaces disputed facts. Every claim is cited.

Persona: retail investor / early-stage analyst doing DYOR with institutional-grade discipline. Research-grade, NOT advisory. No buy/sell signals.

Defensible novelty:
1. Adversarial multi-agent reconciliation — Bull and Bear cite the same evidence, Reconciler ranks disputed facts by materiality.
2. Earnings call audio as first-class evidence via Speechmatics diarization — flag hedging, deflection, contradictions between prepared remarks and Q&A.

---

## Scope discipline — NOT building

- Portfolio management, robo-advice, buy/sell signals
- Real-time / live earnings call ingestion — pre-recorded MP3 from IR page is enough
- "Any company" support — demo runs on one carefully-chosen ticker (NVDA / TSLA / PLTR)
- Heavy technical analysis — one lightweight price+MA snapshot, nothing more
- M&A, hostile takeovers, ETF construction
- RAG (full 10-K fits in Gemini 1M context), Airflow, vector DBs, multi-framework orchestration

---

## Architecture

Three layers — minimum viable stack.

**1. Data ingestion** (cached locally, never refetched mid-demo)
- SEC EDGAR — 10-K / 10-Q, no auth, just User-Agent
- Investor relations page — one downloaded MP3 of the most recent earnings call
- Financial Modeling Prep free tier — fundamentals (P/E, revenue growth, margins, debt/equity)
- All cached as JSON in `data/{ticker}/`

**2. Agents**
- Filing Analyst — Gemini 2.5 Pro on full 10-K, extracts claims + flags accounting language
- Call Analyst — Gemini 2.5 Pro on diarized transcript, flags hedging / deflection / contradictions
- Bull Agent — Featherless Qwen3, parallel
- Bear Agent — Featherless Qwen3, parallel
- Reconciler — Gemini 2.5 Pro, identifies opposing interpretations of identical evidence, ranks by materiality

**3. Orchestration & delivery**
- LangGraph state machine, `asyncio.gather` for Bull/Bear parallel
- FastAPI backend on Vultr High-Performance VM (no GPU; all inference via hosted APIs)
- React three-column UI (Bull / Bear / Reconciler) + audio player with click-to-jump diarized transcript + fundamentals card
- JSON file cache for dev; Postgres optional polish if time allows

Stack pins: Pydantic for structured outputs, Tenacity for retries, httpx for HTTP, python-dotenv for env, asyncio for concurrency. No RAG.

---

## Sponsor tracks (all required)

| Track | Surface |
|-------|---------|
| Vultr | Backend host, public demo URL, repo, video |
| Gemini | `gemini-2.5-pro` for Filing / Call / Reconciler |
| Featherless | Qwen3 for Bull / Bear |
| Speechmatics | Batch transcription + speaker diarization on earnings call MP3 |

---

## Auth — already solved, do not change

`mirel-leonard-org` enforces `constraints/iam.disableServiceAccountKeyCreation`. SA JSON keys cannot be created. The laptop's well-known ADC file at `~/.config/gcloud/application_default_credentials.json` is owned by a separate production project (RobotBoy) and must not be overwritten.

Solution: `vertex_client.py` shells out to `gcloud auth print-access-token` against the active gcloud configuration, builds in-process `google.oauth2.Credentials`, never touches the ADC file. Token is cached for ~1 hour with proactive refresh skew. All Vertex calls import `get_client()` from this module.

### Project IDs

| Project | ID | Role |
|---------|-----|------|
| Diligence | `project-2be42b84-14e0-421a-b3a` | All Vertex billing here |
| RobotBoy | `project-27a856db-d84f-4ee4-a6a` | **Do not touch** |

### gcloud configurations

- `default` — points at RobotBoy; do not modify
- `hackathon` — points at Diligence, active during this work

Switch with `gcloud config configurations activate hackathon`.

Ignore the "active project does not match the quota project in your local Application Default Credentials" warning — it is cosmetic in our setup because `vertex_client.py` does not read the ADC file. **Do NOT** run `gcloud auth application-default set-quota-project` to silence it — that would clobber the RobotBoy ADC.

### Vertex SDK pins

- Use `google-genai`, not `vertexai.generative_models` (deprecated)
- `Client(vertexai=True, project=PROJECT_ID, location="global", credentials=creds)`
- `location="global"` for Gemini text — `us-central1` returns 404 for newer Gemini IDs
- Veo video is out of scope

### Backup of RobotBoy ADC

`~/adc-robotboy-backup.json` — restore if anything ever clobbers the well-known ADC.

---

## Repo layout

```
~/diligence/
├── README.md                # Setup, auth, day plan
├── vertex_client.py         # Auth helper — DO NOT EDIT lightly
├── .env.example             # Service credentials template
├── .env                     # Real keys (gitignored, founder fills in)
├── requirements.txt
├── .gitignore
├── scripts/
│   ├── probe_vertex.py      # ✅ PASSING — Gemini via Vertex confirmed
│   ├── probe_edgar.py       # SEC 10-K/10-Q lookup — no key needed
│   ├── probe_fmp.py         # FMP fundamentals — needs FMP_API_KEY
│   ├── probe_featherless.py # Qwen3 chat completion — needs FEATHERLESS_API_KEY
│   └── probe_speechmatics.py# Diarized transcription — needs SPEECHMATICS_API_KEY + data/probe_clip.mp3
├── services/__init__.py     # EMPTY — fills in Day 1 evening (real service clients)
├── agents/__init__.py       # EMPTY — fills in Day 2
├── data/                    # EMPTY — Day 1 ingestion writes here
└── docs/
    └── CONTEXT.md           # This file
```

---

## Day plan

**Day 1 (current)**
- ✅ Auth (vertex_client.py works)
- ✅ Probes scaffolded
- ⏳ Founder runs remaining 4 probes
- ⏳ Pick demo ticker
- ⏳ Build `services/ingest.py` (download 10-K + MP3 + fundamentals, cache to `data/{ticker}/`)

**Day 2** — agent layer (Filing, Call, Bull, Bear, Reconciler) + LangGraph orchestration

**Day 3** — React frontend + FastAPI server + Vultr deploy + demo video + submission

---

## What to do next in a fresh Claude session

Tell Claude:

> Read `docs/CONTEXT.md` end-to-end and `README.md`. Confirm current state matches the file. Run `python scripts/probe_vertex.py` to verify auth still works. Then ask me which of the 4 remaining probes have passed (Edgar / FMP / Featherless / Speechmatics) and whether I've picked the demo ticker. Based on what is unblocked, propose the next concrete step.

---

## Hard rules for any future Claude session

1. **Never** run `gcloud auth application-default login`. It overwrites the RobotBoy ADC file.
2. **Never** run `gcloud auth application-default set-quota-project`. Same reason.
3. **Never** edit `vertex_client.py` to use API keys or service-account JSON — both are blocked by org policy on this project.
4. **Never** call Vertex from `us-central1` for Gemini text. Always `global`.
5. **Never** install heavy frameworks (LangChain stacks beyond LangGraph, Airflow, vector DBs). Per scope.
6. **Never** suggest writing buy/sell recommendations. Research-grade only.
7. **Always** verify a service probe passes before integrating into agents.
8. **Always** use `asyncio` for parallel agent calls (Bull + Bear), not threading.
9. **Always** require citation back to source for every claim emitted by Filing / Call / Bull / Bear agents.
10. **Never** start a new gcloud auth flow without confirming it does not touch ADC.

---

## Credits / budget

| Source | Amount | Window |
|--------|--------|--------|
| Vultr | $200 | 30 days |
| Google Cloud / Vertex | $300 trial | 90 days, billing `017D51-8B13F6-F13198` |
| Speechmatics | $200 | promo `AIWEEK200` |
| Featherless | $25 | 1 month |

Constraint is time (3 days), not money.

---

## Open questions for founder

1. **Demo ticker** — NVDA / TSLA / PLTR — pick by Day 1 evening. Decision criteria: (a) recent earnings call has a downloadable MP3 on the IR page, (b) Bull and Bear sides both have credible substance (NVDA = strong both sides currently; TSLA = polarising; PLTR = niche but loud).
2. **Earnings call MP3 source** — usually IR page → Events / Webcasts → Replay link → audio file. Sometimes only video is published; if so we extract audio with ffmpeg.
3. **Vultr VM region** — Frankfurt closest to Romania for dev latency, NYC closest to most user judges. Default Frankfurt unless told otherwise.

End of brief.
