"use client";

import CitedText from "./CitedText";

export default function PillarColumn({
  tone,
  thesis,
  pillars,
  concessions,
  claimIndex,
}) {
  const isBull = tone === "bull";
  const accent = isBull ? "text-accent border-accent/40 bg-accent/5" : "text-destructive border-destructive/40 bg-destructive/5";
  const chipBg = isBull ? "bg-accent/15 text-accent" : "bg-destructive/15 text-destructive";

  return (
    <div className={`rounded-lg border ${accent} p-5`}>
      <div className="mb-3 flex items-center gap-3">
        <span className={`rounded-md px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.3em] ${chipBg}`}>
          {isBull ? "Bull" : "Bear"}
        </span>
        <span className="font-mono text-xs text-foreground/50">
          {pillars.length} {pillars.length === 1 ? "pillar" : "pillars"}
        </span>
      </div>

      {thesis && (
        <p className="mb-5 font-display text-base font-bold leading-snug text-foreground">
          {thesis}
        </p>
      )}

      <ol className="space-y-4">
        {pillars.map((p, i) => (
          <li key={i} className="rounded-md border border-border/30 bg-background/40 p-3">
            <p className="font-display text-sm font-bold text-foreground/95">
              {i + 1}. {p.headline}
            </p>
            <p className="mt-2 font-mono text-[13px] leading-relaxed text-foreground/75">
              <CitedText text={p.reasoning} claimIndex={claimIndex} tone={tone} />
            </p>
            {p.cited_claim_ids?.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {p.cited_claim_ids.map((id) => (
                  <ClaimChip key={id} id={id} claim={claimIndex[id]} tone={tone} />
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>

      {concessions?.length > 0 && (
        <div className="mt-5 border-t border-border/30 pt-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-foreground/45">
            Concedes
          </p>
          <ul className="mt-2 space-y-1.5 font-mono text-[12px] text-foreground/65">
            {concessions.map((c, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-foreground/30">▸</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ClaimChip({ id, claim, tone }) {
  const color =
    tone === "bull"
      ? "border-accent/30 bg-accent/10 text-accent"
      : "border-destructive/30 bg-destructive/10 text-destructive";
  const title = claim?.text || `Unknown claim ${id}`;
  return (
    <span
      title={title}
      className={`cursor-help rounded border px-1.5 py-0.5 font-mono text-[10px] ${color}`}
    >
      {id}
    </span>
  );
}
