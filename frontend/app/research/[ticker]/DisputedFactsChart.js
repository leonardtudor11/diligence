"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Palette ties back to the landing-page 3D charts: green for the focused
// disagreement, magenta-purple gradient (Spline scene's right surface) for
// materiality intensity, muted slate for low-materiality rows. Red was
// retired here — it signalled "danger" but materiality is just "how much
// this matters", not "this is bad".
const ACTIVE_FROM    = "#34D399"; // emerald-400, matches landing chart spike
const ACTIVE_TO      = "#22C55E"; // accent
const HEAVY_FROM     = "#D946EF"; // fuchsia-500 — high-materiality top
const HEAVY_TO       = "#7E22CE"; // purple-700 — high-materiality bottom
const MID_FROM       = "#A78BFA"; // violet-400 — mid-materiality top
const MID_TO         = "#6D28D9"; // violet-700
const LOW_FROM       = "rgba(248, 250, 252, 0.30)";
const LOW_TO         = "rgba(148, 163, 184, 0.18)";

function gradientFor(idx, score, isActive) {
  if (isActive) return { id: `bar-grad-active-${idx}`, from: ACTIVE_FROM, to: ACTIVE_TO };
  if (score >= 8) return { id: `bar-grad-heavy-${idx}`, from: HEAVY_FROM, to: HEAVY_TO };
  if (score >= 5) return { id: `bar-grad-mid-${idx}`, from: MID_FROM, to: MID_TO };
  return { id: `bar-grad-low-${idx}`, from: LOW_FROM, to: LOW_TO };
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const f = payload[0].payload;
  return (
    <div className="max-w-xs rounded-md border border-border/60 bg-background/95 p-3 font-mono text-xs shadow-lg backdrop-blur">
      <p className="text-[10px] uppercase tracking-[0.3em] text-foreground/50">
        Materiality {f.materiality_score}/10
      </p>
      <p className="mt-1 font-bold text-foreground">{f.topic}</p>
      <p className="mt-2 text-foreground/70">{f.materiality_rationale}</p>
    </div>
  );
}

export default function DisputedFactsChart({ facts, activeIdx, onPick }) {
  // Defer the chart render to client-mount so Recharts' ResponsiveContainer
  // has actual offsetWidth/offsetHeight to observe. Without this the chart
  // fires `width(-1) height(-1)` warnings on every SSR-then-hydrate cycle
  // and visibly flashes empty for ~200ms before snapping in.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const data = facts.map((f, i) => ({
    ...f,
    idx: i,
    label: truncate(f.topic, 48),
    grad: gradientFor(i, f.materiality_score, i === activeIdx),
  }));

  if (!mounted) {
    return <div className="h-[300px] w-full animate-pulse rounded bg-secondary/15" />;
  }

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 6, right: 28, left: 0, bottom: 6 }}
          barCategoryGap={14}
        >
          <defs>
            {data.map((d) => (
              <linearGradient
                key={d.grad.id}
                id={d.grad.id}
                x1="0%"
                y1="0%"
                x2="100%"
                y2="0%"
              >
                <stop offset="0%"   stopColor={d.grad.from} stopOpacity={0.95} />
                <stop offset="100%" stopColor={d.grad.to}   stopOpacity={1} />
              </linearGradient>
            ))}
            <filter id="bar-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <XAxis
            type="number"
            domain={[0, 10]}
            tick={{
              fill: "rgba(248,250,252,0.55)",
              fontSize: 11,
              fontFamily: "var(--font-mono)",
            }}
            axisLine={{ stroke: "rgba(248,250,252,0.15)" }}
            tickLine={false}
            ticks={[0, 2, 4, 6, 8, 10]}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={230}
            tick={{
              fill: "rgba(248,250,252,0.88)",
              fontSize: 11,
              fontFamily: "var(--font-mono)",
            }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ fill: "rgba(248,250,252,0.04)" }}
          />
          <Bar
            dataKey="materiality_score"
            radius={[0, 8, 8, 0]}
            isAnimationActive
            animationDuration={650}
            animationEasing="ease-out"
            onClick={(d) => onPick(d.idx)}
          >
            {data.map((d) => (
              <Cell
                key={d.idx}
                fill={`url(#${d.grad.id})`}
                cursor="pointer"
                filter={d.idx === activeIdx ? "url(#bar-glow)" : undefined}
                stroke={
                  d.idx === activeIdx
                    ? "rgba(52, 211, 153, 0.65)"
                    : "transparent"
                }
                strokeWidth={d.idx === activeIdx ? 1 : 0}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function truncate(s, n) {
  if (!s) return "";
  return s.length <= n ? s : s.slice(0, n - 1).trimEnd() + "…";
}
