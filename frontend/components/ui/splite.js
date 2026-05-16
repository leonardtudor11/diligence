"use client";

import Spline from "@splinetool/react-spline/next";
import { Suspense } from "react";

/**
 * Loads a Spline scene through the Next.js App Router-aware subpath. The
 * `/next` re-export handles the SSR boundary internally so we only need the
 * Suspense fallback for the runtime download (~1 MB).
 */
export function SplineScene({ scene, className }) {
  return (
    <Suspense
      fallback={
        <div className="flex h-full w-full items-center justify-center">
          <span className="loader" aria-label="Loading 3D scene" />
        </div>
      }
    >
      <Spline scene={scene} className={className} />
    </Suspense>
  );
}
