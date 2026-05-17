"use client";

// Splits a sentence on inline citations like "(F-007)" / "(C-012)" and
// renders matched ids as hoverable chips. The text comes straight from
// Pillar.reasoning / DisputedFact.bull_position so we never invent new
// ids. When the parent supplies onClaimAction + the claim is resolvable
// to an actionable source (call audio or filing URL), the id is rendered
// as a real <button> that mirrors ClaimChip's behaviour. Otherwise it
// stays a hoverable <span title> — same as before this session.

const CITE_RE = /\(([FC]-\d{3,4}(?:,\s*[FC]-\d{3,4})*)\)/g;

export default function CitedText({
  text,
  claimIndex,
  tone,
  onClaimAction,
  filingSources,
  hasAudio,
}) {
  if (!text) return null;
  const accent =
    tone === "bull"
      ? "text-accent decoration-accent/40"
      : "text-destructive decoration-destructive/40";

  const parts = [];
  let last = 0;
  let m;
  let k = 0;
  while ((m = CITE_RE.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(<span key={`t${k++}`}>{text.slice(last, m.index)}</span>);
    }
    const ids = m[1].split(/,\s*/);
    parts.push(
      <span key={`c${k++}`} className="whitespace-nowrap">
        (
        {ids.map((id, i) => (
          <span key={id}>
            <Token
              id={id}
              claim={claimIndex[id]}
              accent={accent}
              onClaimAction={onClaimAction}
              filingSources={filingSources}
              hasAudio={hasAudio}
            />
            {i < ids.length - 1 ? ", " : ""}
          </span>
        ))}
        )
      </span>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(<span key="tail">{text.slice(last)}</span>);
  return <>{parts}</>;
}

function Token({ id, claim, accent, onClaimAction, filingSources, hasAudio }) {
  const srcType = claim?.source?.type;
  let actionable = false;
  let actionLabel = null;
  if (
    srcType === "call" &&
    typeof claim?.source?.start_time === "number" &&
    hasAudio &&
    typeof onClaimAction === "function"
  ) {
    actionable = true;
    actionLabel = `Jump to ${fmtClock(claim.source.start_time)} in transcript`;
  } else if (
    (srcType === "10-K" || srcType === "10-Q") &&
    filingSources?.[srcType]?.url &&
    typeof onClaimAction === "function"
  ) {
    actionable = true;
    actionLabel = `Open ${srcType} on SEC.gov`;
  }

  const titleParts = [claim ? claim.text : `Unknown claim ${id}`];
  if (actionLabel) titleParts.push(actionLabel);
  const title = titleParts.join("  ·  ");

  const baseClass = `underline decoration-dotted underline-offset-2 ${accent}`;

  if (actionable) {
    return (
      <button
        type="button"
        title={title}
        aria-label={actionLabel}
        onClick={(e) => {
          e.stopPropagation();
          onClaimAction(claim);
        }}
        className={`${baseClass} cursor-pointer rounded px-0.5 transition-colors hover:bg-accent/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent`}
      >
        {id}
      </button>
    );
  }

  return (
    <span title={title} className={`${baseClass} cursor-help`}>
      {id}
    </span>
  );
}

function fmtClock(t) {
  if (!Number.isFinite(t)) return "0:00";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
