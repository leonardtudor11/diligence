/**
 * SampleDisputedFact — one concrete row out of the ~15–20 the live reconciler
 * produces per ticker. Surrounded by plain-English explainers so a first-time
 * viewer can read the card without prior finance/agent-pipeline context.
 *
 * Once the agent backend is wired, this same component will accept a real
 * DisputedFact from `Reconciliation.disputed_facts[0]` as a prop. Today the
 * data is hard-coded NVDA Q4-FY26 gross-margin trajectory.
 */

const SAMPLE = {
  topic: "Q4 FY26 gross-margin trajectory",
  materiality_score: 8,
  bull_position:
    "ASP expansion on Blackwell + Hopper mix is sustainable through FY27. Pricing power compounds the operating-leverage tailwind into ~76% non-GAAP gross margin.",
  bull_claim_ids: ["F-014", "C-031"],
  bear_position:
    "Gross margin guided down sequentially in Q4 prepared remarks; CFO repeated ‘mix and yield’ language three times in Q&A — historically a leading indicator of inventory write-downs.",
  bear_claim_ids: ["F-017", "C-042", "C-056"],
  materiality_rationale:
    "Each 100 bps of gross margin = ~$0.40 of FY26 EPS. The bull and bear paths differ by ~400 bps over the next two quarters. Single-largest swing factor in the model.",
};

const GLOSSARY = [
  {
    term: "Disputed fact",
    body:
      "One specific topic where the bull case and the bear case argue opposite conclusions from the same primary sources.",
  },
  {
    term: "Claim IDs (F-014, C-031, …)",
    body:
      "F-### = filing claim from the 10-K/10-Q. C-### = call claim from the earnings-call transcript. Every position must cite real IDs; agents cannot invent facts.",
  },
  {
    term: "Materiality score 1–10",
    body:
      "How much this single disagreement moves the final answer. 1–3 cosmetic. 4–6 worth noting. 7–10 decision-altering. Higher ≠ buy or sell — just ‘matters more’.",
  },
];

const DASHBOARD_PREVIEW = [
  "All 15–20 disputed facts ranked",
  "Bull pillars · Disputed table · Bear pillars (3-column)",
  "Materiality bar chart — click any bar to scroll to the row",
  "Diarised call audio with click-to-jump transcript",
  "Click any claim ID to land in the source filing section",
];

function ScoreBar({ score }) {
  const segments = Array.from({ length: 10 }, (_, i) => i < score);
  return (
    <div className="flex items-center gap-2">
      <div
        className="flex gap-[3px]"
        title="1-3 cosmetic · 4-6 worth noting · 7-10 decision-altering"
        aria-label={`Materiality ${score} of 10 — higher means the disagreement moves the answer more`}
      >
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
            Nothing is invented. The reconciler scores how much the
            disagreement moves the answer.
          </p>
        </header>

        {/* 3-up glossary so a first-time reader has every term defined
            before they touch the card below. */}
        <div className="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {GLOSSARY.map((g) => (
            <div
              key={g.term}
              className="rounded-lg border border-border/40 bg-secondary/20 p-4"
            >
              <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-foreground/45">
                {g.term}
              </p>
              <p className="mt-2 font-mono text-xs leading-relaxed text-foreground/75">
                {g.body}
              </p>
            </div>
          ))}
        </div>

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
                    title="Filing or call claim ID — agents cite by these"
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
                    title="Filing or call claim ID — agents cite by these"
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

        <div className="mt-8 rounded-xl border border-border/40 bg-secondary/15 p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/50">
            On the full dashboard, you'd also see
          </p>
          <ul className="mt-3 grid grid-cols-1 gap-2 font-mono text-sm text-foreground/75 sm:grid-cols-2">
            {DASHBOARD_PREVIEW.map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span className="mt-1.5 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-accent/70" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="mx-auto mt-8 max-w-3xl text-center font-mono text-xs leading-relaxed text-foreground/50">
          <span className="text-amber-300">Research tool, not investment advice.</span>{" "}
          Diligence surfaces contested facts so an analyst can read the
          evidence faster. It does not say buy, sell, hold, long, or short.
          Every claim links back to the source filing section or transcript
          timestamp; the human decides.
        </p>
      </div>
    </section>
  );
}
