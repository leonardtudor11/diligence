"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import Image from "next/image";
import TickerLogos from "./TickerLogos";

export default function Hero() {
  const heroRef = useRef(null);

  useGSAP(
    () => {
      // Breathing glow on the mark only. Entrance fade-ins were removed because
      // gsap.from({opacity:0}) snaps the element invisible on mount and stays
      // there until the tween's first frame ticks, which produced a visible
      // "blank flash" on every refresh and made the buttons appear off-axis
      // when caught mid-stagger.
      gsap.to(".hero-mark", {
        filter: "drop-shadow(0 0 18px rgba(34,197,94,0.55))",
        duration: 2.4,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
      });
    },
    { scope: heroRef }
  );

  return (
    <section
      ref={heroRef}
      className="relative flex flex-col items-center justify-center px-6 pt-24 pb-16 sm:pt-32 sm:pb-24"
    >
      <Image
        src="/diligence-mark.svg"
        alt="Diligence mark"
        width={72}
        height={72}
        className="hero-mark text-accent"
        style={{ color: "var(--color-accent)" }}
      />

      <p className="hero-eyebrow mt-6 font-mono text-xs uppercase tracking-[0.4em] text-foreground/60">
        Multi-agent due diligence
      </p>

      <h1 className="hero-title mt-4 max-w-4xl text-center font-display text-4xl font-black leading-tight tracking-tight sm:text-6xl">
        Bull vs bear, <span className="neon-accent">side by side.</span>
      </h1>

      <p className="hero-subtitle mt-6 max-w-2xl text-center font-mono text-base leading-relaxed text-foreground/70 sm:text-lg">
        Diligence reads 10-K, 10-Q, and the earnings call. Five adversarial
        agents debate the evidence. You see the disputed facts, ranked by
        materiality.
      </p>

      <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
        <a
          href="#analyze"
          className="hero-cta box-border inline-flex h-12 w-64 max-w-full items-center justify-center rounded-md border border-transparent bg-accent px-6 font-mono text-sm font-semibold tracking-wide text-background transition-all duration-200 hover:brightness-110 cursor-pointer sm:w-48"
        >
          Run a ticker
        </a>
        <a
          href="#how"
          className="hero-cta box-border inline-flex h-12 w-64 max-w-full items-center justify-center rounded-md border border-border/60 bg-secondary/30 px-6 font-mono text-sm font-semibold tracking-wide text-foreground/90 transition-colors duration-200 hover:bg-secondary/60 cursor-pointer sm:w-48"
        >
          How it works
        </a>
      </div>

      <div className="hero-strip mt-20 w-full max-w-6xl">
        <p className="mb-4 text-center font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/40">
          Coverage on day one
        </p>
        <TickerLogos />
      </div>
    </section>
  );
}
