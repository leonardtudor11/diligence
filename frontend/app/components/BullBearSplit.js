"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import Image from "next/image";

gsap.registerPlugin(ScrollTrigger);

/**
 * Split-screen Bull vs Bear section.
 *
 * Color mapping inverts the market convention at the user's request:
 *   left half  = BEAR  on green tint (would normally be red)
 *   right half = BULL  on red tint   (would normally be green)
 *
 * On scroll-in: both animals start offscreen, charge inward, collide, and
 * shake. Pure GSAP timeline driven by ScrollTrigger. prefers-reduced-motion
 * collapses everything to a static layout via the JS guard below + the CSS
 * backstop in globals.css.
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
          start: "top 70%",
          toggleActions: "play none none reverse",
        },
        defaults: { ease: "power3.out" },
      });

      tl.set(".bb-spark", { opacity: 0, scale: 0 })
        .from(".bb-bear", { xPercent: -160, opacity: 0, duration: 1.0 })
        .from(".bb-bull", { xPercent: 160, opacity: 0, duration: 1.0 }, "<")
        .to(".bb-spark", { opacity: 1, scale: 1.2, duration: 0.35 }, ">-0.05")
        .to(".bb-spark", { scale: 1, duration: 0.4, ease: "back.out(2)" })
        .fromTo(
          ".bb-shake",
          { x: -6 },
          { x: 6, duration: 0.06, repeat: 5, yoyo: true, ease: "none" },
          "<"
        )
        .from(
          ".bb-stat",
          { opacity: 0, y: 14, duration: 0.4, stagger: 0.08 },
          "-=0.2"
        );

      // Idle breathing while in view.
      gsap.to(".bb-bear", {
        y: -4,
        duration: 2.2,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: 2.2,
      });
      gsap.to(".bb-bull", {
        y: -4,
        duration: 2.4,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        delay: 2.4,
      });
    },
    { scope: ref }
  );

  return (
    <section
      ref={ref}
      id="how"
      className="relative w-full overflow-hidden px-6 py-24 sm:py-32"
    >
      <div className="mx-auto max-w-7xl">
        <header className="mx-auto mb-12 max-w-2xl text-center">
          <p className="font-mono text-xs uppercase tracking-[0.4em] text-foreground/50">
            The adversarial frame
          </p>
          <h2 className="mt-3 font-display text-3xl font-black sm:text-5xl">
            Bull <span className="text-destructive">charges</span>.
            Bear <span className="text-accent">counters</span>.
          </h2>
          <p className="mt-4 font-mono text-sm leading-relaxed text-foreground/70 sm:text-base">
            Two agents read the same evidence and argue the opposite case. The
            reconciler ranks where they disagree by materiality.
          </p>
        </header>

        <div className="bb-shake relative grid grid-cols-1 overflow-hidden rounded-2xl border border-border/40 bg-background/40 backdrop-blur md:grid-cols-2">
          {/* LEFT — BEAR (green per user request) */}
          <div className="relative flex flex-col items-center gap-6 bg-accent/[0.06] p-10 sm:p-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-accent">
              Bear case · short side
            </p>
            <Image
              src="/bear.svg"
              alt="Bear"
              width={220}
              height={140}
              className="bb-bear h-32 w-auto"
              style={{ color: "var(--color-accent)" }}
              priority
            />
            <ul className="bb-stat-group w-full max-w-xs space-y-2 font-mono text-sm text-foreground/85">
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Hedging in Q&amp;A</span>
                <span className="text-accent">14 flags</span>
              </li>
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Concentration risk</span>
                <span className="text-accent">3 customers</span>
              </li>
              <li className="bb-stat flex items-center justify-between py-1">
                <span>Margin trajectory</span>
                <span className="text-accent">−320 bps</span>
              </li>
            </ul>
          </div>

          {/* RIGHT — BULL (red per user request) */}
          <div className="relative flex flex-col items-center gap-6 bg-destructive/[0.06] p-10 sm:p-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-destructive">
              Bull case · long side
            </p>
            <Image
              src="/bull.svg"
              alt="Bull"
              width={220}
              height={140}
              className="bb-bull h-32 w-auto"
              style={{ color: "var(--color-destructive)" }}
              priority
            />
            <ul className="bb-stat-group w-full max-w-xs space-y-2 font-mono text-sm text-foreground/85">
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Compute demand</span>
                <span className="text-destructive">+52% YoY</span>
              </li>
              <li className="bb-stat flex items-center justify-between border-b border-border/30 py-1">
                <span>Pricing power</span>
                <span className="text-destructive">+18% ASP</span>
              </li>
              <li className="bb-stat flex items-center justify-between py-1">
                <span>Operating leverage</span>
                <span className="text-destructive">+410 bps</span>
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
