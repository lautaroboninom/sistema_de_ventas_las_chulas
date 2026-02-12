// web/src/components/Footer.jsx
import React from "react";

export default function Footer() {
  return (
    <footer className="border-t bg-white">
      <div className="max-w-7xl mx-auto px-4 py-3 text-sm text-gray-500 flex items-center justify-between">
        <span>
          &copy; {new Date().getFullYear()} Sepid S.A. Reparaciones. Todos los derechos reservados.
        </span>
        <span>Creado por Lautaro Bonino Montepaone</span>
      </div>
    </footer>
  );
}
