"use client";

import { Suspense, lazy } from "react";

/**
 * Spline scene wrapper. We use the plain `@splinetool/react-spline` import
 * (not `/next`) because the /next subpath exports an async server component
 * that can't be rendered inside the `"use client"` parents that drive our
 * Card + Spotlight layout. React.lazy + Suspense keeps the ~1 MB Spline
 * runtime out of the initial client bundle.
 */
const Spline = lazy(() => import("@splinetool/react-spline"));

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
