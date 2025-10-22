import React from "react";

export default function SimpleBars({ title, categories = [], values = [], height = 200, onClickBar, fmt = (v)=>v, color = "#3b82f6" }) {
  const max = Math.max(1, ...values.map(v=>Number(v)||0));
  const w = Math.max(320, categories.length * 40);
  const pad = 24;
  const innerW = w - pad*2;
  const innerH = height - pad*2;
  const barW = innerW / Math.max(1, categories.length);
  return (
    <div className="p-3 border rounded bg-white overflow-x-auto">
      <div className="text-sm text-gray-600 mb-1">{title}</div>
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full h-48">
        {/* axes */}
        <line x1={pad} y1={height-pad} x2={w-pad} y2={height-pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={height-pad} stroke="#e5e7eb" />
        {values.map((v, i) => {
          const x = pad + i * barW + barW*0.1;
          const h = innerH * (Number(v)||0) / max;
          const y = height - pad - h;
          return (
            <g key={i}>
              <rect x={x} y={y} width={barW*0.8} height={Math.max(0,h)} fill={color}
                style={{cursor: onClickBar ? 'pointer' : 'default'}}
                onClick={() => onClickBar && onClickBar(i)}
              />
              <title>{categories[i]}: {fmt(v)}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

