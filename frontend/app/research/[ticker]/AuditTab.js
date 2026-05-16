"use client";

export default function AuditTab({ warnings, shared, filingInjected, callInjected }) {
  return (
    <section className="mb-6 rounded-lg border border-border/50 bg-secondary/30 p-5">
      <h2 className="font-display text-lg font-bold tracking-wide">Audit</h2>
      <p className="mt-1 font-mono text-xs text-foreground/55">
        Provenance + integrity signals from the reconciler.
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
