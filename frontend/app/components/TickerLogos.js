"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import Image from "next/image";

/**
 * Researched-companies logo strip — infinite horizontal scroll powered by GSAP.
 *
 * Logo source: Clearbit Logo API (`https://logo.clearbit.com/<domain>`), no key,
 * free for development. Replace with locally hosted SVGs before production if
 * Clearbit's free tier becomes a constraint.
 *
 * Reduced-motion guard: useGSAP runs inside a context that the @media rule in
 * globals.css overrides, but we also bail early in JS so the timeline never
 * starts when the user has reduced motion on.
 */

const TICKERS = [
  { ticker: "NVDA", domain: "nvidia.com" },
  { ticker: "TSLA", domain: "tesla.com" },
  { ticker: "PLTR", domain: "palantir.com" },
  { ticker: "AAPL", domain: "apple.com" },
  { ticker: "MSFT", domain: "microsoft.com" },
  { ticker: "META", domain: "meta.com" },
  { ticker: "AMD", domain: "amd.com" },
  { ticker: "AMZN", domain: "amazon.com" },
  { ticker: "GOOG", domain: "abc.xyz" },
];

export default function TickerLogos() {
  const stripRef = useRef(null);

  useGSAP(
    () => {
      if (typeof window === "undefined") return;
      const prefersReduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;
      if (prefersReduced) return;

      // Single-loop horizontal scroll. The track is duplicated, so a -50% shift
      // returns to the visual start frame without a perceptible jump.
      gsap.to(stripRef.current, {
        xPercent: -50,
        ease: "none",
        duration: 30,
        repeat: -1,
      });
    },
    { scope: stripRef }
  );

  const items = [...TICKERS, ...TICKERS];

  return (
    <div className="logo-strip-mask w-full overflow-hidden">
      <div ref={stripRef} className="flex w-max items-center gap-12 py-4">
        {items.map(({ ticker, domain }, idx) => (
          <figure
            key={`${ticker}-${idx}`}
            className="flex h-16 w-44 shrink-0 items-center justify-center gap-3 rounded-lg border border-border/40 bg-secondary/40 px-4"
          >
            <Image
              src={`https://logo.clearbit.com/${domain}?size=64`}
              alt={`${ticker} logo`}
              width={32}
              height={32}
              unoptimized
              className="opacity-90"
            />
            <figcaption className="font-display text-sm font-bold tracking-widest text-foreground/90">
              {ticker}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
