"use client";

import CitedText from "./CitedText";

export default function DisputedFactCard({ fact, claimIndex }) {
  const score = fact.materiality_score;
  const scoreColor =
    score >= 8 ? "text-destructive" : score >= 5 ? "text-yellow-300" : "text-foreground/70";

  return (
    <div className="rounded-lg border border-border/40 bg-secondary/30 p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <h3 className="font-display text-lg font-bold leading-tight">
          {fact.topic}
        </h3>
        <div className="flex shrink-0 items-center gap-2">
          {fact.uncited_claims_flag && (
            <span
              title="At least one side cited a claim_id not present in Filing/Call analyst output"
              className="rounded border border-yellow-500/40 bg-yellow-500/10 px-1.5 py-0.5 font-mono text-[10px] text-yellow-300"
            >
              ⚠ uncited
            </span>
          )}
          <span className={`font-mono text-2xl font-black ${scoreColor}`}>
            {score}
            <span className="text-sm text-foreground/40">/10</span>
          </span>
        </div>
      </div>

      <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.25em] text-foreground/50">
        Why it matters
      </p>
      <p className="mb-5 font-mono text-sm leading-relaxed text-foreground/80">
        {fact.materiality_rationale}
      </p>

      <div className="space-y-4">
        <Side
          label="Bull"
          tone="bull"
          text={fact.bull_position}
          ids={fact.bull_claim_ids}
          claimIndex={claimIndex}
        />
        <Side
          label="Bear"
          tone="bear"
          text={fact.bear_position}
          ids={fact.bear_claim_ids}
          claimIndex={claimIndex}
        />
      </div>
    </div>
  );
}

function Side({ label, tone, text, ids, claimIndex }) {
  const isBull = tone === "bull";
  const border = isBull ? "border-accent/40" : "border-destructive/40";
  const chip = isBull ? "bg-accent/15 text-accent" : "bg-destructive/15 text-destructive";
  return (
    <div className={`rounded-md border ${border} bg-background/40 p-3`}>
      <div className="mb-2 flex items-center justify-between">
        <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.3em] ${chip}`}>
          {label}
        </span>
        <span className="font-mono text-[10px] text-foreground/40">
          {ids?.length ?? 0} citations
        </span>
      </div>
      <p className="font-mono text-[13px] leading-relaxed text-foreground/85">
        <CitedText text={text} claimIndex={claimIndex} tone={tone} />
      </p>
    </div>
  );
}
