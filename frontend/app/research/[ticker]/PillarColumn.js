"use client";

import CitedText from "./CitedText";

export default function PillarColumn({
  tone,
  thesis,
  pillars,
  concessions,
  claimIndex,
  onClaimAction,
  filingSources,
  hasAudio,
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
                  <ClaimChip
                    key={id}
                    id={id}
                    claim={claimIndex[id]}
                    tone={tone}
                    onAction={onClaimAction}
                    filingSources={filingSources}
                    hasAudio={hasAudio}
                  />
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

function ClaimChip({ id, claim, tone, onAction, filingSources, hasAudio }) {
  const isUnverified = claim?.confidence === "unverified_audio";
  const isAccounting = !!claim?.accounting_flag;

  const baseColor =
    tone === "bull"
      ? "border-accent/30 bg-accent/10 text-accent"
      : "border-destructive/30 bg-destructive/10 text-destructive";
  // Yellow ring marks call claims sourced from unverified audio (the
  // confidence_downgrade_reason banner is the top-of-page summary; the
  // ring tells the judge WHICH specific cited claim is downgraded).
  // Amber ring marks filing claims with accounting_flag — the call-out
  // mirrors what the Filing Analyst surfaces in its analysis dump.
  const flagColor = isUnverified
    ? "ring-1 ring-yellow-400/55"
    : isAccounting
    ? "ring-1 ring-amber-300/55"
    : "";

  // Resolve whether this chip has somewhere to jump to. Call chips need
  // audio + a start_time; filing chips need a known SEC URL. Anything
  // else stays a passive tooltip span so unverifiable claims aren't
  // dressed up as interactive.
  const srcType = claim?.source?.type;
  let actionable = false;
  let actionLabel = null;
  if (
    srcType === "call" &&
    typeof claim?.source?.start_time === "number" &&
    hasAudio &&
    typeof onAction === "function"
  ) {
    actionable = true;
    actionLabel = `Jump to ${fmtClock(claim.source.start_time)} in transcript`;
  } else if (
    (srcType === "10-K" || srcType === "10-Q") &&
    filingSources?.[srcType]?.url &&
    typeof onAction === "function"
  ) {
    actionable = true;
    actionLabel = `Open ${srcType} on SEC.gov`;
  }

  const titleParts = [claim?.text || `Unknown claim ${id}`];
  if (actionLabel) titleParts.push(actionLabel);
  if (isUnverified) titleParts.push("⚠ Unverified audio — see confidence banner");
  if (isAccounting) titleParts.push("§ Flagged for accounting language");
  const title = titleParts.join("  ·  ");

  const excerpt = claim?.text ? truncate(claim.text, 40) : null;
  const cursorClass = actionable
    ? "cursor-pointer hover:brightness-110"
    : "cursor-help";
  const className = `group inline-flex max-w-full items-center gap-1.5 rounded border px-1.5 py-0.5 text-left font-mono text-[10px] ${baseColor} ${flagColor} ${cursorClass}`;

  const body = (
    <>
      {isUnverified ? (
        <span aria-label="unverified audio source" className="text-yellow-300">
          ⚠
        </span>
      ) : isAccounting ? (
        <span aria-label="accounting flag" className="text-amber-300">
          §
        </span>
      ) : null}
      <span className="font-semibold">{id}</span>
      {excerpt ? (
        <span className="hidden truncate text-foreground/70 sm:inline-block sm:max-w-[18ch]">
          {excerpt}
        </span>
      ) : null}
    </>
  );

  if (actionable) {
    return (
      <button
        type="button"
        title={title}
        aria-label={actionLabel}
        onClick={(e) => {
          e.stopPropagation();
          onAction(claim);
        }}
        className={className}
      >
        {body}
      </button>
    );
  }

  return (
    <span title={title} className={className}>
      {body}
    </span>
  );
}

function fmtClock(t) {
  if (!Number.isFinite(t)) return "0:00";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function truncate(s, n) {
  if (!s) return "";
  return s.length <= n ? s : s.slice(0, n - 1).trimEnd() + "…";
}
