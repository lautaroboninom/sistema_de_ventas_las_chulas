import { useId } from 'react';

export default function InfoHint({ text, className = '' }) {
  const tooltipId = useId();
  const cleanText = String(text || '').trim();
  if (!cleanText) return null;

  return (
    <span className={`relative inline-flex align-middle ${className}`}>
      <span
        tabIndex={0}
        role="button"
        aria-label={`Informacion: ${cleanText}`}
        aria-describedby={tooltipId}
        className="group inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-neutral-300 bg-neutral-50 text-[11px] font-bold leading-none text-neutral-600 transition hover:border-neutral-500 hover:bg-white focus:border-neutral-700 focus:outline-none focus:ring-2 focus:ring-neutral-300"
      >
        i
        <span
          id={tooltipId}
          role="tooltip"
          className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden w-72 max-w-[80vw] -translate-x-1/2 rounded-md border border-neutral-200 bg-neutral-950 px-3 py-2 text-left text-xs font-medium leading-snug text-white shadow-lg group-hover:block group-focus:block"
        >
          {cleanText}
        </span>
      </span>
    </span>
  );
}
