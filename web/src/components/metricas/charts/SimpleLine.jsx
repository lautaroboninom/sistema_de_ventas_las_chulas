import React from "react";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#6366f1"];

export default function SimpleLine({ title, categories = [], series = [], height = 200, onPointClick, fmt = (v)=>v }) {
  const max = Math.max(1, ...series.flatMap(s => s.values).map(v=>Number(v)||0));
  const w = Math.max(360, categories.length * 50);
  const pad = 24;
  const innerW = w - pad*2;
  const innerH = height - pad*2;
  const xOf = (i) => pad + (i * innerW) / Math.max(1, categories.length-1);
  const yOf = (v) => height - pad - (innerH * (Number(v)||0) / max);
  return (
    <div className="p-3 border rounded bg-white overflow-x-auto">
      <div className="text-sm text-gray-600 mb-1">{title}</div>
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full h-48">
        <line x1={pad} y1={height-pad} x2={w-pad} y2={height-pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={height-pad} stroke="#e5e7eb" />
        {series.map((s, si) => {
          const pts = s.values.map((v,i)=>`${xOf(i)},${yOf(v)}`).join(" ");
          const color = s.color || COLORS[si % COLORS.length];
          return (
            <g key={si}>
              <polyline fill="none" stroke={color} strokeWidth="2" points={pts} />
              {s.values.map((v,i)=> (
                <circle key={i} cx={xOf(i)} cy={yOf(v)} r={3} fill={color}
                  style={{cursor: onPointClick ? 'pointer' : 'default'}}
                  onClick={() => onPointClick && onPointClick(si, i)}>
                  <title>{s.name || ''} {categories[i]}: {fmt(v)}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

