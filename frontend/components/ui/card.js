import { forwardRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal Card primitive. Shadcn-style API surface (forwardRef + className
 * passthrough) but no shadcn token dependency — uses the project's existing
 * border / secondary tokens instead of bg-card / text-card-foreground.
 */
const Card = forwardRef(function Card({ className, ...props }, ref) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-border/40 bg-secondary/20 text-foreground shadow-sm",
        className
      )}
      {...props}
    />
  );
});

export { Card };
