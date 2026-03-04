import { useEffect, useState } from 'react';
import { getRetailConfigPageSettings, putRetailConfigPageSettings } from '../lib/api';

function errMsg(error) {
  return error?.message || 'Ocurrió un error inesperado';
}

const NAV_KEYS = [
  ['pos', 'POS'],
  ['productos', 'Productos'],
  ['compras', 'Compras'],
  ['ventas', 'Ventas'],
  ['garantias', 'Cambios y devoluciones'],
  ['reportes', 'Reportes'],
  ['online', 'Online'],
  ['config_general', 'Config general'],
  ['config_paginas', 'Config páginas'],
];

const PAGE_TITLE_KEYS = [
  ['pos', 'Título POS'],
  ['productos', 'Título productos'],
  ['compras', 'Título compras'],
  ['ventas', 'Título ventas'],
  ['garantias', 'Título cambios y devoluciones'],
  ['reportes', 'Título reportes'],
  ['online', 'Título online'],
  ['config', 'Título config general'],
  ['config_paginas', 'Título config páginas'],
];

const DEFAULT_ROUTES = ['/pos', '/productos', '/compras', '/ventas', '/garantias', '/online', '/config'];

function ensureSettingsShape(value) {
  const row = value || {};
  return {
    app_name: row.app_name || 'Las Chulas',
    app_tagline: row.app_tagline || 'Sistema retail de indumentaria',
    footer_legal_name: row.footer_legal_name || 'Las Chulas',
    sidebar_section_title: row.sidebar_section_title || 'Operaciones',
    default_route: row.default_route || '/pos',
    nav_labels: row.nav_labels || {},
    page_titles: row.page_titles || {},
  };
}

export default function ConfigPaginas() {
  const [settings, setSettings] = useState(ensureSettingsShape(null));
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  async function load() {
    setLoading(true);
    setErr('');
    try {
      const row = await getRetailConfigPageSettings();
      const next = ensureSettingsShape(row);
      setSettings(next);
      window.localStorage.setItem('las_chulas_default_route', next.default_route || '/pos');
      window.localStorage.setItem('las_chulas_app_name', next.app_name || 'Las Chulas');
      window.localStorage.setItem('las_chulas_app_tagline', next.app_tagline || 'Sistema retail de indumentaria');
      window.localStorage.setItem('las_chulas_footer_legal_name', next.footer_legal_name || 'Las Chulas');
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const payload = {
        app_name: settings.app_name,
        app_tagline: settings.app_tagline,
        footer_legal_name: settings.footer_legal_name,
        sidebar_section_title: settings.sidebar_section_title,
        default_route: settings.default_route,
        nav_labels: settings.nav_labels || {},
        page_titles: settings.page_titles || {},
      };
      const row = await putRetailConfigPageSettings(payload);
      const next = ensureSettingsShape(row);
      setSettings(next);
      window.localStorage.setItem('las_chulas_default_route', next.default_route || '/pos');
      window.localStorage.setItem('las_chulas_app_name', next.app_name || 'Las Chulas');
      window.localStorage.setItem('las_chulas_app_tagline', next.app_tagline || 'Sistema retail de indumentaria');
      window.localStorage.setItem('las_chulas_footer_legal_name', next.footer_legal_name || 'Las Chulas');
      setMsg('Configuración de páginas actualizada');
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  function setNavLabel(key, value) {
    setSettings((prev) => ({
      ...prev,
      nav_labels: {
        ...(prev.nav_labels || {}),
        [key]: value,
      },
    }));
  }

  function setPageTitle(key, value) {
    setSettings((prev) => ({
      ...prev,
      page_titles: {
        ...(prev.page_titles || {}),
        [key]: value,
      },
    }));
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Configuración de páginas</h1>
        <p className="text-sm text-gray-600">
          Ajustes globales de nombre de aplicación, etiquetas de menú y títulos por pantalla.
        </p>
      </div>

      <form className="card space-y-4" onSubmit={save}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Nombre app</label>
            <input
              className="input"
              value={settings.app_name}
              onChange={(e) => setSettings((prev) => ({ ...prev, app_name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Subtítulo login</label>
            <input
              className="input"
              value={settings.app_tagline}
              onChange={(e) => setSettings((prev) => ({ ...prev, app_tagline: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Nombre legal footer</label>
            <input
              className="input"
              value={settings.footer_legal_name}
              onChange={(e) => setSettings((prev) => ({ ...prev, footer_legal_name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Título sección menú</label>
            <input
              className="input"
              value={settings.sidebar_section_title}
              onChange={(e) => setSettings((prev) => ({ ...prev, sidebar_section_title: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Ruta inicial</label>
            <select
              className="input"
              value={settings.default_route}
              onChange={(e) => setSettings((prev) => ({ ...prev, default_route: e.target.value }))}
            >
              {DEFAULT_ROUTES.map((route) => (
                <option key={route} value={route}>
                  {route}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="border rounded p-3">
            <h2 className="text-base font-semibold mb-2">Etiquetas de menú</h2>
            <div className="space-y-2">
              {NAV_KEYS.map(([key, label]) => (
                <div key={key}>
                  <label className="block text-xs text-gray-500 mb-1">{label}</label>
                  <input
                    className="input"
                    value={settings.nav_labels?.[key] || ''}
                    onChange={(e) => setNavLabel(key, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="border rounded p-3">
            <h2 className="text-base font-semibold mb-2">Títulos por página</h2>
            <div className="space-y-2">
              {PAGE_TITLE_KEYS.map(([key, label]) => (
                <div key={key}>
                  <label className="block text-xs text-gray-500 mb-1">{label}</label>
                  <input
                    className="input"
                    value={settings.page_titles?.[key] || ''}
                    onChange={(e) => setPageTitle(key, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <button className="btn" type="submit" disabled={saving || loading}>
            Guardar
          </button>
          <button className="px-3 py-2 rounded border" type="button" onClick={load} disabled={saving || loading}>
            Recargar
          </button>
        </div>
      </form>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}


