/**
 * SampleDisputedFact — concrete example of what one Reconciler output row
 * looks like. Until the live agents ship, this is hard-coded NVDA Q4 FY26
 * gross-margin trajectory data. After agents land, this same component will
 * render `Reconciliation.disputed_facts[0]` from the live API.
 *
 * Server component — no client interactivity in the static version.
 */

const SAMPLE = {
  topic: "Q4 FY26 gross-margin trajectory",
  materiality_score: 8,
  bull_position:
    "ASP expansion on Blackwell + Hopper mix is sustainable through FY27. Pricing power compounds the operating-leverage tailwind into ~76% non-GAAP gross margin. (F-014, C-031)",
  bull_claim_ids: ["F-014", "C-031"],
  bear_position:
    "Gross margin guided down sequentially in Q4 prepared remarks; CFO repeated 'mix and yield' language three times in Q&A — historically a leading indicator of inventory write-downs. (F-017, C-042, C-056)",
  bear_claim_ids: ["F-017", "C-042", "C-056"],
  materiality_rationale:
    "Each 100 bps of gross margin = ~$0.40 of FY26 EPS. The bull and bear paths differ by ~400 bps over the next two quarters. Single-largest swing factor in the model.",
};

function ScoreBar({ score }) {
  const segments = Array.from({ length: 10 }, (_, i) => i < score);
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-[3px]" aria-label={`materiality ${score} of 10`}>
        {segments.map((on, i) => (
          <span
            key={i}
            className={`h-2 w-3 rounded-sm ${
              on
                ? i < 4
                  ? "bg-foreground/50"
                  : i < 7
                  ? "bg-amber-400/80"
                  : "bg-accent"
                : "bg-secondary/60"
            }`}
          />
        ))}
      </div>
      <span className="font-display text-base font-black text-foreground">
        {score}
        <span className="text-foreground/40">/10</span>
      </span>
    </div>
  );
}

export default function SampleDisputedFact() {
  return (
    <section id="sample" className="px-6 py-16 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <header className="mx-auto mb-8 max-w-2xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/50">
            One row · NVDA · sample output
          </p>
          <h2 className="mt-3 font-display text-3xl font-black sm:text-4xl">
            What a disputed fact{" "}
            <span className="text-accent">actually</span> looks like.
          </h2>
          <p className="mt-3 font-mono text-sm leading-relaxed text-foreground/65 sm:text-base">
            Every row in the dashboard is one place the bull case and the bear
            case disagree. Both sides cite claim IDs the analysts extracted.
            Nothing is invented.
          </p>
        </header>

        <article className="overflow-hidden rounded-2xl border border-border/40 bg-secondary/20 backdrop-blur">
          <div className="flex flex-col gap-4 border-b border-border/30 bg-background/40 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/40">
                Topic
              </p>
              <p className="mt-1 font-display text-lg font-bold tracking-tight">
                {SAMPLE.topic}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/40">
                Materiality
              </p>
              <ScoreBar score={SAMPLE.materiality_score} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2">
            <div className="border-b border-border/30 bg-accent/[0.05] p-6 md:border-b-0 md:border-r">
              <div className="mb-3 flex items-center gap-2">
                <span className="inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
                <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-accent">
                  Bull position
                </p>
              </div>
              <p className="font-mono text-sm leading-relaxed text-foreground/85">
                {SAMPLE.bull_position}
              </p>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {SAMPLE.bull_claim_ids.map((id) => (
                  <span
                    key={id}
                    className="rounded border border-accent/40 bg-accent/10 px-2 py-0.5 font-mono text-[10px] text-accent"
                  >
                    {id}
                  </span>
                ))}
              </div>
            </div>

            <div className="bg-destructive/[0.05] p-6">
              <div className="mb-3 flex items-center gap-2">
                <span className="inline-flex h-1.5 w-1.5 rounded-full bg-destructive" />
                <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-destructive">
                  Bear position
                </p>
              </div>
              <p className="font-mono text-sm leading-relaxed text-foreground/85">
                {SAMPLE.bear_position}
              </p>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {SAMPLE.bear_claim_ids.map((id) => (
                  <span
                    key={id}
                    className="rounded border border-destructive/40 bg-destructive/10 px-2 py-0.5 font-mono text-[10px] text-destructive"
                  >
                    {id}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="border-t border-border/30 bg-background/60 px-6 py-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/40">
              Reconciler · materiality rationale
            </p>
            <p className="mt-2 font-mono text-sm leading-relaxed text-foreground/75">
              {SAMPLE.materiality_rationale}
            </p>
          </div>
        </article>

        <p className="mt-6 text-center font-mono text-[10px] uppercase tracking-[0.3em] text-foreground/35">
          Sample only · live agent output coming with day-3 backend
        </p>
      </div>
    </section>
  );
}
