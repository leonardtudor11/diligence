"use client";

import { useEffect, useRef, useState } from "react";
import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";

/**
 * "What you get back" — Spline charts teaser. The dashboard graph adopts
 * this scene's emerald/magenta palette so the visual identity carries
 * from landing to dossier.
 *
 * The scene is lazy-mounted via IntersectionObserver: WebGL on Spline is
 * expensive (GL_CLOSE_PATH_NV / ReadPixels stalls visible in console) and
 * we already paid that cost on the hero robot scene at the top of the
 * page. Mounting this second scene only when the user actually scrolls
 * to it keeps the landing-page first paint cheap.
 */
export default function SplineChartsDemo() {
  const ref = useRef(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (!ref.current || active) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setActive(true);
            io.disconnect();
            break;
          }
        }
      },
      { rootMargin: "200px 0px" }
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [active]);

  return (
    <section ref={ref} className="px-6 py-16 sm:py-20">
      <div className="mx-auto max-w-7xl">
        <header className="mx-auto mb-8 max-w-2xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/50">
            What you get back
          </p>
          <h2 className="mt-3 font-display text-3xl font-black sm:text-5xl">
            Materiality, <span className="text-materia">charted</span>.
          </h2>
          <p className="mt-4 font-mono text-sm leading-relaxed text-foreground/70 sm:text-base">
            Every disputed fact lands on a 1–10 materiality scale. The
            dashboard chart uses the same emerald-and-magenta gradient as
            the surfaces below — green for the focused disagreement, purple
            for the highest-materiality rows.
          </p>
        </header>

        <Card className="relative h-[520px] w-full overflow-hidden bg-black/[0.96]">
          <Spotlight
            className="-top-20 left-10 md:-top-10 md:left-40"
            fill="#A855F7"
          />
          <div className="relative h-full w-full">
            {active ? (
              <SplineScene
                scene="https://prod.spline.design/YjQh3czZPvLqnDAp/scene.splinecode"
                className="h-full w-full"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center">
                <span className="loader" aria-label="Loading 3D charts" />
              </div>
            )}
          </div>
        </Card>
      </div>
    </section>
  );
}
