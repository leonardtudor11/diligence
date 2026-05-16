"""LangGraph orchestrator for the Diligence agent layer.

Dataflow:

    START
      │
      ├── Filing Analyst (Gemini)        ─┐
      ├── Call Analyst   (Gemini)        ─┤   fan-out, parallel
      │                                   │
      ▼                                   ▼
    (implicit join — Bull/Bear wait on both)
      │
      ├── Bull Agent (Featherless Qwen3) ─┐
      ├── Bear Agent (Featherless Qwen3) ─┤   fan-out, parallel
      │                                   │
      ▼                                   ▼
    (implicit join)
      │
      └── Reconciler (Gemini)
          │
          ▼
        END

Architecture pins from `docs/RESEARCH.md`:

* RQ1: every agent exports `async def`; LangGraph calls them directly.
* RQ4: State is a module-scope `TypedDict` so `get_type_hints` resolves
  `Annotated[dict, _merge_agents]` cleanly under Python 3.14.
* Bull and Bear write disjoint keys into `state["agents"]` so the
  `_merge_agents` reducer composes them losslessly.

State contract:

    {
      "ticker": "NVDA",
      "data_dir": Path("data"),
      "reuse_cache": False,
      "agents": {
        "filing": {... FilingAnalysis dump ...},
        "call":   {... CallAnalysis dump ...},
        "bull":   {... BullCase dump ...},
        "bear":   {... BearCase dump ...},
        "reconciliation": {... Reconciliation dump ...},
      }
    }

The `reuse_cache` flag lets each node short-circuit if the cached JSON
already exists on disk — the orchestrator (`agents.run`) sets this when
iterating on downstream behaviour without re-spending Gemini/Featherless
calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.bear import build_bear_case
from agents.bull import build_bull_case
from agents.call import analyze_call
from agents.filing import analyze_filings
from agents.reconciler import reconcile
from agents.schemas import (
    BearCase,
    BullCase,
    CallAnalysis,
    FilingAnalysis,
    Reconciliation,
)


def _merge_agents(left: dict | None, right: dict | None) -> dict:
    """Dict reducer for parallel writes into `state['agents']`.

    Last-write-wins per key — fine because each agent writes a unique key
    (filing / call / bull / bear / reconciliation). See RQ4 in
    `docs/RESEARCH.md`.
    """
    out: dict = dict(left or {})
    out.update(right or {})
    return out


class State(TypedDict):
    """Module-scope TypedDict so LangGraph's `get_type_hints(include_extras=True)`
    can resolve `Annotated` references under Python 3.14. (RQ4 gotcha.)
    """

    ticker: str
    data_dir: Path
    reuse_cache: bool
    agents: Annotated[dict, _merge_agents]


def _cache_path(state: State, name: str) -> Path:
    return state["data_dir"] / state["ticker"] / f"analysis_{name}.json"


def _load_cached(state: State, name: str, model_cls) -> Any | None:
    """Return a Pydantic-validated cache hit, or None if the file does not exist
    or `reuse_cache` is False.
    """
    if not state.get("reuse_cache"):
        return None
    path = _cache_path(state, name)
    if not path.exists():
        return None
    return model_cls.model_validate_json(path.read_text())


async def filing_node(state: State) -> dict:
    cached = _load_cached(state, "filing", FilingAnalysis)
    result = cached or await analyze_filings(state["ticker"], state["data_dir"])
    if cached:
        print(f"[filing] {state['ticker']} cache-hit (skipped Gemini call)")
    return {"agents": {"filing": result.model_dump(mode="json")}}


async def call_node(state: State) -> dict:
    cached = _load_cached(state, "call", CallAnalysis)
    result = cached or await analyze_call(state["ticker"], state["data_dir"])
    if cached:
        print(f"[call] {state['ticker']} cache-hit (skipped Gemini call)")
    return {"agents": {"call": result.model_dump(mode="json")}}


async def bull_node(state: State) -> dict:
    cached = _load_cached(state, "bull", BullCase)
    result = cached or await build_bull_case(state["ticker"], state["data_dir"])
    if cached:
        print(f"[bull] {state['ticker']} cache-hit (skipped Featherless call)")
    return {"agents": {"bull": result.model_dump(mode="json")}}


async def bear_node(state: State) -> dict:
    cached = _load_cached(state, "bear", BearCase)
    result = cached or await build_bear_case(state["ticker"], state["data_dir"])
    if cached:
        print(f"[bear] {state['ticker']} cache-hit (skipped Featherless call)")
    return {"agents": {"bear": result.model_dump(mode="json")}}


async def reconciler_node(state: State) -> dict:
    # Reconciler is the final write — also obeys reuse_cache for full
    # end-to-end re-runs against cached upstream output.
    out_path = state["data_dir"] / state["ticker"] / "reconciliation.json"
    if state.get("reuse_cache") and out_path.exists():
        result = Reconciliation.model_validate_json(out_path.read_text())
        print(f"[reconciler] {state['ticker']} cache-hit (skipped Gemini call)")
    else:
        result = await reconcile(state["ticker"], state["data_dir"])
    return {"agents": {"reconciliation": result.model_dump(mode="json")}}


def build_graph():
    """Compile and return the LangGraph runnable.

    Edges:
        START → filing
        START → call
        filing → bull
        call   → bull
        filing → bear
        call   → bear
        bull → reconciler
        bear → reconciler
        reconciler → END

    LangGraph treats multi-parent edges as an implicit join — a node only
    runs once all of its parents have produced their state update.
    """
    g = StateGraph(State)

    g.add_node("filing", filing_node)
    g.add_node("call", call_node)
    g.add_node("bull", bull_node)
    g.add_node("bear", bear_node)
    g.add_node("reconciler", reconciler_node)

    g.add_edge(START, "filing")
    g.add_edge(START, "call")
    g.add_edge("filing", "bull")
    g.add_edge("call", "bull")
    g.add_edge("filing", "bear")
    g.add_edge("call", "bear")
    g.add_edge("bull", "reconciler")
    g.add_edge("bear", "reconciler")
    g.add_edge("reconciler", END)

    return g.compile()


async def run_for_ticker(
    ticker: str,
    data_dir: Path = Path("data"),
    *,
    reuse_cache: bool = False,
) -> dict:
    """Execute the full graph end-to-end. Returns the final state dict."""
    graph = build_graph()
    initial: State = {
        "ticker": ticker,
        "data_dir": data_dir,
        "reuse_cache": reuse_cache,
        "agents": {},
    }
    return await graph.ainvoke(initial)
