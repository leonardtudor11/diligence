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

# CORS — frontend served from same origin in prod (nginx), but allow
# everything in dev so `next dev` on :3000 can call :8000 directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

    return JSONResponse(
        {
            "ticker": ticker.upper(),
            "agents": agents,
            "transcript_words": _load_transcript_words(td),
            "has_audio": (td / "earnings_call.mp3").exists(),
        }
    )


@app.post("/api/research/{ticker}")
async def start_research(
    ticker: str,
    background_tasks: BackgroundTasks,
    reuse_cache: bool = False,
) -> dict[str, str]:
    """Trigger a fresh graph run for a ticker."""
    td = _ticker_dir(ticker)
    if not td.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{ticker.upper()} not ingested — run services.ingest first",
        )

    run_id = uuid.uuid4().hex[:12]
    _RUN_QUEUES[run_id] = asyncio.Queue()
    _RUN_META[run_id] = {"ticker": ticker.upper(), "status": "running", "error": None}

    background_tasks.add_task(_run_graph_bg, run_id, ticker.upper(), reuse_cache)
    return {"run_id": run_id, "ticker": ticker.upper()}


async def _run_graph_bg(run_id: str, ticker: str, reuse_cache: bool) -> None:
    """Background coroutine: execute the agent graph and stream node-complete
    events into the SSE queue.
    """
    q = _RUN_QUEUES[run_id]
    meta = _RUN_META[run_id]
    try:
        # Lazy import — keeps `uvicorn backend.api:app --reload` fast and
        # avoids pulling Vertex/Featherless deps into the import graph if
        # the server is only serving cached data.
        from agents.graph import build_graph

        graph = build_graph()
        initial = {
            "ticker": ticker,
            "data_dir": DATA_DIR,
            "reuse_cache": reuse_cache,
            "agents": {},
        }

        await q.put(json.dumps({"event": "start", "ticker": ticker}))

        # `astream` yields one update per node completion. Each update is
        # {node_name: state_delta}; we forward just the node name so the UI
        # can light up a progress badge without leaking model output.
        async for step in graph.astream(initial):
            for node_name, _delta in step.items():
                await q.put(json.dumps({"event": "node_complete", "node": node_name}))

        meta["status"] = "done"
        await q.put(json.dumps({"event": "done", "ticker": ticker}))
    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        logger.exception("graph run failed: ticker=%s run_id=%s", ticker, run_id)
        meta["status"] = "error"
        meta["error"] = str(exc)
        await q.put(json.dumps({"event": "error", "error": str(exc)}))
    finally:
        # Sentinel — the SSE generator exits when it sees None.
        await q.put(None)


@app.get("/api/research/{ticker}/stream")
async def stream_research(ticker: str, run_id: str, request: Request) -> StreamingResponse:
    """SSE stream of node-complete events for an in-flight run."""
    q = _RUN_QUEUES.get(run_id)
    if q is None:
        raise HTTPException(status_code=404, detail=f"unknown run_id {run_id}")

    async def gen():
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
                yield f"data: {item}\n\n"
        finally:
            # Tidy up — keep the run's terminal status in _RUN_META so the
            # client can still GET the final result; only the queue dies.
            _RUN_QUEUES.pop(run_id, None)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx: disable response buffering
        },
    )


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
