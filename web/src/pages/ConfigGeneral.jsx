import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  deleteUsuario,
  getPermisosCatalogo,
  getRetailConfigPaymentAccounts,
  getRetailConfigSettings,
  getUsuarioPermisos,
  getUsuarios,
  patchUsuarioActivo,
  patchUsuarioReset,
  patchUsuarioRolePerm,
  postUsuario,
  postUsuarioPermisosReset,
  putRetailConfigPaymentAccounts,
  putRetailConfigSettings,
  putUsuarioPermisos,
} from '../lib/api';

const EFFECT_LABELS = {
  inherit: 'Heredar',
  allow: 'Permitir',
  deny: 'Bloquear',
};

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function toBool(value) {
  return value === true || value === 'true' || value === 1 || value === '1';
}

export default function ConfigGeneral() {
  const { user, refreshSession } = useAuth();
  const [rows, setRows] = useState([]);
  const [settings, setSettings] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [form, setForm] = useState({ nombre: '', email: '', rol: 'empleado' });
  const [actionMenuUserId, setActionMenuUserId] = useState(null);

  const [permOpen, setPermOpen] = useState(false);
  const [permCatalog, setPermCatalog] = useState([]);
  const [permTarget, setPermTarget] = useState(null);
  const [permData, setPermData] = useState(null);
  const [permOverrides, setPermOverrides] = useState({});
  const [permSearch, setPermSearch] = useState('');
  const [permLoading, setPermLoading] = useState(false);
  const [permSaving, setPermSaving] = useState(false);
  const [permResetting, setPermResetting] = useState(false);
  const [permErr, setPermErr] = useState('');

  async function loadAll() {
    setLoading(true);
    setErr('');
    try {
      const [usersData, settingsData, accountsData] = await Promise.all([
        getUsuarios(),
        getRetailConfigSettings(),
        getRetailConfigPaymentAccounts(),
      ]);
      setRows(Array.isArray(usersData) ? usersData : []);
      setSettings(settingsData || {});
      setAccounts(Array.isArray(accountsData) ? accountsData : []);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    function onDocumentMouseDown(event) {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-user-actions-menu="true"]')) {
        return;
      }
      setActionMenuUserId(null);
    }

    document.addEventListener('mousedown', onDocumentMouseDown);
    return () => document.removeEventListener('mousedown', onDocumentMouseDown);
  }, []);

  useEffect(() => {
    if (actionMenuUserId == null) return;
    const stillExists = rows.some((row) => Number(row.id) === Number(actionMenuUserId));
    if (!stillExists) {
      setActionMenuUserId(null);
    }
  }, [rows, actionMenuUserId]);

  async function createUser(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const data = await postUsuario(form);
      setForm({ nombre: '', email: '', rol: 'empleado' });
      setMsg(data?.created ? 'Usuario creado' : 'Usuario actualizado');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(row) {
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchUsuarioActivo(row.id, !row.activo);
      setMsg('Estado de usuario actualizado');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function changeRole(row, rol) {
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchUsuarioRolePerm(row.id, { rol });
      setMsg('Rol actualizado');
      if (Number(row.id) === Number(user?.id)) {
        await refreshSession?.();
      }
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function resendRecoveryMail(row) {
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchUsuarioReset(row.id);
      setMsg('Se envio el mail de recuperacion');
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function deleteUser(row) {
    const label = row?.email || row?.nombre || `#${row?.id}`;
    if (!window.confirm(`Eliminar usuario ${label}?`)) {
      return;
    }

    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await deleteUsuario(row.id);
      setMsg('Usuario eliminado');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function saveSettings(e) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await putRetailConfigSettings({
        business_name: settings.business_name || undefined,
        iva_condition: settings.iva_condition || undefined,
        arca_env: settings.arca_env || undefined,
        arca_cuit: settings.arca_cuit || undefined,
        arca_pto_vta_store:
          settings.arca_pto_vta_store === '' || settings.arca_pto_vta_store == null
            ? undefined
            : Number(settings.arca_pto_vta_store),
        arca_pto_vta_online:
          settings.arca_pto_vta_online === '' || settings.arca_pto_vta_online == null
            ? undefined
            : Number(settings.arca_pto_vta_online),
        arca_cert_path: settings.arca_cert_path || undefined,
        arca_key_path: settings.arca_key_path || undefined,
        tiendanube_store_id:
          settings.tiendanube_store_id === '' || settings.tiendanube_store_id == null
            ? undefined
            : Number(settings.tiendanube_store_id),
        tiendanube_client_id: settings.tiendanube_client_id || undefined,
        tiendanube_client_secret: settings.tiendanube_client_secret || undefined,
        tiendanube_access_token: settings.tiendanube_access_token || undefined,
        tiendanube_webhook_secret: settings.tiendanube_webhook_secret || undefined,
        ticket_printer_name: settings.ticket_printer_name || undefined,
        label_printer_name: settings.label_printer_name || undefined,
        auto_invoice_online_paid: toBool(settings.auto_invoice_online_paid),
        return_warranty_size_days:
          settings.return_warranty_size_days === '' || settings.return_warranty_size_days == null
            ? undefined
            : Number(settings.return_warranty_size_days),
        return_warranty_breakage_days:
          settings.return_warranty_breakage_days === '' || settings.return_warranty_breakage_days == null
            ? undefined
            : Number(settings.return_warranty_breakage_days),
        purchase_default_markup_pct:
          settings.purchase_default_markup_pct === '' || settings.purchase_default_markup_pct == null
            ? undefined
            : Number(settings.purchase_default_markup_pct),
      });
      setMsg('Configuracion guardada');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function saveAccounts() {
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await putRetailConfigPaymentAccounts({
        accounts: accounts.map((a) => ({
          id: a.id,
          code: a.code,
          label: a.label,
          payment_method: a.payment_method || null,
          provider: a.provider || null,
          active: !!a.active,
          sort_order: Number(a.sort_order || 100),
        })),
      });
      setMsg('Cuentas de cobro guardadas');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  function updateAccount(idx, patch) {
    setAccounts((prev) => prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)));
  }

  async function ensurePermCatalog() {
    if (permCatalog.length) return permCatalog;
    const data = await getPermisosCatalogo();
    const list = Array.isArray(data?.permissions) ? data.permissions : [];
    setPermCatalog(list);
    return list;
  }

  async function openPermEditor(row) {
    setPermOpen(true);
    setPermLoading(true);
    setPermErr('');
    setPermTarget(row);
    setPermData(null);
    setPermOverrides({});
    setPermSearch('');
    try {
      await ensurePermCatalog();
      const data = await getUsuarioPermisos(row.id);
      setPermData(data || null);
      setPermOverrides({ ...(data?.overrides || {}) });
    } catch (error) {
      setPermErr(errMsg(error));
    } finally {
      setPermLoading(false);
    }
  }

  function closePermEditor() {
    setPermOpen(false);
    setPermTarget(null);
    setPermData(null);
    setPermOverrides({});
    setPermSearch('');
    setPermErr('');
    setPermLoading(false);
    setPermSaving(false);
    setPermResetting(false);
  }

  const modalEditable = Boolean(permData?.editable);
  const permTargetRole = String(permData?.user?.rol || '').toLowerCase();

  function isRoleLockedPermission(code) {
    return code === 'page.reportes' && permTargetRole !== 'admin';
  }

  const groupedPermissions = useMemo(() => {
    const list = Array.isArray(permCatalog) ? permCatalog : [];
    const needle = (permSearch || '').trim().toLowerCase();
    const groups = new Map();

    list.forEach((item) => {
      const text = `${item?.label || ''} ${item?.code || ''} ${item?.group || ''} ${item?.type || ''}`.toLowerCase();
      if (needle && !text.includes(needle)) return;

      const groupName = item?.group || 'Otros';
      if (!groups.has(groupName)) {
        groups.set(groupName, []);
      }
      groups.get(groupName).push(item);
    });

    return Array.from(groups.entries()).sort((a, b) =>
      a[0].localeCompare(b[0], 'es', { sensitivity: 'base' }),
    );
  }, [permCatalog, permSearch]);

  const permDirty = useMemo(() => {
    if (!permData) return false;
    const original = permData.overrides || {};
    const allCodes = (permCatalog || []).map((p) => p.code);
    return allCodes.some((code) => {
      const next = permOverrides?.[code] || 'inherit';
      const prev = original?.[code] || 'inherit';
      return next !== prev;
    });
  }, [permCatalog, permData, permOverrides]);

  function setOverride(code, effect) {
    setPermOverrides((prev) => ({ ...prev, [code]: effect }));
  }

  async function savePermisos() {
    if (!permTarget || !modalEditable) return;
    setPermSaving(true);
    setPermErr('');
    try {
      const data = await putUsuarioPermisos(permTarget.id, { overrides: permOverrides });
      setPermData(data || null);
      setPermOverrides({ ...(data?.overrides || {}) });
      setMsg('Permisos actualizados');
      if (Number(permTarget.id) === Number(user?.id)) {
        await refreshSession?.();
      }
      await loadAll();
    } catch (error) {
      setPermErr(errMsg(error));
    } finally {
      setPermSaving(false);
    }
  }

  async function resetPermisos() {
    if (!permTarget || !modalEditable) return;
    if (!window.confirm('Restablecer permisos personalizados del usuario?')) {
      return;
    }

    setPermResetting(true);
    setPermErr('');
    try {
      const data = await postUsuarioPermisosReset(permTarget.id);
      setPermData(data || null);
      setPermOverrides({ ...(data?.overrides || {}) });
      setMsg('Permisos restablecidos');
      if (Number(permTarget.id) === Number(user?.id)) {
        await refreshSession?.();
      }
      await loadAll();
    } catch (error) {
      setPermErr(errMsg(error));
    } finally {
      setPermResetting(false);
    }
  }

  if (loading && !settings) {
    return <div className="card">Cargando configuracion...</div>;
  }

  return (
    <>
      <div className="space-y-4">
        <div className="card">
          <h1 className="h1">Configuracion general</h1>
          <p className="text-sm text-gray-600">Usuarios, parametros fiscales ARCA, Tienda Nube y cuentas de cobro.</p>
          <Link to="/config/paginas" className="inline-block mt-2 text-sm font-semibold text-[#d9584b] hover:text-[#be4c41]">
            Ir a configuracion de paginas
          </Link>
        </div>

        <form className="card space-y-4" onSubmit={saveSettings}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Parametros del negocio e integraciones</h2>
              <p className="text-sm text-gray-600">Facturacion y Tienda Nube quedaron en bloques separados para una carga mas clara.</p>
            </div>
            <button className="btn" type="submit" disabled={saving}>
              Guardar parametros
            </button>
          </div>

          <section className="space-y-3 rounded-xl border border-gray-200 bg-white/60 p-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Negocio y operacion</h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <input
                className="input"
                placeholder="Nombre comercial"
                value={settings?.business_name || ''}
                onChange={(e) => setSettings((v) => ({ ...v, business_name: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Condicion IVA"
                value={settings?.iva_condition || ''}
                onChange={(e) => setSettings((v) => ({ ...v, iva_condition: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Impresora ticket"
                value={settings?.ticket_printer_name || ''}
                onChange={(e) => setSettings((v) => ({ ...v, ticket_printer_name: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Impresora etiquetas"
                value={settings?.label_printer_name || ''}
                onChange={(e) => setSettings((v) => ({ ...v, label_printer_name: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                min="1"
                placeholder="Garantia cambio de talle (dias)"
                value={settings?.return_warranty_size_days ?? 30}
                onChange={(e) => setSettings((v) => ({ ...v, return_warranty_size_days: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                min="1"
                placeholder="Garantia por roturas (dias)"
                value={settings?.return_warranty_breakage_days ?? 90}
                onChange={(e) => setSettings((v) => ({ ...v, return_warranty_breakage_days: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                placeholder="Margen compras por defecto (%)"
                value={settings?.purchase_default_markup_pct ?? 100}
                onChange={(e) => setSettings((v) => ({ ...v, purchase_default_markup_pct: e.target.value }))}
              />
            </div>
          </section>

          <section className="space-y-3 rounded-xl border border-gray-200 bg-white/60 p-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Facturacion (ARCA)</h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <select
                className="input"
                value={settings?.arca_env || 'homologacion'}
                onChange={(e) => setSettings((v) => ({ ...v, arca_env: e.target.value }))}
              >
                <option value="homologacion">ARCA homologacion</option>
                <option value="produccion">ARCA produccion</option>
              </select>
              <input
                className="input"
                placeholder="ARCA CUIT"
                value={settings?.arca_cuit || ''}
                onChange={(e) => setSettings((v) => ({ ...v, arca_cuit: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                placeholder="Pto vta local"
                value={settings?.arca_pto_vta_store || ''}
                onChange={(e) => setSettings((v) => ({ ...v, arca_pto_vta_store: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                placeholder="Pto vta online"
                value={settings?.arca_pto_vta_online || ''}
                onChange={(e) => setSettings((v) => ({ ...v, arca_pto_vta_online: e.target.value }))}
              />
              <input
                className="input"
                placeholder={
                  settings?.arca_cert_path_configured
                    ? `ARCA cert path (actual: ${settings?.arca_cert_path_masked || 'configurado'})`
                    : 'ARCA cert path'
                }
                value={settings?.arca_cert_path || ''}
                onChange={(e) => setSettings((v) => ({ ...v, arca_cert_path: e.target.value }))}
              />
              <input
                className="input"
                placeholder={
                  settings?.arca_key_path_configured
                    ? `ARCA key path (actual: ${settings?.arca_key_path_masked || 'configurado'})`
                    : 'ARCA key path'
                }
                value={settings?.arca_key_path || ''}
                onChange={(e) => setSettings((v) => ({ ...v, arca_key_path: e.target.value }))}
              />
              <label className="inline-flex min-h-[42px] items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 text-sm">
                <input
                  type="checkbox"
                  checked={toBool(settings?.auto_invoice_online_paid)}
                  onChange={(e) => setSettings((v) => ({ ...v, auto_invoice_online_paid: e.target.checked }))}
                />
                Facturar online automaticamente
              </label>
            </div>
          </section>

          <section className="space-y-3 rounded-xl border border-gray-200 bg-white/60 p-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Integracion Tienda Nube</h3>
            <p className="text-xs text-gray-500">Estos campos son solo para el enlace de tienda online y webhooks.</p>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <input
                className="input"
                type="number"
                placeholder="Tienda Nube store_id"
                value={settings?.tiendanube_store_id || ''}
                onChange={(e) => setSettings((v) => ({ ...v, tiendanube_store_id: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Tienda Nube client_id"
                value={settings?.tiendanube_client_id || ''}
                onChange={(e) => setSettings((v) => ({ ...v, tiendanube_client_id: e.target.value }))}
              />
              <input
                className="input"
                placeholder={
                  settings?.tiendanube_client_secret_configured
                    ? `Tienda Nube client_secret (actual: ${settings?.tiendanube_client_secret_masked || 'configurado'})`
                    : 'Tienda Nube client_secret'
                }
                value={settings?.tiendanube_client_secret || ''}
                onChange={(e) => setSettings((v) => ({ ...v, tiendanube_client_secret: e.target.value }))}
              />
              <input
                className="input"
                placeholder={
                  settings?.tiendanube_access_token_configured
                    ? `Tienda Nube access_token (actual: ${settings?.tiendanube_access_token_masked || 'configurado'})`
                    : 'Tienda Nube access_token'
                }
                value={settings?.tiendanube_access_token || ''}
                onChange={(e) => setSettings((v) => ({ ...v, tiendanube_access_token: e.target.value }))}
              />
              <input
                className="input md:col-span-2"
                placeholder={
                  settings?.tiendanube_webhook_secret_configured
                    ? `Tienda Nube webhook secret (actual: ${settings?.tiendanube_webhook_secret_masked || 'configurado'})`
                    : 'Tienda Nube webhook secret (client_secret)'
                }
                value={settings?.tiendanube_webhook_secret || ''}
                onChange={(e) => setSettings((v) => ({ ...v, tiendanube_webhook_secret: e.target.value }))}
              />
            </div>
          </section>

          <button className="btn" type="submit" disabled={saving}>
            Guardar parametros
          </button>
        </form>

        <div className="card space-y-3">
          <h2 className="text-lg font-semibold">Cuentas de cobro</h2>
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">Code</th>
                  <th className="py-2 pr-3">Label</th>
                  <th className="py-2 pr-3">Metodo</th>
                  <th className="py-2 pr-3">Provider</th>
                  <th className="py-2 pr-3">Orden</th>
                  <th className="py-2 pr-3">Activa</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((row, idx) => (
                  <tr key={row.id || idx} className="border-b last:border-b-0">
                    <td className="py-2 pr-3">{row.code}</td>
                    <td className="py-2 pr-3">
                      <input
                        className="input"
                        value={row.label || ''}
                        onChange={(e) => updateAccount(idx, { label: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <select
                        className="input"
                        value={row.payment_method || ''}
                        onChange={(e) => updateAccount(idx, { payment_method: e.target.value || null })}
                      >
                        <option value="">-</option>
                        <option value="cash">cash</option>
                        <option value="debit">debit</option>
                        <option value="transfer">transfer</option>
                        <option value="credit">credit</option>
                      </select>
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        className="input"
                        value={row.provider || ''}
                        onChange={(e) => updateAccount(idx, { provider: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        className="input"
                        type="number"
                        value={row.sort_order || 100}
                        onChange={(e) => updateAccount(idx, { sort_order: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="checkbox"
                        checked={!!row.active}
                        onChange={(e) => updateAccount(idx, { active: e.target.checked })}
                      />
                    </td>
                  </tr>
                ))}
                {!accounts.length ? (
                  <tr>
                    <td className="py-3 text-gray-500" colSpan={6}>Sin cuentas</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <button className="btn" type="button" onClick={saveAccounts} disabled={saving || !accounts.length}>
            Guardar cuentas
          </button>
        </div>

        <form className="card space-y-3" onSubmit={createUser}>
          <h2 className="text-lg font-semibold">Nuevo usuario</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <input
              className="input"
              placeholder="Nombre"
              value={form.nombre}
              onChange={(e) => setForm((v) => ({ ...v, nombre: e.target.value }))}
              required
            />
            <input
              className="input"
              type="email"
              placeholder="Email"
              value={form.email}
              onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))}
              required
            />
            <select className="input" value={form.rol} onChange={(e) => setForm((v) => ({ ...v, rol: e.target.value }))}>
              <option value="empleado">Empleado</option>
              <option value="admin">Admin</option>
            </select>
            <button className="btn" type="submit" disabled={saving}>
              Guardar usuario
            </button>
          </div>
        </form>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">Usuarios</h2>
            <button className="px-3 py-2 rounded border" type="button" onClick={loadAll} disabled={loading}>
              Actualizar
            </button>
          </div>
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">Nombre</th>
                  <th className="py-2 pr-3">Email</th>
                  <th className="py-2 pr-3">Rol</th>
                  <th className="py-2 pr-3">Perm.</th>
                  <th className="py-2 pr-3">Activo</th>
                  <th className="py-2 pr-3">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b last:border-b-0">
                    <td className="py-2 pr-3">{row.nombre}</td>
                    <td className="py-2 pr-3">{row.email}</td>
                    <td className="py-2 pr-3">
                      <select
                        className="input"
                        value={row.rol}
                        onChange={(e) => changeRole(row, e.target.value)}
                        disabled={saving}
                      >
                        <option value="empleado">Empleado</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="py-2 pr-3">
                      <span className="inline-flex min-w-8 justify-center rounded border bg-neutral-100 px-2 py-1 text-xs font-semibold">
                        {Number(row?.permisos_personalizados || 0)}
                      </span>
                    </td>
                    <td className="py-2 pr-3">{row.activo ? 'Si' : 'No'}</td>
                    <td className="py-2 pr-3">
                      <div className="relative inline-block" data-user-actions-menu="true">
                        <button
                          type="button"
                          className="h-8 w-8 rounded border text-lg leading-none hover:bg-neutral-100"
                          aria-label="Abrir menu de acciones"
                          aria-expanded={Number(actionMenuUserId) === Number(row.id)}
                          onClick={() =>
                            setActionMenuUserId((prev) =>
                              Number(prev) === Number(row.id) ? null : row.id
                            )
                          }
                          disabled={saving}
                        >
                          {'\u22EE'}
                        </button>

                        {Number(actionMenuUserId) === Number(row.id) ? (
                          <div className="absolute right-0 z-30 mt-1 w-48 rounded-lg border border-neutral-200 bg-white py-1 shadow-lg">
                            <button
                              className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100"
                              type="button"
                              onClick={() => {
                                setActionMenuUserId(null);
                                toggleActive(row);
                              }}
                              disabled={saving}
                            >
                              {row.activo ? 'Desactivar' : 'Activar'}
                            </button>
                            <button
                              className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100"
                              type="button"
                              onClick={() => {
                                setActionMenuUserId(null);
                                openPermEditor(row);
                              }}
                              disabled={saving}
                            >
                              Permisos personalizados
                            </button>
                            <button
                              className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100 disabled:text-neutral-400"
                              type="button"
                              onClick={() => {
                                setActionMenuUserId(null);
                                resendRecoveryMail(row);
                              }}
                              disabled={saving || !row.activo}
                            >
                              Reenviar mail
                            </button>
                            <button
                              className="block w-full px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50"
                              type="button"
                              onClick={() => {
                                setActionMenuUserId(null);
                                deleteUser(row);
                              }}
                              disabled={saving}
                            >
                              Eliminar
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
                {!rows.length ? (
                  <tr>
                    <td className="py-3 text-gray-500" colSpan={6}>Sin usuarios</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        {err ? <p className="text-sm text-red-700">{err}</p> : null}
        {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
      </div>

      {permOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={closePermEditor}
        >
          <div
            className="card w-full max-w-6xl max-h-[88vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-3 border-b border-neutral-200 pb-3">
              <div>
                <h3 className="text-lg font-semibold">Editar permisos</h3>
                <p className="text-sm text-neutral-600">
                  {permTarget ? `${permTarget.nombre} (${permTarget.email})` : '-'}
                </p>
              </div>
              <button type="button" className="btn-secondary px-3 py-1.5" onClick={closePermEditor}>
                Cerrar
              </button>
            </div>

            <div className="space-y-3 overflow-auto max-h-[calc(88vh-120px)] pr-1">
              {permErr ? (
                <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {permErr}
                </div>
              ) : null}

              {permLoading ? (
                <p className="text-sm text-neutral-600">Cargando permisos...</p>
              ) : (
                <>
                  {!modalEditable && permData ? (
                    <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      Este usuario no permite edicion granular (rol admin).
                    </div>
                  ) : null}
                  {modalEditable && permTargetRole !== 'admin' ? (
                    <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      El permiso <code>page.reportes</code> esta bloqueado por politica de rol (solo admin).
                    </div>
                  ) : null}

                  <div className="flex flex-col gap-3 md:flex-row md:items-center">
                    <input
                      type="text"
                      className="input w-full md:max-w-md"
                      placeholder="Buscar permiso por nombre, codigo o grupo"
                      value={permSearch}
                      onChange={(e) => setPermSearch(e.target.value)}
                    />
                    <div className="text-xs text-neutral-500">
                      {groupedPermissions.reduce((acc, [, items]) => acc + items.length, 0)} permiso(s)
                    </div>
                    <div className="md:ml-auto flex gap-2">
                      <button
                        className="btn-secondary"
                        type="button"
                        onClick={resetPermisos}
                        disabled={!modalEditable || permResetting}
                      >
                        {permResetting ? 'Reseteando...' : 'Reset'}
                      </button>
                      <button
                        className="btn"
                        type="button"
                        onClick={savePermisos}
                        disabled={!modalEditable || permSaving || !permDirty}
                      >
                        {permSaving ? 'Guardando...' : 'Guardar'}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {groupedPermissions.map(([groupName, items]) => (
                      <div key={groupName} className="rounded-xl border border-neutral-200 overflow-hidden">
                        <div className="bg-neutral-50 px-3 py-2 text-sm font-semibold border-b border-neutral-200">
                          {groupName}
                        </div>
                        <div className="divide-y divide-neutral-200">
                          {items.map((item) => {
                            const code = item.code;
                            const override = permOverrides?.[code] || 'inherit';
                            const effective = !!permData?.effective_permissions?.[code];
                            const roleLocked = isRoleLockedPermission(code);
                            return (
                              <div key={code} className="px-3 py-2 flex flex-col gap-2 md:flex-row md:items-center">
                                <div className="min-w-0 flex-1">
                                  <div className="text-sm font-medium">{item.label || code}</div>
                                  <div className="text-xs text-neutral-500">{code}</div>
                                  {roleLocked ? (
                                    <div className="text-xs text-amber-700">Bloqueado por politica de rol.</div>
                                  ) : null}
                                </div>
                                <div>
                                  <span
                                    className={[
                                      'inline-flex rounded border px-2 py-1 text-xs',
                                      effective
                                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                        : 'border-red-200 bg-red-50 text-red-700',
                                    ].join(' ')}
                                  >
                                    {effective ? 'Efectivo: permitido' : 'Efectivo: bloqueado'}
                                  </span>
                                </div>
                                <div className="w-full md:w-48">
                                  <select
                                    className="input text-sm"
                                    value={override}
                                    disabled={!modalEditable || roleLocked}
                                    onChange={(e) => setOverride(code, e.target.value)}
                                  >
                                    <option value="inherit">{EFFECT_LABELS.inherit}</option>
                                    <option value="allow">{EFFECT_LABELS.allow}</option>
                                    <option value="deny">{EFFECT_LABELS.deny}</option>
                                  </select>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}

                    {!groupedPermissions.length ? (
                      <p className="text-sm text-neutral-500">No hay permisos para el filtro actual.</p>
                    ) : null}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
