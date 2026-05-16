"use client";

import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";

/**
 * "How it works" section. Three-step pipeline on the left tells the user
 * what actually happens between ticker entry and the materiality chart on
 * the right; the Spline robot on the right is decorative — it stands in for
 * "the agent doing the work" while we still load the real backend.
 *
 * The 3-step copy now carries the substance that the Hero subtitle only
 * gestures at. Each step's numbered chip uses the brand accent so the eye
 * walks down 01 → 02 → 03 without effort.
 */

const STEPS = [
  {
    n: "01",
    title: "Cache the sources",
    body:
      "10-K + 10-Q from SEC EDGAR. Earnings call audio via yt-dlp. Speechmatics transcribes with speaker diarization. Everything saved locally so the agents read the same evidence on every run.",
  },
  {
    n: "02",
    title: "Five agents debate",
    body:
      "Filing analyst and call analyst extract atomic claims with citations. Bull and Bear build opposing investment cases on top, citing only those claim IDs. The reconciler diffs them.",
  },
  {
    n: "03",
    title: "See what's disputed",
    body:
      "Every disagreement is ranked 1–10 by materiality. Each side's argument links back to the filing section or transcript timestamp. No invented facts, no unsourced claims.",
  },
];

export default function SplineSceneDemo() {
  return (
    <section className="px-6 py-16 sm:py-20">
      <div className="mx-auto max-w-7xl">
        <Card className="relative w-full overflow-hidden bg-black/[0.96]">
          <Spotlight
            className="-top-40 left-0 md:-top-20 md:left-60"
            fill="#22C55E"
          />

          <div className="flex flex-col md:flex-row">
            <div className="relative z-10 flex flex-1 flex-col justify-center gap-6 p-8 sm:p-12">
              <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/50">
                How it works
              </p>
              <h2 className="bg-gradient-to-b from-neutral-50 to-neutral-400 bg-clip-text font-display text-3xl font-black text-transparent sm:text-4xl">
                One ticker in.
                <br />
                Cited disagreements out.
              </h2>

              <ol className="mt-2 space-y-5">
                {STEPS.map((s) => (
                  <li key={s.n} className="flex gap-4">
                    <span className="shrink-0 font-display text-2xl font-black leading-none text-accent">
                      {s.n}
                    </span>
                    <div>
                      <p className="font-display text-base font-bold tracking-wide text-neutral-100">
                        {s.title}
                      </p>
                      <p className="mt-1 max-w-md font-mono text-sm leading-relaxed text-neutral-400">
                        {s.body}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <div className="relative min-h-[420px] flex-1 md:min-h-[520px]">
              <SplineScene
                scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
                className="h-full w-full"
              />
            </div>
          </div>

          {/* lablab.ai hackathon badge — DOM overlay on the chassis since the
              Spline scene itself cannot be re-textured without re-uploading
              from the Spline editor. */}
          <div className="pointer-events-none absolute bottom-4 right-4 z-20 hidden sm:block">
            <div className="rounded-md border border-amber-400/40 bg-black/70 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.3em] text-amber-300/90 shadow-[inset_0_0_0_1px_rgba(252,211,77,0.08)] backdrop-blur">
              <span className="text-amber-200">lablab.ai</span>
              <span className="mx-2 text-amber-300/40">·</span>
              <span>Milan AI Week ’26</span>
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}
