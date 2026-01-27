import React from "react";

export default function SimpleBars({
  title,
  subtitle,
  categories = [],
  labels,
  titles,
  values = [],
  height = 200,
  onClickBar,
  fmt = (v) => v,
  color = "#3b82f6",
  showValues = false,
  tickEvery,
}) {
  const labelList = labels && labels.length === categories.length ? labels : categories;
  const titleList = titles && titles.length === categories.length ? titles : categories;
  const max = Math.max(1, ...values.map((v) => Number(v) || 0));
  const maxLabelLen = Math.max(0, ...labelList.map((l) => String(l || "").length));
  const perBar = Math.min(160, Math.max(60, Math.ceil(maxLabelLen * 6.5) || 60));
  const w = Math.max(360, categories.length * perBar);
  const pad = 30;
  const innerW = w - pad * 2;
  const innerH = height - pad * 2;
  const barW = innerW / Math.max(1, categories.length);
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
        {values.map((v, i) => {
          const x = pad + i * barW + barW * 0.1;
          const h = innerH * (Number(v) || 0) / max;
          const y = height - pad - h;
          const labelX = pad + i * barW + barW * 0.5;
          const labelY = height - 8;
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={barW * 0.8}
                height={Math.max(0, h)}
                fill={color}
                style={{ cursor: onClickBar ? "pointer" : "default" }}
                onClick={() => onClickBar && onClickBar(i)}
              />
              {showValues ? (
                <text x={labelX} y={Math.max(pad + 10, y - 4)} textAnchor="middle" fontSize="10" fill="#374151">
                  {fmt(v)}
                </text>
              ) : null}
              {labelList[i] && i % step === 0 ? (
                <text x={labelX} y={labelY} textAnchor="middle" fontSize="10" fill="#6b7280">
                  {labelList[i]}
                </text>
              ) : null}
              <title>{titleList[i]}: {fmt(v)}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
