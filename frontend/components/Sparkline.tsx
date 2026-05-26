"use client";
import { useId, useMemo } from "react";

export function Sparkline({
  data,
  height = 64,
  stroke = "#22d3a8",
  fillFrom = "rgba(34,211,168,0.35)",
  fillTo = "rgba(34,211,168,0)",
}: {
  data: number[];
  height?: number;
  stroke?: string;
  fillFrom?: string;
  fillTo?: string;
}) {
  const id = useId().replace(/:/g, "");
  const { path, area, viewW, viewH } = useMemo(() => {
    const W = 600;
    const H = height;
    if (!data || data.length < 2) {
      return { path: "", area: "", viewW: W, viewH: H };
    }
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const step = W / (data.length - 1);
    const points = data.map((v, i) => {
      const x = i * step;
      const y = H - ((v - min) / range) * (H - 6) - 3;
      return [x, y] as const;
    });
    const path = points.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(" ");
    const area = `${path} L${W},${H} L0,${H} Z`;
    return { path, area, viewW: W, viewH: H };
  }, [data, height]);

  if (!data || data.length < 2) {
    return (
      <div
        style={{ height }}
        className="w-full flex items-center justify-center text-[11px] text-gray-500 border border-dashed border-white/5 rounded-md"
      >
        not enough equity data yet
      </div>
    );
  }

  return (
    <svg viewBox={`0 0 ${viewW} ${viewH}`} preserveAspectRatio="none" className="w-full" style={{ height }}>
      <defs>
        <linearGradient id={`g-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fillFrom} />
          <stop offset="100%" stopColor={fillTo} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g-${id})`} />
      <path d={path} fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
