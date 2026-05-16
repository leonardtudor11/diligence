"use client";

import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";

/**
 * Spline 3D hero section. Re-themed from the 21st.dev "SplineSceneBasic"
 * pattern: left half holds the Diligence value-prop copy, right half hosts a
 * Spline interactive robot scene that signals "AI / agentic" intent. Spotlight
 * sweeps the top of the card. Heavy assets (Spline runtime) load only on the
 * client via the SplineScene Suspense boundary.
 */
export default function SplineSceneDemo() {
  return (
    <section className="px-6 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl">
        <Card className="relative h-[500px] w-full overflow-hidden bg-black/[0.96]">
          <Spotlight
            className="-top-40 left-0 md:-top-20 md:left-60"
            fill="#22C55E"
          />

          <div className="flex h-full flex-col md:flex-row">
            <div className="relative z-10 flex flex-1 flex-col justify-center p-8 sm:p-12">
              <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/50">
                Agent layer
              </p>
              <h2 className="mt-3 bg-gradient-to-b from-neutral-50 to-neutral-400 bg-clip-text font-display text-4xl font-black text-transparent md:text-5xl">
                Five agents.
                <br />
                One ticker.
              </h2>
              <p className="mt-4 max-w-lg font-mono text-sm leading-relaxed text-neutral-300 sm:text-base">
                Filing analyst, call analyst, bull, bear, and reconciler. Each
                reads the same evidence and writes its own verdict. The
                disputed facts are what you actually look at.
              </p>
            </div>

            <div className="relative flex-1">
              <SplineScene
                scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
                className="h-full w-full"
              />
            </div>
          </div>

          {/* lablab.ai hackathon badge — sits over the lower-right corner of
              the card like a stamped brass plaque on a chassis. Cannot edit
              the Spline scene itself without re-uploading from the editor,
              so the marker is rendered as a DOM overlay instead. */}
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
