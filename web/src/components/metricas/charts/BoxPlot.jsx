import React from "react";

// Expects items: [{p25, p50, p75, p90, p95}] aligned with categories
export default function BoxPlot({
  title,
  subtitle,
  categories = [],
  items = [],
  height = 200,
  onClickBox,
  color = "#3b82f6",
  tickEvery,
}) {
  const values = items
    .flatMap((it) => [it?.p25, it?.p75, it?.p90, it?.p95])
    .filter((v) => v != null)
    .map(Number);
  const max = Math.max(1, ...values);
  const w = Math.max(360, categories.length * 56);
  const pad = 30;
  const innerW = w - pad * 2;
  const innerH = height - pad * 2;
  const xOf = (i) => pad + (i * innerW) / Math.max(1, categories.length - 1);
  const yOf = (v) => height - pad - (innerH * (Number(v) || 0) / max);
  const step = Math.max(1, tickEvery || Math.ceil(categories.length / 8));
  const gridLines = 4;

  return (
    <div className="p-3 border rounded bg-white overflow-x-auto">
      <div className="mb-2">
        <div className="text-sm font-medium text-gray-700">{title}</div>
        {subtitle ? <div className="text-xs text-gray-500">{subtitle}</div> : null}
      </div>
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full h-48" role="img" aria-label={title}>
        <title>{title}</title>
        {subtitle ? <desc>{subtitle}</desc> : null}
        {Array.from({ length: gridLines }).map((_, i) => {
          const y = height - pad - (innerH * (i + 1)) / gridLines;
          return <line key={`grid-${i}`} x1={pad} y1={y} x2={w - pad} y2={y} stroke="#f3f4f6" />;
        })}
        <line x1={pad} y1={height - pad} x2={w - pad} y2={height - pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#e5e7eb" />
        {categories.map((label, i) => {
          if (!label || i % step !== 0) return null;
          return (
            <text key={`label-${i}`} x={xOf(i)} y={height - 8} textAnchor="middle" fontSize="10" fill="#6b7280">
              {label}
            </text>
          );
        })}
        {items.map((it, i) => {
          const x = xOf(i);
          const p25 = it?.p25;
          const p50 = it?.p50;
          const p75 = it?.p75;
          const p90 = it?.p90 ?? it?.p75;
          const p95 = it?.p95 ?? it?.p90;
          if (p25 == null || p50 == null || p75 == null) return null;
          const boxW = 18;
          const y25 = yOf(p25);
          const y50 = yOf(p50);
          const y75 = yOf(p75);
          const y90 = yOf(p90);
          const y95 = yOf(p95);
          return (
            <g
              key={i}
              transform={`translate(${x},0)`}
              style={{ cursor: onClickBox ? "pointer" : "default" }}
              onClick={() => onClickBox && onClickBox(i)}
            >
              <line x1={0} y1={y75} x2={0} y2={y95} stroke={color} />
              <line x1={-boxW / 4} y1={y95} x2={boxW / 4} y2={y95} stroke={color} />
              <line x1={0} y1={y25} x2={0} y2={y90} stroke={color} />
              <line x1={-boxW / 4} y1={y90} x2={boxW / 4} y2={y90} stroke={color} />
              <rect x={-boxW / 2} y={y75} width={boxW} height={Math.max(1, y25 - y75)} fill="#bfdbfe" stroke={color} />
              <line x1={-boxW / 2} y1={y50} x2={boxW / 2} y2={y50} stroke={color} strokeWidth={2} />
              <title>{categories[i]}: P50 {p50?.toFixed?.(1)} (P25 {p25?.toFixed?.(1)} / P75 {p75?.toFixed?.(1)})</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
