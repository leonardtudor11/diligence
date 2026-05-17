"use client";

import { TIER_BADGE } from "./TranscriptPlayer";

// Reject any non-http(s) URL before rendering as an <a href>. A
// poisoned candidate URL with a `javascript:` scheme is otherwise an
// active XSS sink, target="_blank" notwithstanding.
function safeHref(url) {
  if (typeof url !== "string") return null;
  if (!/^https?:\/\//i.test(url)) return null;
  return url;
}

// Format yt-dlp's YYYYMMDD upload_date as YYYY-MM-DD for visual
// consistency with the rest of the dashboard (SEC filing dates).
function fmtUploadDate(d) {
  if (typeof d !== "string" || d.length !== 8) return d || "—";
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
}

export default function AuditTab({
  warnings,
  shared,
  filingInjected,
  callInjected,
  filingSources,
  audioSource,
  manifestWarnings = [],
}) {
  const candidates = audioSource?.candidates_considered || [];

  return (
    <section className="mb-6 rounded-lg border border-border/50 bg-secondary/30 p-5">
      <h2 className="font-display text-lg font-bold tracking-wide">Audit</h2>
      <p className="mt-1 font-mono text-xs text-foreground/55">
        Provenance + integrity signals from the pipeline and the reconciler.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Block title="Integrity warnings" empty="No warnings — every cited claim_id resolved.">
          {warnings.map((w, i) => (
            <li key={i} className="text-destructive">
              ⚠ {w}
            </li>
          ))}
        </Block>

        <Block title="Prompt-injection probes" empty="Clean.">
          {filingInjected && (
            <li className="text-yellow-300">Filing Analyst flagged injection inside &lt;filing&gt; tags.</li>
          )}
          {callInjected && (
            <li className="text-yellow-300">Call Analyst flagged injection inside &lt;transcript&gt; tags.</li>
          )}
        </Block>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Block title="SEC filings (primary source)" empty="No filing provenance in manifest.">
          {filingSources && Object.entries(filingSources).map(([form, src]) => {
            const href = safeHref(src?.url);
            return href ? (
              <li key={form} className="text-foreground/80">
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  {form} · filed {src.filed}
                </a>
                {src.accession ? (
                  <span className="ml-2 text-foreground/40">{src.accession}</span>
                ) : null}
              </li>
            ) : null;
          })}
        </Block>

        <Block title="Pipeline warnings" empty="Pipeline ran clean — no manifest warnings.">
          {manifestWarnings.map((w, i) => (
            <li key={i} className="text-yellow-300">⚠ {w}</li>
          ))}
        </Block>
      </div>

      {candidates.length > 0 ? (
        <CandidatesPanel candidates={candidates} audioSource={audioSource} />
      ) : null}

      {shared?.length > 0 && (
        <details className="mt-5">
          <summary className="cursor-pointer font-mono text-xs uppercase tracking-[0.3em] text-foreground/55">
            Shared ground ({shared.length})
          </summary>
          <ul className="mt-3 space-y-1.5 font-mono text-sm text-foreground/75">
            {shared.map((s, i) => (
              <li key={i}>▸ {s}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function CandidatesPanel({ candidates, audioSource }) {
  const winnerUrl = audioSource?.url;
  const winnerBadge = audioSource?.tier ? TIER_BADGE[audioSource.tier] : null;
  // Bar width is relative to the highest score in the list, so the
  // winner's bar fills the column and runners-up shrink in proportion.
  // `max(1, …)` guards a degenerate top-of-list-is-zero edge.
  const maxScore = Math.max(1, ...candidates.map((c) => c.score || 0));

  return (
    <details className="mt-5" open={true}>
      <summary className="cursor-pointer font-mono text-xs uppercase tracking-[0.3em] text-foreground/55">
        Audio candidates
        <span className="ml-2 normal-case tracking-normal text-foreground/70">
          picked{" "}
          {winnerBadge ? (
            <span className={`mx-1 rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wider ${winnerBadge.accent}`}>
              {winnerBadge.short} · {winnerBadge.text}
            </span>
          ) : null}
          score{" "}
          <span className="font-semibold text-foreground">
            {audioSource?.score ?? "—"}
          </span>{" "}
          over {Math.max(0, candidates.length - 1)} alternative
          {candidates.length === 2 ? "" : "s"}
        </span>
        {audioSource?.queries?.length ? (
          <span className="ml-2 normal-case tracking-normal text-foreground/40">
            queries: {audioSource.queries.join(" · ")}
          </span>
        ) : null}
      </summary>

      {/* Horizontal scroll on narrow screens so the 5-column table stays
          legible on mobile rather than collapsing into a wall of stacked
          text. Minimum width preserves column intent. */}
      <div className="mt-3 -mx-1 overflow-x-auto">
        <table className="w-full min-w-[600px] border-separate border-spacing-y-1 font-mono text-xs">
          <thead>
            <tr className="text-left text-foreground/45">
              <th className="px-2 py-1 font-medium uppercase tracking-[0.2em] w-[110px]">Score</th>
              <th className="px-2 py-1 font-medium uppercase tracking-[0.2em] w-[140px]">Tier</th>
              <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Uploader</th>
              <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Title</th>
              <th className="px-2 py-1 font-medium uppercase tracking-[0.2em] w-[110px]">Upload</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c, i) => {
              const isWinner = winnerUrl && c.url && winnerUrl === c.url;
              const badge = c.tier ? TIER_BADGE[c.tier] : null;
              const pct = Math.max(2, Math.min(100, ((c.score || 0) / maxScore) * 100));
              const href = safeHref(c.url);
              return (
                <tr
                  key={i}
                  className={
                    isWinner
                      ? "bg-accent/10 text-foreground"
                      : "text-foreground/75 hover:bg-background/30"
                  }
                >
                  <td className="px-2 py-1 align-middle">
                    <div className="flex items-center gap-2">
                      <span className="w-7 shrink-0 text-right font-semibold">
                        {c.score ?? "—"}
                      </span>
                      <div className="h-1.5 w-16 overflow-hidden rounded bg-foreground/10">
                        <div
                          className={`h-full ${isWinner ? "bg-accent" : "bg-foreground/40"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-1 align-middle">
                    {badge ? (
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wider ${badge.accent}`}>
                        {badge.short} · {badge.text}
                      </span>
                    ) : (
                      <span className="text-foreground/45">—</span>
                    )}
                  </td>
                  <td className="px-2 py-1 align-middle">
                    {isWinner ? (
                      <span className="mr-1 text-accent" aria-label="winner">✓</span>
                    ) : null}
                    {c.uploader || "—"}
                  </td>
                  <td className="px-2 py-1 truncate max-w-[24rem] align-middle" title={c.title}>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-accent"
                      >
                        {c.title || href}
                      </a>
                    ) : (
                      c.title || "—"
                    )}
                  </td>
                  <td className="px-2 py-1 text-foreground/55 align-middle">
                    {fmtUploadDate(c.upload_date)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Block({ title, children, empty }) {
  const items = Array.isArray(children) ? children : children ? [children] : [];
  const has = items.some(Boolean);
  return (
    <div className="rounded-md border border-border/40 bg-background/40 p-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-foreground/55">
        {title}
      </p>
      {has ? (
        <ul className="mt-2 space-y-1.5 font-mono text-sm">{items}</ul>
      ) : (
        <p className="mt-2 font-mono text-sm text-foreground/45">{empty}</p>
      )}
    </div>
  );
}
