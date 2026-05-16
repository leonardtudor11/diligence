# Diligence

Adversarial multi-agent investment due-diligence system. Built for Milan AI Week / lablab.ai hackathon (Vultr, Gemini, Featherless, Speechmatics tracks).

User picks a publicly-traded company. The system ingests primary sources (SEC 10-K, earnings call audio, fundamentals), runs specialized AI agents that independently build the strongest Bull case and Bear case from the same evidence, then synthesizes a Reconciler analysis that surfaces disputed facts. Every claim cites its source.

**Research-grade, not advisory.** No buy/sell/hold recommendations. Evidence and counter-evidence; the human decides.

---

## Architecture (three layers)

1. **Data ingestion** — SEC EDGAR (10-K/10-Q), investor-relations MP3 (earnings call), Financial Modeling Prep (fundamentals). Cached to `data/{ticker}/` as JSON for deterministic, offline-able demos.
2. **Agent layer**
   - Filing Analyst — Gemini 2.5 Pro on full 10-K
   - Call Analyst — Gemini 2.5 Pro on diarized transcript
   - Bull Agent — Featherless Qwen3, parallel
   - Bear Agent — Featherless Qwen3, parallel
   - Reconciler — Gemini 2.5 Pro, surfaces disputed facts
3. **Orchestration & delivery** — LangGraph state machine, FastAPI backend, React three-column UI, audio player with click-to-jump diarized transcript, Vultr deployment.

Out of scope: RAG, vector DBs, Airflow, technical charts beyond a snapshot, M&A / ETF construction, real-time live calls.

---

## Auth — critical reproducibility note

`mirel-leonard-org` enforces `constraints/iam.disableServiceAccountKeyCreation`, so service-account JSON keys cannot be created. The laptop's Application Default Credentials file is also owned by a separate production project (RobotBoy) — overwriting it would re-route that project's billing.

**Solution:** mint a short-lived OAuth access token via `gcloud auth print-access-token` against the active gcloud configuration. Token lives in-process, is auto-refreshed before expiry, never touches disk. ADC file is untouched.

Implementation: `vertex_client.py`. All Vertex AI work imports `get_client()` from that module.

### One-time setup

```bash
# Separate gcloud configuration for this project
gcloud config configurations create hackathon
gcloud config configurations activate hackathon
gcloud auth login mirel_leonard@yahoo.com
gcloud config set project project-2be42b84-14e0-421a-b3a

# Confirm Vertex enabled
gcloud services enable aiplatform.googleapis.com --project=project-2be42b84-14e0-421a-b3a
```

### Every working session

```bash
gcloud config configurations activate hackathon
cd ~/diligence
source .venv/bin/activate
```

### Project IDs

| Project | ID | Notes |
|---------|-----|-------|
| Diligence (hackathon) | `project-2be42b84-14e0-421a-b3a` | All Vertex calls billed here |
| RobotBoy (production) | `project-27a856db-d84f-4ee4-a6a` | Untouched by this repo |

### Vertex SDK notes

- Use `google-genai`, not the deprecated `vertexai.generative_models`
- `Client(vertexai=True, project=..., location="global", credentials=...)`
- `location="global"` for Gemini text/image (us-central1 returns 404 for newer Gemini IDs)
- `location="us-central1"` only if Veo video added later (not in current scope)

---

## Service credentials

Copy `.env.example` → `.env` and fill in:

| Var | Source |
|-----|--------|
| `SPEECHMATICS_API_KEY` | speechmatics.com console, AIWEEK200 promo applied |
| `FEATHERLESS_API_KEY` | featherless.ai dashboard |
| `FMP_API_KEY` | financialmodelingprep.com free tier |
| `SEC_USER_AGENT` | EDGAR ToS — set to your real email |

---

## Verify each service independently — do this BEFORE agent code

Day-1 discipline. Each service must pass its own probe before integration.

```bash
python scripts/probe_vertex.py        # Gemini via Vertex
python scripts/probe_speechmatics.py  # batch transcription + diarization
python scripts/probe_featherless.py   # Qwen3 inference
python scripts/probe_fmp.py           # fundamentals
python scripts/probe_edgar.py         # SEC 10-K/10-Q lookup
```

`probe_speechmatics.py` needs a short MP3 at `data/probe_clip.mp3` (any 5-10 sec voice clip).

---

## Repo layout

```
diligence/
├── vertex_client.py         # Auth helper — gcloud token, never touches ADC
├── .env.example             # Service credentials template
├── requirements.txt
├── scripts/                 # Throwaway probes for each service
├── services/                # Production service clients (Day 1 evening +)
├── agents/                  # Bull / Bear / Reconciler / Filing / Call (Day 2)
├── data/                    # Cached primary sources, JSON per ticker
└── docs/                    # Architecture notes, demo script
```

---

## Sponsor track alignment

| Track | What we use |
|-------|-------------|
| Vultr | Backend host + public demo URL |
| Gemini | `gemini-2.5-pro` for Filing / Call / Reconciler heavy reasoning |
| Featherless | Qwen3 for Bull / Bear adversarial agents |
| Speechmatics | Batch transcription + speaker diarization on earnings call MP3 |

---

## Day plan

- **Day 1** — auth + probes + pick demo ticker (NVDA / TSLA / PLTR) + data ingestion
- **Day 2** — agent layer (5 agents) + LangGraph orchestration
- **Day 3** — frontend + Vultr deploy + demo video + submission
