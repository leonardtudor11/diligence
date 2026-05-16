"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const ACCENT = "var(--color-accent, #22C55E)";
const DESTRUCT = "var(--color-destructive, #EF4444)";
const NEUTRAL = "rgba(248, 250, 252, 0.35)";

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
  // Recharts treats the first key in `data` as the Y-axis category for a
  // horizontal layout. We pre-truncate the topic so the axis stays readable.
  const data = facts.map((f, i) => ({
    ...f,
    idx: i,
    label: truncate(f.topic, 48),
  }));

  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 6, right: 24, left: 0, bottom: 6 }}
          barCategoryGap={10}
        >
          <XAxis
            type="number"
            domain={[0, 10]}
            tick={{ fill: "rgba(248,250,252,0.55)", fontSize: 11, fontFamily: "var(--font-mono)" }}
            axisLine={{ stroke: "rgba(248,250,252,0.15)" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={210}
            tick={{ fill: "rgba(248,250,252,0.85)", fontSize: 11, fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(248,250,252,0.04)" }} />
          <Bar dataKey="materiality_score" radius={[0, 6, 6, 0]} onClick={(d) => onPick(d.idx)}>
            {data.map((d, i) => (
              <Cell
                key={d.idx}
                fill={
                  i === activeIdx
                    ? ACCENT
                    : d.materiality_score >= 8
                    ? DESTRUCT
                    : NEUTRAL
                }
                cursor="pointer"
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
