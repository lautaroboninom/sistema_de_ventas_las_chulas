import React from 'react';

export default function Footer({ legalName }) {
  const companyLegal = legalName || import.meta.env.VITE_COMPANY_LEGAL || import.meta.env.VITE_APP_NAME || 'Las Chulas';

  return (
    <footer className="border-t border-neutral-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 text-xs text-neutral-500">
        <span>&copy; {new Date().getFullYear()} {companyLegal}</span>
        <span className="hidden tracking-wide text-neutral-400 sm:inline">RetailHub | LB Solutions</span>
      </div>
    </footer>
  );
}
