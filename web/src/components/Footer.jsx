// web/src/components/Footer.jsx
import React from "react";

export default function Footer() {
  return (
    <footer className="border-t bg-white">
      <div className="max-w-7xl mx-auto px-4 py-3 text-sm text-gray-500 flex flex-col md:flex-row md:items-center md:justify-between gap-1">
        <span>&copy; {new Date().getFullYear()} EQUILUX MD. Sistema de Reparaciones.</span>
        <span>Washington 2757 1P, CABA | (+54 9) 11 2758-2826 | contacto@equiluxmd.com</span>
      </div>
    </footer>
  );
}
