"""FastAPI service for the Diligence dashboard.

Endpoints
=========

GET  /api/research/{ticker}
    Return the cached reconciliation + 4 agent JSONs from ``data/{ticker}/``.
    404 if the ticker has never been ingested + analysed.

POST /api/research/{ticker}
    Kick off ``agents.graph.run_for_ticker`` in a background task. Returns a
    ``run_id`` immediately. Progress is streamed via the SSE endpoint below.

GET  /api/research/{ticker}/stream
    Server-Sent Events. Emits one event per agent-node complete plus a
    terminal ``done`` / ``error`` event. Used by the dashboard for live
    runs; for the hackathon demo we serve cached NVDA without ever hitting
    this path.

GET  /api/research/{ticker}/audio
    Stream the earnings_call.mp3 with HTTP Range support for the
    wavesurfer.js player. The frontend never reads from disk directly.

Storage layout (per HANDOFF.md)
-------------------------------

    data/{TICKER}/
        analysis_filing.json     # FilingAnalysis
        analysis_call.json       # CallAnalysis
        analysis_bull.json       # BullCase
        analysis_bear.json       # BearCase
        reconciliation.json      # Reconciliation
        transcript.json          # Speechmatics json-v2 (word-level)
        earnings_call.mp3        # raw audio

Run locally::

    cd ~/diligence
    .venv/bin/python -m uvicorn backend.api:app --reload --port 8000

Production unit lives at /etc/systemd/system/diligence-api.service on the
Vultr box; nginx routes /api/ -> 127.0.0.1:8000.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

# Silence httpx/httpcore INFO — they leak query-string secrets when an
# upstream API call 4xx's. See feedback_httpx_secret_leak memory.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("diligence.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Resolve data dir: env override > repo-root/data
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DILIGENCE_DATA_DIR", REPO_ROOT / "data")).resolve()

# Filename → state["agents"] key. The dashboard reads them all in one shot.
AGENT_FILES: dict[str, str] = {
    "filing": "analysis_filing.json",
    "call": "analysis_call.json",
    "bull": "analysis_bull.json",
    "bear": "analysis_bear.json",
    "reconciliation": "reconciliation.json",
}

app = FastAPI(title="Diligence API", version="0.1.0")

# CORS — origin allowlist. `*` was a CSRF + spend-abuse vector: any site
# could POST /api/research/{T} and burn the user's Gemini quota. The
# DILIGENCE_CORS_ORIGINS env var is a comma-separated list; default to
# the production demo URL + local dev hosts. allow_credentials is left
# False (no cookie-bearing requests on this API) so the allowlist also
# blocks credentialed reads.
_DEFAULT_ALLOWED_ORIGINS = [
    "http://80.240.26.175",
    "https://80.240.26.175",
    "http://diligence.duckdns.org",
    "https://diligence.duckdns.org",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_origins_env = os.environ.get("DILIGENCE_CORS_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _origins_env.split(",") if o.strip()]
    if _origins_env
    else _DEFAULT_ALLOWED_ORIGINS
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------------
# In-process run registry. Single uvicorn worker (see systemd unit) so a
# plain dict is fine for the demo. Swap for Redis if we ever scale workers.
# -------------------------------------------------------------------------

# run_id -> asyncio.Queue[str]. Each item is a JSON-encoded SSE payload.
_RUN_QUEUES: dict[str, asyncio.Queue] = {}
# run_id -> {"ticker": str, "status": "running"|"done"|"error", "error": str|None}
_RUN_META: dict[str, dict[str, Any]] = {}
# run_id -> [json_str, ...]. Append-only log so an SSE reconnect can replay
# every event that has already fired before tailing the live queue.
_RUN_EVENTS_LOG: dict[str, list[str]] = {}
# Per-ticker asyncio.Lock — two concurrent POSTs for the same ticker queue
# on the same lock instead of both spawning ingest + agent runs in parallel.
_TICKER_LOCKS: dict[str, asyncio.Lock] = collections.defaultdict(asyncio.Lock)

# Rate-limit POST /api/research/{ticker} — per-IP deque of submission
# timestamps; max RATE_LIMIT_BURST cold-ingest requests per
# RATE_LIMIT_WINDOW_S window. Cached-ticker POSTs are exempt because they
# don't trigger paid spend, only a fast cache-replay.
RATE_LIMIT_WINDOW_S = 3600
RATE_LIMIT_BURST = 3
_POST_HISTORY: dict[str, "collections.deque[float]"] = collections.defaultdict(
    collections.deque
)


async def _emit(run_id: str, payload: dict) -> None:
    """Append an event to the replay log and the live queue (if open).

    Each event is wrapped with a monotonic per-run sequence number so an
    SSE connection that replays the log and then tails the queue can
    drop tail items whose seq is already in the replay (otherwise the
    same event gets yielded twice — once from log, once from queue).
    """
    log_ref = _RUN_EVENTS_LOG.setdefault(run_id, [])
    seq = len(log_ref)  # monotonic per run; same coroutine = no race
    item = {"seq": seq, "msg": json.dumps(payload)}
    log_ref.append(item)
    q = _RUN_QUEUES.get(run_id)
    if q is not None:
        await q.put(item)


# How long to keep finished-run replay logs + metadata before pruning.
# A single uvicorn worker process can stay up for days; without pruning
# every POST accumulates kilobytes of events forever.
RUN_RETENTION_S = 3600


def _purge_old_runs() -> None:
    """Drop run_id entries whose status is terminal and whose last event
    fired more than RUN_RETENTION_S ago. Best-effort; called inline from
    POST so we don't need a separate sweeper task."""
    import time as _time
    now = _time.monotonic()
    to_drop: list[str] = []
    for rid, meta in _RUN_META.items():
        if meta.get("status") not in ("done", "error"):
            continue
        ts = meta.get("_finished_at")
        if ts is None:
            # First time we've seen this run as terminal — stamp it now
            # so the next sweep can age it out.
            meta["_finished_at"] = now
            continue
        if now - ts > RUN_RETENTION_S:
            to_drop.append(rid)
    for rid in to_drop:
        _RUN_META.pop(rid, None)
        _RUN_EVENTS_LOG.pop(rid, None)
        _RUN_QUEUES.pop(rid, None)


def _now_monotonic() -> float:
    import time as _time
    return _time.monotonic()


def _client_ip(request: Request) -> str:
    """Resolve the client IP.

    Trust order:
      1. ``X-Real-IP`` set by nginx (`proxy_set_header X-Real-IP $remote_addr`).
         nginx overwrites client-supplied values, so this is the safest
         source when traffic comes through the canonical reverse proxy.
      2. The *last* entry of ``X-Forwarded-For`` — nginx appends the real
         client IP to whatever the client sent via `$proxy_add_x_forwarded_for`,
         so the rightmost hop is the trusted one. Reading the leftmost
         was a rate-limit bypass: a client could send any value and own
         a unique bucket.
      3. ``request.client.host`` as a last resort (direct connection).

    WARNING: if uvicorn is ever reachable without nginx in front, the
    X-* headers are arbitrarily forgeable. Bind uvicorn to 127.0.0.1
    only (matches the systemd unit).
    """
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-1]
    if request.client is not None:
        return request.client.host
    return "unknown"


def _rate_limit_peek(ip: str) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds) WITHOUT consuming a slot.

    Use this in the POST handler to reject a request early; the slot
    is only consumed after the bg task confirms a cold ingest is
    actually starting (see ``_rate_limit_consume``). Otherwise two
    concurrent POSTs for the same ticker both pass the peek, only one
    runs ingest, but both slots are debited — burning the user's quota
    on phantom work.
    """
    import time as _time
    now = _time.monotonic()
    dq = _POST_HISTORY[ip]
    cutoff = now - RATE_LIMIT_WINDOW_S
    while dq and dq[0] < cutoff:
        dq.popleft()
    if not dq:
        _POST_HISTORY.pop(ip, None)  # release empty deques to bound memory
        return True, 0
    if len(dq) >= RATE_LIMIT_BURST:
        retry = max(1, int(dq[0] + RATE_LIMIT_WINDOW_S - now))
        return False, retry
    return True, 0


def _rate_limit_consume(ip: str) -> None:
    """Append a timestamp to the per-IP deque. Called from inside the
    per-ticker lock once a cold ingest is confirmed to start."""
    import time as _time
    _POST_HISTORY[ip].append(_time.monotonic())


def _ticker_dir(ticker: str) -> Path:
    """Validate ticker and return its data dir.

    Tickers are 1-6 ASCII uppercase letters/digits. Anything else is a
    path-traversal smell — reject hard.
    """
    t = ticker.upper()
    if not t.isalnum() or not (1 <= len(t) <= 6):
        raise HTTPException(status_code=400, detail=f"invalid ticker: {ticker!r}")
    return DATA_DIR / t


def _load_agent_outputs(ticker_dir: Path) -> dict[str, Any]:
    """Read every agent JSON that exists. Missing files are returned as None."""
    out: dict[str, Any] = {}
    for key, fname in AGENT_FILES.items():
        p = ticker_dir / fname
        if p.exists():
            try:
                out[key] = json.loads(p.read_text())
            except json.JSONDecodeError as e:
                logger.error("malformed %s: %s", p, e)
                out[key] = None
        else:
            out[key] = None
    return out


def _load_transcript_words(ticker_dir: Path) -> list[dict]:
    """Flatten Speechmatics json-v2 results into UI-friendly word objects.

    Each item: ``{idx, content, start_time, end_time, speaker, type}``.
    Punctuation tokens (type='punctuation') keep their content but inherit
    speaker from the preceding word so they don't reset the speaker run.
    """
    p = ticker_dir / "transcript.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    results = raw.get("results", [])
    words: list[dict] = []
    last_speaker = "S1"
    for i, r in enumerate(results):
        alt = (r.get("alternatives") or [{}])[0]
        speaker = alt.get("speaker") or last_speaker
        last_speaker = speaker
        words.append(
            {
                "idx": i,
                "content": alt.get("content", ""),
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "speaker": speaker,
                "type": r.get("type", "word"),
            }
        )
    return words


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "data_dir": str(DATA_DIR)}


@app.get("/api/research/{ticker}")
def get_research(ticker: str) -> JSONResponse:
    """Return the cached agent outputs for a ticker."""
    td = _ticker_dir(ticker)
    if not td.exists():
        raise HTTPException(status_code=404, detail=f"no data for {ticker.upper()}")

    agents = _load_agent_outputs(td)
    if agents["reconciliation"] is None:
        raise HTTPException(
            status_code=409,
            detail=f"{ticker.upper()} ingested but reconciliation missing — run agents.run first",
        )

    manifest_path = td / "manifest.json"
    manifest: dict | None = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            logger.error("malformed manifest at %s: %s", manifest_path, e)

    return JSONResponse(
        {
            "ticker": ticker.upper(),
            "agents": agents,
            "manifest": manifest,
            "transcript_words": _load_transcript_words(td),
            "has_audio": (td / "earnings_call.mp3").exists(),
        }
    )


@app.post("/api/research/{ticker}")
async def start_research(
    ticker: str,
    request: Request,
    background_tasks: BackgroundTasks,
    reuse_cache: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Start (or surface) a research run for a ticker.

    Cold ticker: runs the full pipeline — ``services.ingest.ingest`` in a
    worker thread, then the agent graph. Cached ticker: ``ingest`` is
    skipped (manifest already present) and ``reuse_cache`` is forced on
    so the agent graph short-circuits at every cached analysis file.

    A new ``run_id`` is always returned; the SSE stream replays past
    events for the same ``run_id`` so the frontend can reconnect mid-run.

    Rate-limited: a single IP can submit at most ``RATE_LIMIT_BURST``
    *cold* (paid) POSTs per ``RATE_LIMIT_WINDOW_S`` window. Cached
    submissions are exempt because they only replay the existing cache.
    """
    td = _ticker_dir(ticker)
    full_cache = (td / "reconciliation.json").exists() and not force
    _purge_old_runs()
    ip = _client_ip(request)

    if not full_cache:
        # Peek the rate limit but do NOT consume a slot yet — concurrent
        # POSTs for the same ticker can both pass the peek, but only one
        # actually starts ingest inside the lock. The bg coroutine
        # consumes the slot atomically after confirming need_ingest=True.
        allowed, retry_after = _rate_limit_peek(ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit: {RATE_LIMIT_BURST} cold-ingest runs per "
                    f"hour per IP. Retry in ~{retry_after}s."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    run_id = uuid.uuid4().hex[:12]
    _RUN_QUEUES[run_id] = asyncio.Queue()
    _RUN_META[run_id] = {
        "ticker": ticker.upper(),
        "status": "running",
        "error": None,
    }
    _RUN_EVENTS_LOG[run_id] = []

    # If the ticker is fully cached and the caller did not pass force=true,
    # default to reusing cached analyses so we don't re-spend Gemini /
    # Featherless on the agent graph.
    effective_reuse_cache = reuse_cache or full_cache

    background_tasks.add_task(
        _run_full_pipeline_bg,
        run_id,
        ticker.upper(),
        effective_reuse_cache,
        force,
        ip,
    )
    return {
        "run_id": run_id,
        "ticker": ticker.upper(),
        "cached": full_cache,
    }


async def _run_full_pipeline_bg(
    run_id: str,
    ticker: str,
    reuse_cache: bool,
    force: bool,
    ip: str,
) -> None:
    """Background coroutine: optional ingest + agent graph, streamed via SSE.

    The per-ticker ``asyncio.Lock`` serialises concurrent runs for the same
    ticker so two judges hitting "Run NVDA" don't both pay for ingest /
    agents. The second caller's queue still gets events emitted via the
    replay log when the lock releases.

    Rate-limit slot is consumed inside the lock once we've confirmed a
    cold ingest is actually starting — prevents two concurrent POSTs for
    the same ticker from debiting two slots when only one will spend.
    """
    meta = _RUN_META[run_id]
    lock = _TICKER_LOCKS[ticker]
    try:
        async with lock:
            await _emit(run_id, {"event": "start", "ticker": ticker})

            td = DATA_DIR / ticker
            manifest_path = td / "manifest.json"
            need_ingest = force or not manifest_path.exists()
            if need_ingest:
                # Confirm and consume the rate-limit slot now.
                allowed, retry_after = _rate_limit_peek(ip)
                if not allowed:
                    await _emit(run_id, {
                        "event": "error",
                        "error": f"Rate limit reached during queued ingest. "
                                 f"Retry in ~{retry_after}s.",
                    })
                    meta["status"] = "error"
                    meta["error"] = "rate_limited"
                    meta["_finished_at"] = _now_monotonic()
                    return
                _rate_limit_consume(ip)
                await _emit(run_id, {"event": "ingest_start", "ticker": ticker})
                # Lazy import — keeps server bootstrap free of yt-dlp /
                # google-genai weight when serving cached data.
                from services.ingest import ingest as run_ingest
                manifest = await asyncio.to_thread(run_ingest, ticker, force=force)
                sources = manifest.get("sources") or {}
                audio_src = sources.get("audio") or {}
                await _emit(run_id, {
                    "event": "ingest_done",
                    "files": manifest.get("files") or {},
                    "warnings": manifest.get("warnings") or [],
                    "audio_tier": audio_src.get("tier"),
                    "audio_score": audio_src.get("score"),
                    "audio_url": audio_src.get("url"),
                    "audio_uploader": audio_src.get("uploader"),
                })
            else:
                await _emit(run_id, {"event": "ingest_cached"})

            # RECOMPUTE cache state INSIDE the lock. The POST handler's
            # full_cache decision was made before this coroutine queued
            # on the lock — two concurrent cold POSTs for the same ticker
            # would both have reuse_cache=False at that point. After the
            # first run writes reconciliation.json, the second wakes up
            # here and we MUST force reuse_cache=True so the agent graph
            # short-circuits instead of re-spending Gemini + Featherless
            # on outputs that already exist on disk. Codex 2026-05-17.
            reconciliation_path = td / "reconciliation.json"
            if reconciliation_path.exists() and not force:
                reuse_cache = True

            from agents.graph import build_graph
            graph = build_graph()
            initial = {
                "ticker": ticker,
                "data_dir": DATA_DIR,
                "reuse_cache": reuse_cache,
                "agents": {},
            }
            async for step in graph.astream(initial):
                for node_name, _delta in step.items():
                    await _emit(run_id, {
                        "event": "node_complete",
                        "node": node_name,
                    })

            meta["status"] = "done"
            meta["_finished_at"] = _now_monotonic()
            await _emit(run_id, {"event": "done", "ticker": ticker})
    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        logger.exception(
            "pipeline failed: ticker=%s run_id=%s", ticker, run_id,
        )
        meta["status"] = "error"
        meta["error"] = str(exc)
        meta["_finished_at"] = _now_monotonic()
        await _emit(run_id, {"event": "error", "error": str(exc)})
    finally:
        # Sentinel — the SSE generator exits when it sees None.
        q = _RUN_QUEUES.get(run_id)
        if q is not None:
            await q.put(None)


@app.get("/api/research/{ticker}/stream")
async def stream_research(
    ticker: str, run_id: str, request: Request,
) -> StreamingResponse:
    """SSE stream of pipeline + agent events.

    Replays every event already in ``_RUN_EVENTS_LOG[run_id]`` before
    tailing the live queue, so a reconnect (or a slow ProgressModal
    mount) doesn't miss the start / ingest_done events.

    Validates ticker format and confirms the run_id actually belongs
    to this ticker — otherwise the path parameter was being ignored
    entirely, which let any ticker string in the URL collect SSE for
    any valid run_id.
    """
    _ticker_dir(ticker)  # raises 400 on malformed ticker
    if run_id not in _RUN_META:
        raise HTTPException(status_code=404, detail=f"unknown run_id {run_id}")
    if _RUN_META[run_id].get("ticker") != ticker.upper():
        raise HTTPException(
            status_code=404,
            detail=f"run_id {run_id} does not belong to ticker {ticker.upper()}",
        )

    async def gen():
        # Replay first. Snapshot the log (list copy) so concurrent _emit
        # writes don't extend our iteration. Track the highest seq we've
        # yielded so the queue-tail can skip already-yielded items.
        replayed = list(_RUN_EVENTS_LOG.get(run_id, []))
        max_seq = -1
        for past in replayed:
            yield f"data: {past['msg']}\n\n"
            if past["seq"] > max_seq:
                max_seq = past["seq"]

        # If the run terminated before this client connected, the queue
        # is gone — the replay above is all there is.
        q = _RUN_QUEUES.get(run_id)
        if q is None:
            return

        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Keep-alive comment — proxies (nginx, CF) hate long idle.
                    yield ": keep-alive\n\n"
                    continue
                if item is None:
                    return
                # Drop tail items that the replay already covered.
                if isinstance(item, dict) and item.get("seq", -1) <= max_seq:
                    continue
                payload = item["msg"] if isinstance(item, dict) else item
                yield f"data: {payload}\n\n"
                if isinstance(item, dict) and item.get("seq", -1) > max_seq:
                    max_seq = item["seq"]
        finally:
            # Tidy up the queue once this client disconnects. Keep the
            # terminal status in _RUN_META + the replay log so a
            # subsequent reconnect can still see the run's history.
            _RUN_QUEUES.pop(run_id, None)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx: disable response buffering
        },
    )


@app.get("/api/tickers")
def list_tickers() -> dict[str, Any]:
    """List every ticker with a cached reconciliation.

    Powers the TickerLauncher chip set on the landing page. Each entry
    includes the manifest-derived company name, an ``audio_tier`` (T1/T2
    /T3/T4 or null when audio is absent), and a ``has_audio`` flag.
    """
    out: list[dict[str, Any]] = []
    if not DATA_DIR.exists():
        return {"tickers": out}
    for d in sorted(DATA_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "reconciliation.json").exists():
            continue
        entry: dict[str, Any] = {"ticker": d.name}
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text())
            except json.JSONDecodeError as e:
                logger.error("malformed manifest at %s: %s", manifest_path, e)
                m = {}
            entry["company"] = m.get("company")
            files = m.get("files") or {}
            entry["has_audio"] = bool(files.get("earnings_call_mp3"))
            audio = (m.get("sources") or {}).get("audio") or {}
            entry["audio_tier"] = audio.get("tier")
            entry["audio_score"] = audio.get("score")
        out.append(entry)
    return {"tickers": out}


@app.get("/api/research/{ticker}/audio")
def get_audio(ticker: str, request: Request) -> Response:
    """Serve the earnings call MP3 with HTTP Range support for wavesurfer.

    FileResponse already handles ``If-Modified-Since`` etc. For Range we
    implement the 206 path manually since FileResponse only returns 200.
    """
    td = _ticker_dir(ticker)
    audio_path = td / "earnings_call.mp3"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="audio not found")

    file_size = audio_path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        )

    # Parse "bytes=START-END" — END may be empty. Reject anything weird with 416.
    try:
        units, _, rng = range_header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError("not bytes unit")
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
        if start < 0 or end >= file_size or start > end:
            raise ValueError("range out of bounds")
    except ValueError:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    length = end - start + 1

    def stream_chunk():
        with audio_path.open("rb") as f:
            f.seek(start)
            remaining = length
            chunk = 64 * 1024
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        stream_chunk(),
        status_code=206,
        media_type="audio/mpeg",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "public, max-age=3600",
        },
    )
