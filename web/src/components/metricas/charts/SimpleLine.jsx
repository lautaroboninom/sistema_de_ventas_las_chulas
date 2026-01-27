import React from "react";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#6366f1"];

export default function SimpleLine({
  title,
  subtitle,
  categories = [],
  series = [],
  height = 200,
  onPointClick,
  fmt = (v) => v,
  showLegend,
  tickEvery,
  xLabels,
}) {
  const max = Math.max(1, ...series.flatMap((s) => s.values).map((v) => Number(v) || 0));
  const w = Math.max(360, categories.length * 56);
  const pad = 30;
  const innerW = w - pad * 2;
  const innerH = height - pad * 2;
  const xOf = (i) => pad + (i * innerW) / Math.max(1, categories.length - 1);
  const yOf = (v) => height - pad - (innerH * (Number(v) || 0) / max);
  const labels = xLabels && xLabels.length === categories.length ? xLabels : categories;
  const step = Math.max(1, tickEvery || Math.ceil(categories.length / 8));
  const gridLines = 4;
  const legendOn = typeof showLegend === "boolean" ? showLegend : series.length > 1;

  return (
    <div className="p-3 border rounded bg-white overflow-x-auto">
      <div className="mb-2">
        <div className="text-sm font-medium text-gray-700">{title}</div>
        {subtitle ? <div className="text-xs text-gray-500">{subtitle}</div> : null}
        {legendOn ? (
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-600">
            {series.map((s, si) => {
              const color = s.color || COLORS[si % COLORS.length];
              return (
                <div key={`${s.name || "serie"}-${si}`} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-sm" style={{ background: color }} />
                  <span>{s.name || `Serie ${si + 1}`}</span>
                </div>
              );
            })}
          </div>
        ) : null}
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
        {labels.map((label, i) => {
          if (!label || i % step !== 0) return null;
          return (
            <text key={`label-${i}`} x={xOf(i)} y={height - 8} textAnchor="middle" fontSize="10" fill="#6b7280">
              {label}
            </text>
          );
        })}
        {series.map((s, si) => {
          const pts = s.values.map((v, i) => `${xOf(i)},${yOf(v)}`).join(" ");
          const color = s.color || COLORS[si % COLORS.length];
          return (
            <g key={si}>
              <polyline fill="none" stroke={color} strokeWidth="2" points={pts} />
              {s.values.map((v, i) => (
                <circle
                  key={i}
                  cx={xOf(i)}
                  cy={yOf(v)}
                  r={3}
                  fill={color}
                  style={{ cursor: onPointClick ? "pointer" : "default" }}
                  onClick={() => onPointClick && onPointClick(si, i)}
                >
                  <title>{s.name || ""} {categories[i]}: {fmt(v)}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
