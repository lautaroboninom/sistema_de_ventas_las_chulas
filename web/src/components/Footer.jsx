// web/src/components/Footer.jsx
import React from "react";

export default function Footer() {
  const companyLegal =
    import.meta.env.VITE_COMPANY_LEGAL ||
    import.meta.env.VITE_APP_NAME ||
    "Sistema de Reparaciones";

  return (
    <footer className="border-t bg-white">
      <div className="max-w-7xl mx-auto px-4 py-3 text-sm text-gray-500">
        <span>
          &copy; {new Date().getFullYear()} {companyLegal}. Todos los derechos reservados.
        </span>
      </div>
    </footer>
  );
}
