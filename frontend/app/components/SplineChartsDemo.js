"use client";

import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";

/**
 * "What you get back" — interactive Spline chart scene used as a teaser for
 * the dashboard view that ships on Day 3. Same SplineScene wrapper as the
 * robot card; only the splinecode URL differs. Scene is the CC0 "Charts with
 * interactive hover animation" published on Spline community.
 */
export default function SplineChartsDemo() {
  return (
    <section className="px-6 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl">
        <header className="mx-auto mb-10 max-w-2xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/50">
            What you get back
          </p>
          <h2 className="mt-3 font-display text-3xl font-black sm:text-5xl">
            Materiality, charted.
          </h2>
          <p className="mt-4 font-mono text-sm leading-relaxed text-foreground/70 sm:text-base">
            Every disputed fact lands on a 1–10 materiality scale. Hover any
            bar to see the bull and bear citations that drive the score.
          </p>
        </header>

        <Card className="relative h-[520px] w-full overflow-hidden bg-black/[0.96]">
          <Spotlight
            className="-top-20 left-10 md:-top-10 md:left-40"
            fill="#EF4444"
          />
          <div className="relative h-full w-full">
            <SplineScene
              scene="https://prod.spline.design/YjQh3czZPvLqnDAp/scene.splinecode"
              className="h-full w-full"
            />
          </div>
          <div className="pointer-events-none absolute bottom-4 right-4 z-20 hidden sm:block">
            <div className="rounded-md border border-border/40 bg-black/70 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.3em] text-foreground/70 backdrop-blur">
              <span className="text-accent">live</span>
              <span className="mx-2 text-foreground/30">·</span>
              <span>reconciler output preview</span>
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}
