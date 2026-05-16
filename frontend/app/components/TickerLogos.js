"use client";

import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

/**
 * Researched-companies logo strip — infinite horizontal scroll via GSAP.
 *
 * Logos are local monochrome SVGs from simple-icons, served as CSS masks so
 * the existing currentColor / theme variables drive the tint. Clearbit's free
 * Logo API was deprecated, so we no longer fetch logos at runtime.
 */

const TICKERS = [
  "NVDA",
  "TSLA",
  "PLTR",
  "AAPL",
  "MSFT",
  "META",
  "AMD",
  "AMZN",
  "GOOG",
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

      // Duplicated track + xPercent:-50 means we loop back to the exact visual
      // start frame without a visible jump.
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
      <div ref={stripRef} className="flex w-max items-center gap-10 py-4">
        {items.map((ticker, idx) => (
          <figure
            key={`${ticker}-${idx}`}
            className="flex h-16 w-44 shrink-0 items-center justify-center gap-3 rounded-lg border border-border/40 bg-secondary/40 px-4"
          >
            <span
              aria-hidden="true"
              className="block bg-foreground/85"
              style={{
                width: "28px",
                height: "28px",
                WebkitMaskImage: `url(/logos/${ticker}.svg)`,
                maskImage: `url(/logos/${ticker}.svg)`,
                WebkitMaskRepeat: "no-repeat",
                maskRepeat: "no-repeat",
                WebkitMaskPosition: "center",
                maskPosition: "center",
                WebkitMaskSize: "contain",
                maskSize: "contain",
              }}
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
