import Link from "next/link";

export const metadata = {
  title: "How it works — Diligence",
  description:
    "Methodology: data sources, autonomous audio selection, five-agent adversarial pipeline, confidence bands.",
};

const PIPELINE = [
  {
    n: 1,
    name: "EDGAR",
    role: "Primary filings",
    detail:
      "Latest 10-K + 10-Q resolved via SEC's ticker→CIK index. Plain-text extraction via lxml. Filed dates and accession numbers carried through to the dashboard's Audit tab.",
  },
  {
    n: 2,
    name: "Financial Modeling Prep (free tier)",
    role: "Fundamentals",
    detail:
      "/stable/* endpoints: profile, ratios-TTM, key-metrics-TTM, income statement, balance sheet, cash flow. Last 4 reporting periods.",
  },
  {
    n: 3,
    name: "yt-dlp + autonomous selector",
    role: "Earnings-call audio",
    detail:
      "Probes up to 16 YouTube candidates across two queries ({ticker} + {issuer name}), scores each on duration / title positives / title negatives / uploader tier / recency-vs-target-date. Picks the highest above MIN_CANDIDATE_SCORE=50 or skips audio gracefully. Every candidate's score breakdown is captured in the manifest.",
  },
  {
    n: 4,
    name: "Speechmatics (batch + diarization)",
    role: "Transcript with speaker labels",
    detail:
      "json-v2 output: word-level start/end + per-word speaker tag. Diarization quality is audited — coverage <20% or 0 speakers hard-fails the transcript; <80% or single-speaker surfaces a manifest warning the dashboard shows.",
  },
];

const AGENTS = [
  {
    name: "Filing Analyst",
    model: "Gemini 2.5 Pro",
    role: "Extracts claim_ids F-001+ from 10-K + 10-Q. Structured output via Pydantic schema enforcement on Vertex.",
  },
  {
    name: "Call Analyst",
    model: "Gemini 2.5 Pro",
    role: "Extracts claim_ids C-001+ from the diarized transcript. Each claim links to a transcript timestamp via the speaker turn.",
  },
  {
    name: "Bull",
    model: "Qwen3-32B (Featherless)",
    role: "Builds the strongest possible bull case using ONLY claim_ids from Filing + Call. Uncited assertions are surfaced in the audit panel.",
  },
  {
    name: "Bear",
    model: "Qwen3-32B (Featherless)",
    role: "Same constraint, opposite direction. Bull + Bear run in parallel against the same evidence pool.",
  },
  {
    name: "Reconciler",
    model: "Gemini 2.5 Pro",
    role: "Diffs bull vs bear, materializes disputed facts ranked 1–10 by materiality, flags uncited claims, captures shared-ground items both sides agree on.",
  },
];

const TIERS = [
  { tier: "T1", label: "Verified primary", detail: "Uploader/channel matches the issuer name (token-level). Confidence: high." },
  { tier: "T2", label: "Trusted aggregator", detail: "Bloomberg, Reuters, WSJ, Morningstar, S&P Global. Confidence: high but provenance one degree removed." },
  { tier: "T3", label: "Editorial aggregator", detail: "Yahoo Finance, CNBC, Benzinga, Seeking Alpha, MarketWatch. Confidence: medium — may include host commentary. Dashboard renders the call audio with a confidence-downgrade banner." },
  { tier: "T4", label: "Unverified", detail: "Channel can't be matched to the issuer or to any trusted aggregator allowlist. Confidence: low. Dashboard surfaces a confidence-downgrade banner explicitly stating the call claims are sourced from unverified audio." },
];

function Section({ title, eyebrow, children }) {
  return (
    <section className="mt-12">
      {eyebrow ? (
        <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/40">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
        {title}
      </h2>
      <div className="mt-5 space-y-4 font-mono text-sm text-foreground/80">
        {children}
      </div>
    </section>
  );
}

export default function MethodologyPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-6 py-16">
      <Link
        href="/"
        className="font-mono text-xs uppercase tracking-[0.3em] text-foreground/50 hover:text-foreground"
      >
        ← diligence
      </Link>

      <h1 className="mt-6 font-display text-4xl font-black tracking-tight sm:text-5xl">
        How it works
      </h1>
      <p className="mt-3 font-mono text-sm text-foreground/65">
        Diligence is a multi-agent pipeline that turns three primary sources
        (filings, fundamentals, earnings-call audio) into a materiality-ranked
        set of disputed facts. Every claim cites a primary-source ID. Every
        source has a tier band the dashboard renders inline.
      </p>

      <Section title="Pipeline" eyebrow="Data flow">
        <ol className="space-y-4">
          {PIPELINE.map((p) => (
            <li
              key={p.n}
              className="rounded-md border border-border/40 bg-secondary/20 p-4"
            >
              <div className="flex items-baseline justify-between">
                <p className="font-display text-lg font-bold tracking-wide">
                  <span className="text-accent">{p.n}.</span> {p.name}
                </p>
                <p className="text-[11px] uppercase tracking-[0.25em] text-foreground/45">
                  {p.role}
                </p>
              </div>
              <p className="mt-2 text-foreground/75">{p.detail}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Five adversarial agents" eyebrow="Reasoning layer">
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {AGENTS.map((a) => (
            <li
              key={a.name}
              className="rounded-md border border-border/40 bg-secondary/20 p-4"
            >
              <p className="font-display text-base font-bold tracking-wide">
                {a.name}
              </p>
              <p className="mt-1 text-[11px] uppercase tracking-[0.25em] text-foreground/45">
                {a.model}
              </p>
              <p className="mt-2 text-foreground/75">{a.role}</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-foreground/60">
          Orchestrated by LangGraph. Filing + Call run in parallel; their output
          feeds Bull + Bear in parallel; Reconciler waits for both. Each agent
          short-circuits on a cache file so re-runs cost zero credits when the
          upstream output is unchanged.
        </p>
      </Section>

      <Section title="Audio-source tiers" eyebrow="Provenance">
        <ul className="space-y-3">
          {TIERS.map((t) => (
            <li
              key={t.tier}
              className="flex flex-col gap-2 rounded-md border border-border/40 bg-secondary/20 p-4 sm:flex-row sm:items-baseline"
            >
              <p className="font-mono text-xs font-bold uppercase tracking-[0.3em] text-accent sm:w-12">
                {t.tier}
              </p>
              <p className="font-display text-sm font-bold tracking-wide sm:w-44">
                {t.label}
              </p>
              <p className="text-foreground/75">{t.detail}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Confidence bands" eyebrow="What you see">
        <p>
          Every dashboard renders the active tier inline with the transcript
          player. When the picked audio is T3 or T4, the reconciler appends a
          <span className="text-yellow-300/90"> confidence_downgrade_reason</span>{" "}
          banner stating that call-derived claims are sourced from an
          aggregator or unverified channel. When no audio cleared the
          threshold, the pipeline runs filing-only and the banner explicitly
          says so.
        </p>
        <p>
          The Audit tab lists every yt-dlp candidate the selector saw, with the
          winner highlighted. Open it once if the tier ever surprises you.
        </p>
      </Section>

      <Section title="Limits + honesty" eyebrow="Known constraints">
        <ul className="list-disc space-y-2 pl-6 text-foreground/75">
          <li>
            FMP free tier covers ~5 years of historical financials. Long-horizon
            multi-decade trends are not in scope.
          </li>
          <li>
            yt-dlp is a hackathon-grade audio source. Production would swap to
            Quartr / Otter / direct IR-page scraping.
          </li>
          <li>
            Some companies don't have an official YouTube channel for earnings
            calls (e.g. Alphabet uses Google's channel, AMD posts on the IR
            page). The selector falls back through editorial aggregators or
            skips audio cleanly with a transparent banner.
          </li>
          <li>
            Research-grade output — Diligence flags disagreements. It does not
            issue buy / sell / hold recommendations.
          </li>
        </ul>
      </Section>

      <p className="mt-12 font-mono text-xs text-foreground/45">
        Source code:{" "}
        <a
          href="https://github.com/leonardtudor11/diligence"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline-offset-4 hover:underline"
        >
          github.com/leonardtudor11/diligence
        </a>
      </p>
    </main>
  );
}
