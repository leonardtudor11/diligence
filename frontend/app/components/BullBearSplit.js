"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger);

/**
 * Split-screen Bull vs Bear section.
 *
 * On scroll-in: both animals charge inward from offscreen, collide, and
 * shake. Pure GSAP timeline driven by ScrollTrigger. prefers-reduced-motion
 * collapses everything to a static layout.
 *
 * Initial-state positioning happens INSIDE the timeline (`tl.set`) rather
 * than via `gsap.set` at mount, so the animals stay visible until the
 * ScrollTrigger actually fires. Without this, the section rendered blank
 * for ~600ms after first paint and looked broken in screen recordings.
 */

export default function BullBearSplit() {
  const ref = useRef(null);

  useGSAP(
    () => {
      const prefersReduced =
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      if (prefersReduced) {
        gsap.set([".bb-bear", ".bb-bull", ".bb-spark"], { opacity: 1, x: 0 });
        return;
      }

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: ref.current,
          start: "top 85%",
          toggleActions: "play none none reverse",
        },
        defaults: { ease: "power3.out" },
      });

      tl
        // Start state — kept INSIDE the timeline so animals stay visible
        // until the ScrollTrigger actually fires.
        .set(".bb-bear",  { xPercent: -240, opacity: 0 })
        .set(".bb-bull",  { xPercent:  240, opacity: 0 })
        .set(".bb-spark", { opacity: 0, scale: 0 })
        .set(".bb-stat",  { opacity: 0, y: 14 })
        // Charge inward — accelerating ease so the impact reads as fast.
        .to(".bb-bear", {
          xPercent: 0,
          opacity: 1,
          duration: 0.9,
          ease: "power4.in",
        })
        .to(
          ".bb-bull",
          { xPercent: 0, opacity: 1, duration: 0.9, ease: "power4.in" },
          "<"
        )
        // Collision: spark pops with overshoot, container shakes once.
        .to(
          ".bb-spark",
          { opacity: 1, scale: 1.4, duration: 0.18, ease: "back.out(3)" },
          ">-0.06"
        )
        .fromTo(
          ".bb-shake",
          { x: -8 },
          { x: 8, duration: 0.06, repeat: 4, yoyo: true, ease: "none" },
          "<"
        )
        // Recoil outward briefly.
        .to(
          ".bb-bear",
          { x: "-=22", duration: 0.12, ease: "power2.out" },
          "<"
        )
        .to(".bb-bull", { x: "+=22", duration: 0.12, ease: "power2.out" }, "<")
        // Elastic settle back toward center — animals end nose-to-nose.
        .to(".bb-bear", { x: 0, duration: 0.55, ease: "elastic.out(1, 0.45)" })
        .to(
          ".bb-bull",
          { x: 0, duration: 0.55, ease: "elastic.out(1, 0.45)" },
          "<"
        )
        .to(".bb-spark", { scale: 1, duration: 0.3 }, "<")
        // Stat lines fade in once the dust settles.
        .to(
          ".bb-stat",
          { opacity: 1, y: 0, duration: 0.4, stagger: 0.07 },
          "-=0.25"
        );

      // Idle bob — gentler than before so it doesn't compete with the clash.
      gsap.to(".bb-bear", {
        y: -3,
        duration: 2.0,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: 2.5,
      });
      gsap.to(".bb-bull", {
        y: -3,
        duration: 2.2,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: 2.7,
      });
    },
    { scope: ref }
  );

  return (
    <section
      ref={ref}
      id="adversarial"
      className="relative w-full overflow-hidden px-6 py-16 sm:py-20"
    >
      <div className="mx-auto max-w-7xl">
        <header className="mx-auto mb-8 max-w-2xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/50">
            The adversarial frame
          </p>
          <h2 className="mt-3 font-display text-3xl font-black sm:text-5xl">
            Bull <span className="text-accent">charges</span>.
            Bear <span className="text-destructive">counters</span>.
          </h2>
          <p className="mt-4 font-mono text-sm leading-relaxed text-foreground/70 sm:text-base">
            Two agents read the same evidence and argue the opposite case. The
            reconciler ranks where they disagree by materiality.
          </p>
        </header>

        <div className="bb-shake relative grid grid-cols-1 overflow-hidden rounded-2xl border border-border/40 bg-background/40 backdrop-blur md:grid-cols-2">
          {/* LEFT — BEAR (red, market-convention bear-side risk colour) */}
          <div className="relative flex flex-col items-center gap-6 bg-destructive/[0.06] p-10 sm:p-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-destructive">
              Bear case · short side
            </p>
            <span
              role="img"
              aria-label="Bear silhouette"
              className="bb-bear block bg-destructive"
              style={{
                width: "12rem",
                height: "8rem",
                WebkitMaskImage: "url(/bear.svg)",
                maskImage: "url(/bear.svg)",
                WebkitMaskRepeat: "no-repeat",
                maskRepeat: "no-repeat",
                WebkitMaskPosition: "center",
                maskPosition: "center",
                WebkitMaskSize: "contain",
                maskSize: "contain",
                filter: "drop-shadow(0 6px 18px rgba(239,68,68,0.35))",
              }}
            />
            <ul className="bb-stat-group w-full max-w-xs space-y-2 font-mono text-sm text-foreground/85">
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Hedging in Q&amp;A</span>
                <span className="text-destructive">14 flags</span>
              </li>
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Concentration risk</span>
                <span className="text-destructive">3 customers</span>
              </li>
              <li className="bb-stat flex items-center justify-between py-1">
                <span>Margin trajectory</span>
                <span className="text-destructive">−320 bps</span>
              </li>
            </ul>
          </div>

          {/* RIGHT — BULL (green, market-convention long-side positive colour) */}
          <div className="relative flex flex-col items-center gap-6 bg-accent/[0.06] p-10 sm:p-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-accent">
              Bull case · long side
            </p>
            <span
              role="img"
              aria-label="Bull silhouette"
              className="bb-bull block bg-accent"
              style={{
                width: "12rem",
                height: "8rem",
                WebkitMaskImage: "url(/bull.svg)",
                maskImage: "url(/bull.svg)",
                WebkitMaskRepeat: "no-repeat",
                maskRepeat: "no-repeat",
                WebkitMaskPosition: "center",
                maskPosition: "center",
                WebkitMaskSize: "contain",
                maskSize: "contain",
                transform: "scaleX(-1)",
                filter: "drop-shadow(0 6px 18px rgba(34,197,94,0.35))",
              }}
            />
            <ul className="bb-stat-group w-full max-w-xs space-y-2 font-mono text-sm text-foreground/85">
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Compute demand</span>
                <span className="text-accent">+52% YoY</span>
              </li>
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Pricing power</span>
                <span className="text-accent">+18% ASP</span>
              </li>
              <li className="bb-stat flex items-center justify-between py-1">
                <span>Operating leverage</span>
                <span className="text-accent">+410 bps</span>
              </li>
            </ul>
          </div>

          {/* CENTER spark / collision marker */}
          <div className="pointer-events-none absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 md:block">
            <div
              className="bb-spark grid h-20 w-20 place-items-center rounded-full border border-border/50 bg-background/95 font-display text-base font-black tracking-tight text-foreground"
              style={{
                boxShadow:
                  "0 0 0 8px rgba(34,197,94,0.10), 0 0 0 18px rgba(239,68,68,0.08)",
              }}
            >
              VS
            </div>
          </div>
        </div>

        <p className="mt-10 text-center font-mono text-xs uppercase tracking-[0.3em] text-foreground/40">
          Reconciler ranks every disputed fact by materiality · 1–10 scale
        </p>
      </div>
    </section>
  );
}
