/**
 * Footer — hackathon credit, source code, attribution. Renders as a server
 * component (no "use client"); the content is static and Next can stream it.
 */

const STACK_BADGES = [
  "Next.js 16",
  "FastAPI",
  "LangGraph",
  "Gemini 2.5 Pro",
  "Qwen3-32B",
  "Speechmatics",
  "Vultr",
];

export default function Footer() {
  return (
    <footer className="mt-8 border-t border-border/40 bg-background/80 px-6 py-10 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 md:flex-row md:items-start md:justify-between">
        <div className="max-w-md">
          <p className="font-display text-lg font-black tracking-wide">
            Diligence
          </p>
          <p className="mt-2 font-mono text-xs leading-relaxed text-foreground/55">
            Adversarial multi-agent due-diligence on public-company tickers.
            Built at <span className="text-amber-300">lablab.ai · Milan AI Week '26</span>.
            Not investment advice; cited claims are extracted from public
            filings and earnings audio for research purposes only.
          </p>
        </div>

        <div className="flex flex-col gap-4 font-mono text-xs">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-foreground/60">
            <a
              href="https://github.com/leonardtudor11/diligence"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground"
            >
              GitHub
            </a>
            <a
              href="https://github.com/leonardtudor11/diligence/blob/main/SECURITY.md"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground"
            >
              Security
            </a>
            <a
              href="https://github.com/leonardtudor11/diligence/blob/main/frontend/CREDITS.md"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground"
            >
              Credits
            </a>
            <a
              href="https://github.com/leonardtudor11/diligence/blob/main/HANDOFF.md"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground"
            >
              Roadmap
            </a>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {STACK_BADGES.map((label) => (
              <span
                key={label}
                className="rounded border border-border/40 bg-secondary/30 px-2 py-0.5 text-[10px] tracking-wider text-foreground/55"
              >
                {label}
              </span>
            ))}
          </div>

          <p className="text-[10px] tracking-wider text-foreground/35">
            Bull + bear silhouettes © Lorc / game-icons.net (CC BY 3.0). Brand
            marks © their respective owners.
          </p>
        </div>
      </div>
    </footer>
  );
}
