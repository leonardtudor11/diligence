"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import DisputedFactsChart from "./DisputedFactsChart";
import PillarColumn from "./PillarColumn";
import DisputedFactCard from "./DisputedFactCard";
import TranscriptPlayer from "./TranscriptPlayer";
import AuditTab from "./AuditTab";

export default function Dashboard({ ticker, payload }) {
  const { agents, transcript_words: words = [], has_audio, manifest } = payload;
  const reconciliation = agents.reconciliation;
  const bull = agents.bull;
  const bear = agents.bear;
  const filing = agents.filing;
  const call = agents.call;
  const audioSource = manifest?.sources?.audio || null;
  const filingSources = {
    "10-K": manifest?.sources?.["10k"] || null,
    "10-Q": manifest?.sources?.["10q"] || null,
  };
  const manifestWarnings = manifest?.warnings || [];

  const [activeFactIdx, setActiveFactIdx] = useState(0);
  const [showAudit, setShowAudit] = useState(false);

  // Build claim_id → Claim index for the disputed-fact card to render
  // citations inline without re-scanning every render.
  const claimIndex = useMemo(() => {
    const out = {};
    for (const c of filing?.claims ?? []) out[c.claim_id] = c;
    for (const c of call?.claims ?? []) out[c.claim_id] = c;
    return out;
  }, [filing, call]);

  const disputed = reconciliation?.disputed_facts ?? [];
  const activeFact = disputed[activeFactIdx];

  return (
    <main className="flex flex-1 flex-col px-6 py-10 sm:px-10">
      {/* Top bar — grid keeps title and badges on dedicated rows so the
          header never overflows or wraps unpredictably between desktop
          and mobile. */}
      <header className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <Link
            href="/"
            className="font-mono text-xs uppercase tracking-[0.3em] text-foreground/50 hover:text-foreground"
          >
            ← diligence
          </Link>
          <h1 className="mt-2 font-display text-3xl font-black tracking-tight sm:text-4xl">
            {ticker}{" "}
            <span className="text-foreground/40">— adversarial dossier</span>
          </h1>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap sm:items-center sm:gap-3 sm:justify-end">
          <Badge label="Filing" value={filing?.claims?.length ?? 0} />
          <Badge label="Call" value={call?.claims?.length ?? 0} />
          <Badge label="Disputed" value={disputed.length} accent />
          {reconciliation?.integrity_warnings?.length > 0 && (
            <button
              onClick={() => setShowAudit((v) => !v)}
              className="col-span-3 rounded-md border border-destructive/60 bg-destructive/10 px-3 py-1.5 font-mono text-xs text-destructive hover:bg-destructive/20 sm:col-span-1"
            >
              {reconciliation.integrity_warnings.length} audit ⚠
            </button>
          )}
          <button
            onClick={() => setShowAudit((v) => !v)}
            className="col-span-3 rounded-md border border-border/60 bg-secondary/40 px-3 py-1.5 font-mono text-xs text-foreground/80 hover:bg-secondary/60 sm:col-span-1"
          >
            Audit
          </button>
        </div>
      </header>

      {/* Confidence-downgrade banner */}
      {reconciliation?.confidence_downgrade_reason && (
        <div className="mb-6 rounded-md border border-yellow-500/50 bg-yellow-500/10 px-4 py-3">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-yellow-200">
            Confidence downgrade
          </p>
          <p className="mt-1 font-mono text-sm text-yellow-100">
            {reconciliation.confidence_downgrade_reason}
          </p>
        </div>
      )}

      {/* Audit panel (collapsible) */}
      {showAudit && (
        <AuditTab
          warnings={reconciliation?.integrity_warnings ?? []}
          shared={reconciliation?.shared_ground ?? []}
          filingInjected={filing?.injection_detected}
          callInjected={call?.injection_detected}
          filingSources={filingSources}
          audioSource={audioSource}
          manifestWarnings={manifestWarnings}
        />
      )}

      {/* Materiality chart */}
      <section className="mb-8 rounded-lg border border-border/40 bg-secondary/20 p-5">
        <h2 className="mb-1 font-display text-lg font-bold tracking-wide">
          Disputed facts, ranked by materiality
        </h2>
        <p className="mb-4 font-mono text-xs text-foreground/50">
          Click a bar to focus that disagreement.
        </p>
        <DisputedFactsChart
          facts={disputed}
          activeIdx={activeFactIdx}
          onPick={setActiveFactIdx}
        />
      </section>

      {/* 3-column: bull / disputed-focus / bear */}
      <section className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.2fr_1fr]">
        <PillarColumn
          tone="bull"
          ticker={ticker}
          thesis={bull?.thesis}
          pillars={bull?.pillars ?? []}
          concessions={bull?.counter_arguments_acknowledged ?? []}
          claimIndex={claimIndex}
        />

        <div>
          {activeFact ? (
            <DisputedFactCard fact={activeFact} claimIndex={claimIndex} />
          ) : (
            <div className="rounded-lg border border-border/40 bg-secondary/20 p-5">
              <p className="font-mono text-sm text-foreground/60">
                No disputed facts produced for this ticker.
              </p>
            </div>
          )}

          {/* Shared ground — under the focused fact */}
          {(reconciliation?.shared_ground ?? []).length > 0 && (
            <div className="mt-5 rounded-lg border border-accent/30 bg-accent/5 p-5">
              <h3 className="font-display text-sm font-bold uppercase tracking-[0.3em] text-accent">
                Both sides agree
              </h3>
              <ul className="mt-3 space-y-2 font-mono text-sm text-foreground/85">
                {(reconciliation?.shared_ground ?? []).map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-accent">▸</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <PillarColumn
          tone="bear"
          ticker={ticker}
          thesis={bear?.thesis}
          pillars={bear?.pillars ?? []}
          concessions={bear?.counter_arguments_acknowledged ?? []}
          claimIndex={claimIndex}
        />
      </section>

      {/* Transcript player */}
      <section className="mt-10 rounded-lg border border-border/40 bg-secondary/20 p-5">
        <h2 className="mb-2 font-display text-lg font-bold tracking-wide">
          Earnings call — click any word to jump to that moment
        </h2>
        <p className="mb-4 font-mono text-xs text-foreground/50">
          Speaker labels come from Speechmatics diarisation. Call claims are
          flagged <span className="text-yellow-300/90">unverified_audio</span>{" "}
          until an authoritative source is wired in.
        </p>
        {has_audio ? (
          <TranscriptPlayer ticker={ticker} words={words} audioSource={audioSource} />
        ) : (
          <p className="font-mono text-sm text-foreground/50">No audio cached.</p>
        )}
      </section>

      <Link
        href="/"
        className="mt-12 inline-block font-mono text-xs uppercase tracking-[0.3em] text-foreground/50 hover:text-foreground"
      >
        ← back home
      </Link>
    </main>
  );
}

function Badge({ label, value, accent }) {
  return (
    <div
      className={`flex items-baseline gap-2 rounded-md border px-3 py-1.5 font-mono text-xs ${
        accent
          ? "border-accent/40 bg-accent/10 text-accent"
          : "border-border/60 bg-secondary/30 text-foreground/80"
      }`}
    >
      <span className="uppercase tracking-[0.2em] opacity-70">{label}</span>
      <span className="text-sm font-bold">{value}</span>
    </div>
  );
}
