/**
 * Footer — hackathon credit, source code, attribution. Renders as a server
 * component (no "use client"); the content is static and Next can stream it.
 *
 * Layout: two equal-feeling columns at md+. Left = disclaimer paragraph.
 * Right = links + tech-stack badges + attribution. Both columns center
 * vertically and the right column right-aligns its content so the link row
 * lines up with the page's right edge instead of floating mid-air.
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

const FOOTER_LINKS = [
  { label: "GitHub", href: "https://github.com/leonardtudor11/diligence" },
  {
    label: "Security",
    href: "https://github.com/leonardtudor11/diligence/blob/main/SECURITY.md",
  },
  {
    label: "Credits",
    href: "https://github.com/leonardtudor11/diligence/blob/main/frontend/CREDITS.md",
  },
  {
    label: "Roadmap",
    href: "https://github.com/leonardtudor11/diligence/blob/main/HANDOFF.md",
  },
  {
    label: "License",
    href: "https://github.com/leonardtudor11/diligence/blob/main/LICENSE",
  },
];

export default function Footer() {
  return (
    <footer className="mt-8 border-t border-border/40 bg-background/80 px-6 py-10 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-10 md:flex-row md:items-center md:justify-between">
        {/* Left — brand + disclaimer */}
        <div className="max-w-md">
          <p className="font-display text-lg font-black tracking-wide">
            Diligence
          </p>
          <p className="mt-2 font-mono text-sm leading-relaxed text-foreground/60">
            Adversarial multi-agent due-diligence on public-company tickers.
            Built at{" "}
            <span className="text-amber-300">
              lablab.ai · Milan AI Week '26
            </span>
            . Not investment advice; cited claims are extracted from public
            filings and earnings audio for research purposes only.
          </p>
        </div>

        {/* Right — links + badges + attribution */}
        <div className="flex flex-col gap-4 font-mono text-sm md:items-end md:text-right">
          <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 text-foreground/70 md:justify-end">
            {FOOTER_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="transition-colors duration-150 hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="flex flex-wrap items-center gap-2 md:justify-end">
            {STACK_BADGES.map((label) => (
              <span
                key={label}
                className="rounded border border-border/40 bg-secondary/30 px-2.5 py-1 text-xs tracking-wider text-foreground/65"
              >
                {label}
              </span>
            ))}
          </div>

          <p className="text-xs leading-relaxed text-foreground/40">
            Bull + bear silhouettes © Lorc / game-icons.net (CC BY 3.0).
            <br className="hidden md:inline" /> Brand marks © their respective
            owners.
          </p>
        </div>
      </div>
    </footer>
  );
}
