import React from "react";

// Expects items: [{p25, p50, p75, p90, p95}] aligned with categories
export default function BoxPlot({ title, categories = [], items = [], height = 200, onClickBox, color = "#3b82f6" }) {
  const values = items.flatMap(it => [it?.p25, it?.p75, it?.p90, it?.p95]).filter(v => v != null).map(Number);
  const max = Math.max(1, ...values);
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
        {items.map((it,i)=>{
          const x = xOf(i);
          const p25 = it?.p25; const p50 = it?.p50; const p75 = it?.p75; const p90 = it?.p90 ?? it?.p75; const p95 = it?.p95 ?? it?.p90;
          if (p25 == null || p50 == null || p75 == null) return null;
          const boxW = 18;
          const y25 = yOf(p25), y50 = yOf(p50), y75 = yOf(p75), y90 = yOf(p90), y95 = yOf(p95);
          return (
            <g key={i} transform={`translate(${x},0)`} style={{cursor:onClickBox ? 'pointer' : 'default'}} onClick={()=>onClickBox && onClickBox(i)}>
              {/* whiskers */}
              <line x1={0} y1={y75} x2={0} y2={y95} stroke={color} />
              <line x1={-boxW/4} y1={y95} x2={boxW/4} y2={y95} stroke={color} />
              <line x1={0} y1={y25} x2={0} y2={y90} stroke={color} />
              <line x1={-boxW/4} y1={y90} x2={boxW/4} y2={y90} stroke={color} />
              {/* box */}
              <rect x={-boxW/2} y={y75} width={boxW} height={Math.max(1, y25 - y75)} fill="#bfdbfe" stroke={color} />
              {/* median */}
              <line x1={-boxW/2} y1={y50} x2={boxW/2} y2={y50} stroke={color} strokeWidth={2} />
              <title>{categories[i]}: P50 {p50?.toFixed?.(1)} (P25 {p25?.toFixed?.(1)} – P75 {p75?.toFixed?.(1)})</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

