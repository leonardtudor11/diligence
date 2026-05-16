"use client";

// Splits a sentence on inline citations like "(F-007)" / "(C-012)" and
// renders matched ids as hoverable chips. The text comes straight from
// Pillar.reasoning so we never invent new ids.

const CITE_RE = /\(([FC]-\d{3,4}(?:,\s*[FC]-\d{3,4})*)\)/g;

export default function CitedText({ text, claimIndex, tone }) {
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
        {ids.map((id, i) => {
          const claim = claimIndex[id];
          return (
            <span key={id}>
              <span
                title={claim ? claim.text : `Unknown claim ${id}`}
                className={`cursor-help underline decoration-dotted underline-offset-2 ${accent}`}
              >
                {id}
              </span>
              {i < ids.length - 1 ? ", " : ""}
            </span>
          );
        })}
        )
      </span>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(<span key="tail">{text.slice(last)}</span>);
  return <>{parts}</>;
}
