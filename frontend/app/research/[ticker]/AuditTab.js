"use client";

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
          {filingSources && Object.entries(filingSources).map(([form, src]) =>
            src?.url ? (
              <li key={form} className="text-foreground/80">
                <a
                  href={src.url}
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
            ) : null
          )}
        </Block>

        <Block title="Pipeline warnings" empty="Pipeline ran clean — no manifest warnings.">
          {manifestWarnings.map((w, i) => (
            <li key={i} className="text-yellow-300">⚠ {w}</li>
          ))}
        </Block>
      </div>

      {candidates.length > 0 ? (
        <details className="mt-5" open={false}>
          <summary className="cursor-pointer font-mono text-xs uppercase tracking-[0.3em] text-foreground/55">
            Audio candidates considered ({candidates.length})
            {audioSource?.queries?.length ? (
              <span className="ml-2 normal-case tracking-normal text-foreground/40">
                queries: {audioSource.queries.join(" · ")}
              </span>
            ) : null}
          </summary>
          <table className="mt-3 w-full border-separate border-spacing-y-1 font-mono text-xs">
            <thead>
              <tr className="text-left text-foreground/45">
                <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Score</th>
                <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Tier</th>
                <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Uploader</th>
                <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Title</th>
                <th className="px-2 py-1 font-medium uppercase tracking-[0.2em]">Upload</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => {
                const isWinner =
                  audioSource?.url && c.url && audioSource.url === c.url;
                return (
                  <tr
                    key={i}
                    className={
                      isWinner
                        ? "bg-accent/10 text-foreground"
                        : "text-foreground/75 hover:bg-background/30"
                    }
                  >
                    <td className="px-2 py-1 font-semibold">{c.score}</td>
                    <td className="px-2 py-1 text-foreground/60">
                      {c.tier ? c.tier.split("_")[0] : "—"}
                    </td>
                    <td className="px-2 py-1">{c.uploader || "—"}</td>
                    <td className="px-2 py-1 truncate max-w-[24rem]" title={c.title}>
                      {c.url ? (
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-accent"
                        >
                          {c.title || c.url}
                        </a>
                      ) : (
                        c.title || "—"
                      )}
                    </td>
                    <td className="px-2 py-1 text-foreground/55">
                      {c.upload_date || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </details>
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
