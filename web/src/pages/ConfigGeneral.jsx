import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { useAuth } from '../context/AuthContext';
import {
  deleteUsuario,
  getRetailConfigArcaAccounts,
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
  postRetailOnlineOAuthApplyToken,
  postRetailOnlineOAuthReauthorizeUrl,
  putRetailConfigArcaAccounts,
  putRetailConfigPaymentAccounts,
  putRetailConfigSettings,
  putUsuarioPermisos,
} from '../lib/api';
import { can, PERMISSION_CODES } from '../lib/permissions';

const EFFECT_LABELS = {
  inherit: 'Heredar',
  allow: 'Permitir',
  deny: 'Bloquear',
};

const ARCA_HELP_LINKS = [
  {
    id: 'acciones',
    label: 'Pasos oficiales ARCA',
    url: 'https://www.afip.gob.ar/fe/documentos/AccionesarealizarparaconsumirunWebservicedeFacturaElectr.pdf',
  },
  {
    id: 'wsass',
    label: 'Manual WSASS (homologacion)',
    url: 'https://www.afip.gob.ar/ws/WSASS/html/index.html',
  },
  {
    id: 'wsfe',
    label: 'Manuales WS Factura Electronica',
    url: 'https://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp',
  },
  {
    id: 'asociar',
    label: 'Asociar certificado a WSN',
    url: 'https://www.afip.gob.ar/ws/WSAA/wsaa_asociar_certificado_a_wsn_produccion.pdf',
  },
];

function errMsg(error) {
  const detail = error?.data?.detail;
  const hint = error?.data?.hint;
  if (detail && hint) return `${detail} ${hint}`;
  if (detail) return detail;
  return error?.message || 'Ocurrio un error inesperado';
}
function toBool(value) {
  return value === true || value === 'true' || value === 1 || value === '1';
}

const ACTION_MENU_WIDTH = 192;
const ACTION_MENU_HEIGHT = 188;
const ACTION_MENU_GAP = 6;
const ACTION_MENU_MARGIN = 8;

export default function ConfigGeneral() {
  const { user, refreshSession } = useAuth();
  const [rows, setRows] = useState([]);
  const [settings, setSettings] = useState(null);
  const [arcaAccounts, setArcaAccounts] = useState([]);
  const [arcaRotation, setArcaRotation] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [form, setForm] = useState({ nombre: '', email: '', rol: 'empleado' });
  const [actionMenuUserId, setActionMenuUserId] = useState(null);
  const [actionMenuPos, setActionMenuPos] = useState(null);

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
  const actionMenuFirstButtonRef = useRef(null);
  const [oauthForm, setOauthForm] = useState({
    store_id: '',
    access_token: '',
    webhook_secret: '',
  });
  const [oauthSaving, setOauthSaving] = useState(false);

  const canEditBusinessSettings = can(user, PERMISSION_CODES.ACTION_CONFIG_EDITAR);
  const canEditOnlineCredentials = can(user, PERMISSION_CODES.ACTION_CONFIG_ONLINE_CREDENTIALS);
  const canSaveSettings = canEditBusinessSettings || canEditOnlineCredentials;
  const actionMenuRow = useMemo(
    () => rows.find((row) => Number(row.id) === Number(actionMenuUserId)) || null,
    [rows, actionMenuUserId],
  );

  function closeActionMenu() {
    setActionMenuUserId(null);
    setActionMenuPos(null);
  }

  function calcActionMenuPosition(anchorRect) {
    if (!anchorRect) return null;
    const viewportW = window.innerWidth || 0;
    const viewportH = window.innerHeight || 0;

    const left = Math.max(
      ACTION_MENU_MARGIN,
      Math.min(viewportW - ACTION_MENU_WIDTH - ACTION_MENU_MARGIN, anchorRect.right - ACTION_MENU_WIDTH),
    );

    const openUpwards =
      anchorRect.bottom + ACTION_MENU_GAP + ACTION_MENU_HEIGHT > viewportH - ACTION_MENU_MARGIN &&
      anchorRect.top - ACTION_MENU_GAP - ACTION_MENU_HEIGHT >= ACTION_MENU_MARGIN;

    const top = openUpwards
      ? Math.max(ACTION_MENU_MARGIN, anchorRect.top - ACTION_MENU_HEIGHT - ACTION_MENU_GAP)
      : Math.max(
          ACTION_MENU_MARGIN,
          Math.min(viewportH - ACTION_MENU_HEIGHT - ACTION_MENU_MARGIN, anchorRect.bottom + ACTION_MENU_GAP),
        );

    return { top, left };
  }

  function toggleActionMenu(userId, triggerEl) {
    if (!triggerEl) return;
    const nextId = Number(userId);
    if (Number(actionMenuUserId) === nextId) {
      closeActionMenu();
      return;
    }
    const pos = calcActionMenuPosition(triggerEl.getBoundingClientRect());
    setActionMenuUserId(nextId);
    setActionMenuPos(pos);
  }

  async function loadAll() {
    setLoading(true);
    setErr('');
    try {
      const [usersData, settingsData, arcaData, accountsData] = await Promise.all([
        getUsuarios(),
        getRetailConfigSettings(),
        getRetailConfigArcaAccounts(),
        getRetailConfigPaymentAccounts(),
      ]);
      setRows(Array.isArray(usersData) ? usersData : []);
      setSettings(settingsData || {});
      setArcaAccounts(Array.isArray(arcaData?.accounts) ? arcaData.accounts : []);
      setArcaRotation(arcaData?.rotation || null);
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
    if (!settings) return;
    setOauthForm((prev) => {
      const nextStoreId = settings?.tiendanube_store_id ? String(settings.tiendanube_store_id) : '';
      if (prev.store_id || !nextStoreId) return prev;
      return { ...prev, store_id: nextStoreId };
    });
  }, [settings?.tiendanube_store_id]);
  useEffect(() => {
    function onDocumentMouseDown(event) {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-user-actions-menu="true"]')) {
        return;
      }
      closeActionMenu();
    }

    document.addEventListener('mousedown', onDocumentMouseDown);
    return () => document.removeEventListener('mousedown', onDocumentMouseDown);
  }, []);
  useEffect(() => {
    if (actionMenuUserId == null) return;
    const stillExists = rows.some((row) => Number(row.id) === Number(actionMenuUserId));
    if (!stillExists) {
      closeActionMenu();
    }
  }, [rows, actionMenuUserId]);

  useEffect(() => {
    if (actionMenuUserId == null) return undefined;
    function closeOnViewportChange() {
      closeActionMenu();
    }
    window.addEventListener('resize', closeOnViewportChange);
    window.addEventListener('scroll', closeOnViewportChange, true);
    return () => {
      window.removeEventListener('resize', closeOnViewportChange);
      window.removeEventListener('scroll', closeOnViewportChange, true);
    };
  }, [actionMenuUserId]);

  useEffect(() => {
    if (!actionMenuRow || !actionMenuPos) return undefined;
    const timer = window.setTimeout(() => {
      actionMenuFirstButtonRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [actionMenuRow, actionMenuPos]);

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
      const data = await patchUsuarioReset(row.id);
      setMsg(data?.detail || 'Mail de recuperacion enviado correctamente');
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
    if (!canSaveSettings) {
      setErr('No tenes permisos para editar esta configuracion.');
      return;
    }
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const payload = {};
      if (canEditBusinessSettings) {
        payload.business_name = settings.business_name || undefined;
        payload.iva_condition = settings.iva_condition || undefined;
        payload.arca_env = settings.arca_env || undefined;
        payload.ticket_printer_name = settings.ticket_printer_name || undefined;
        payload.label_printer_name = settings.label_printer_name || undefined;
        payload.ean_country_prefix = settings.ean_country_prefix || undefined;
        payload.ean_generic_supplier_code = settings.ean_generic_supplier_code || undefined;
        payload.auto_invoice_online_paid = toBool(settings.auto_invoice_online_paid);
        payload.return_warranty_size_days =
          settings.return_warranty_size_days === '' || settings.return_warranty_size_days == null
            ? undefined
            : Number(settings.return_warranty_size_days);
        payload.return_warranty_breakage_days =
          settings.return_warranty_breakage_days === '' || settings.return_warranty_breakage_days == null
            ? undefined
            : Number(settings.return_warranty_breakage_days);
        payload.purchase_default_markup_pct =
          settings.purchase_default_markup_pct === '' || settings.purchase_default_markup_pct == null
            ? undefined
            : Number(settings.purchase_default_markup_pct);
      }

      if (canEditOnlineCredentials) {
        payload.tiendanube_store_id =
          settings.tiendanube_store_id === '' || settings.tiendanube_store_id == null
            ? undefined
            : Number(settings.tiendanube_store_id);
        payload.tiendanube_client_id = settings.tiendanube_client_id || undefined;
        payload.tiendanube_client_secret = settings.tiendanube_client_secret || undefined;
        payload.tiendanube_access_token = settings.tiendanube_access_token || undefined;
        payload.tiendanube_webhook_secret = settings.tiendanube_webhook_secret || undefined;
      }

      const hasChanges = Object.keys(payload).some((key) => payload[key] !== undefined);
      if (!hasChanges) {
        setErr('No hay campos permitidos para guardar con tu perfil.');
        return;
      }

      await putRetailConfigSettings(payload);
      setMsg('Configuracion guardada');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function saveAccounts() {
    if (!canEditBusinessSettings) {
      setErr('No tenes permisos para editar cuentas de cobro.');
      return;
    }
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

  async function saveArcaAccounts() {
    if (!canEditBusinessSettings && !canEditOnlineCredentials) {
      setErr('No tenes permisos para editar cuentas ARCA.');
      return;
    }
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await putRetailConfigArcaAccounts({
        accounts: arcaAccounts.map((account) => {
          const payload = {
            id: account.id,
            code: account.code,
          };
          if (canEditBusinessSettings) {
            payload.label = account.label || '';
            payload.active = !!account.active;
            payload.sort_order =
              account.sort_order === '' || account.sort_order == null ? 100 : Number(account.sort_order);
            payload.arca_cuit = account.arca_cuit === '' ? null : account.arca_cuit || undefined;
            payload.arca_pto_vta_store =
              account.arca_pto_vta_store === ''
                ? null
                : account.arca_pto_vta_store == null
                  ? undefined
                : Number(account.arca_pto_vta_store);
            payload.arca_pto_vta_online =
              account.arca_pto_vta_online === ''
                ? null
                : account.arca_pto_vta_online == null
                  ? undefined
                : Number(account.arca_pto_vta_online);
            payload.arca_cbte_tipo_store =
              account.arca_cbte_tipo_store === ''
                ? null
                : account.arca_cbte_tipo_store == null
                  ? undefined
                : Number(account.arca_cbte_tipo_store);
            payload.arca_cbte_tipo_online =
              account.arca_cbte_tipo_online === ''
                ? null
                : account.arca_cbte_tipo_online == null
                  ? undefined
                : Number(account.arca_cbte_tipo_online);
          }
          if (canEditOnlineCredentials) {
            payload.arca_cert_path = account.arca_cert_path === '' ? null : account.arca_cert_path || undefined;
            payload.arca_key_path = account.arca_key_path === '' ? null : account.arca_key_path || undefined;
          }
          return payload;
        }),
      });
      setMsg('Cuentas ARCA guardadas');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function openTiendaNubeReauthorize() {
    if (!canEditOnlineCredentials) return;
    setOauthSaving(true);
    setErr('');
    setMsg('');
    try {
      const data = await postRetailOnlineOAuthReauthorizeUrl({});
      const url = data?.authorize_url || '';
      if (!url) {
        throw new Error('No se pudo generar URL de autorizacion.');
      }
      window.open(url, '_blank', 'noopener,noreferrer');
      setMsg('Se abrio la autorizacion de Tienda Nube en una nueva pestana.');
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setOauthSaving(false);
    }
  }

  async function applyTiendaNubeToken() {
    if (!canEditOnlineCredentials) return;
    setOauthSaving(true);
    setErr('');
    setMsg('');
    try {
      const storeIdRaw = String(oauthForm.store_id || '').trim();
      const accessToken = String(oauthForm.access_token || '').trim();
      if (!storeIdRaw || !accessToken) {
        throw new Error('Completa store_id y access_token para aplicar el token.');
      }
      await postRetailOnlineOAuthApplyToken({
        store_id: Number(storeIdRaw),
        access_token: accessToken,
        webhook_secret: String(oauthForm.webhook_secret || '').trim() || undefined,
      });
      setOauthForm((prev) => ({ ...prev, access_token: '', webhook_secret: '' }));
      setMsg('Token online aplicado correctamente.');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setOauthSaving(false);
    }
  }

  function openArcaHelp(link) {
    if (!link?.url) return;
    setErr('');
    window.open(link.url, '_blank', 'noopener,noreferrer');
    setMsg(`Se abrio "${link.label}" en una nueva pestana.`);
  }

  function updateArcaAccount(idx, patch) {
    setArcaAccounts((prev) => prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)));
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
  const roleLockedPermissions = useMemo(
    () => new Set(Array.isArray(permData?.role_locked_permissions) ? permData.role_locked_permissions : []),
    [permData],
  );

  function isRoleLockedPermission(code) {
    return roleLockedPermissions.has(code);
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
              {!canSaveSettings ? (
                <p className="mt-1 text-xs text-amber-700">
                  Tu usuario tiene acceso de lectura en esta seccion. Para editar, se requiere permiso tecnico.
                </p>
              ) : null}
            </div>
            <button className="btn" type="submit" disabled={saving || !canSaveSettings}>
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
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, business_name: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Condicion IVA"
                value={settings?.iva_condition || ''}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, iva_condition: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Impresora ticket"
                value={settings?.ticket_printer_name || ''}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, ticket_printer_name: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Impresora etiquetas"
                value={settings?.label_printer_name || ''}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, label_printer_name: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Prefijo pais EAN-13 (ej 779)"
                value={settings?.ean_country_prefix || '779'}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, ean_country_prefix: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Codigo proveedor generico (0000)"
                value={settings?.ean_generic_supplier_code || '0000'}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, ean_generic_supplier_code: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                min="1"
                placeholder="Garantia cambio de talle (dias)"
                value={settings?.return_warranty_size_days ?? 30}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, return_warranty_size_days: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                min="1"
                placeholder="Garantia por roturas (dias)"
                value={settings?.return_warranty_breakage_days ?? 90}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, return_warranty_breakage_days: e.target.value }))}
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                placeholder="Margen compras por defecto (%)"
                value={settings?.purchase_default_markup_pct ?? 100}
                disabled={!canEditBusinessSettings}
                onChange={(e) => setSettings((v) => ({ ...v, purchase_default_markup_pct: e.target.value }))}
              />
            </div>
          </section>

          <section className="space-y-3 rounded-xl border border-gray-200 bg-white/60 p-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Facturacion (ARCA)</h3>
            <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-3">
              <h4 className="text-sm font-semibold">Guia de alta ARCA para clientas</h4>
              <p className="text-xs text-gray-500">
                Para emitir en modo real hay que completar certificacion, asociacion al WSN y punto de venta fiscal.
                Usa estos tutoriales oficiales para reunir la informacion antes de cargar los campos en RH.
              </p>
              <div className="flex flex-wrap gap-2">
                {ARCA_HELP_LINKS.map((link) => (
                  <button
                    key={link.id}
                    className="btn-secondary"
                    type="button"
                    onClick={() => openArcaHelp(link)}
                  >
                    {link.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-3">
              <h4 className="text-sm font-semibold">Entorno ARCA</h4>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <select
                  className="input"
                  value={settings?.arca_env || 'homologacion'}
                  disabled={!canEditBusinessSettings}
                  onChange={(e) => setSettings((v) => ({ ...v, arca_env: e.target.value }))}
                >
                  <option value="homologacion">ARCA homologacion</option>
                  <option value="produccion">ARCA produccion</option>
                </select>
                <label className="inline-flex min-h-[42px] items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 text-sm">
                  <input
                    type="checkbox"
                    checked={toBool(settings?.auto_invoice_online_paid)}
                    disabled={!canEditBusinessSettings}
                    onChange={(e) => setSettings((v) => ({ ...v, auto_invoice_online_paid: e.target.checked }))}
                  />
                  Facturar online automaticamente
                </label>
              </div>
              <div className="text-xs text-gray-500">
                Ultima cuenta usada:{' '}
                <strong>{arcaRotation?.last_account_label || arcaRotation?.last_account_code || 'sin uso'}</strong>. Proxima:{' '}
                <strong>{arcaRotation?.next_account_label || arcaRotation?.next_account_code || 'sin cuenta activa'}</strong>.
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {arcaAccounts.map((account, idx) => (
                <section key={account.id || account.code || idx} className="rounded-lg border border-gray-200 bg-white p-3 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-semibold">Cuenta {idx === 0 ? 'A' : 'B'}</h4>
                      <p className="text-xs text-gray-500">{account.label || account.code || 'Cuenta ARCA'}</p>
                      <p className="text-[11px] uppercase tracking-wide text-gray-400">{account.code || 'sin codigo'}</p>
                    </div>
                    <label className="inline-flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={!!account.active}
                        disabled={!canEditBusinessSettings}
                        onChange={(e) => updateArcaAccount(idx, { active: e.target.checked })}
                      />
                      Activa
                    </label>
                  </div>

                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <input
                      className="input"
                      placeholder="Etiqueta visible"
                      value={account.label || ''}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { label: e.target.value })}
                    />
                    <input
                      className="input"
                      placeholder="CUIT emisor"
                      value={account.arca_cuit || ''}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { arca_cuit: e.target.value })}
                    />
                    <input
                      className="input"
                      type="number"
                      placeholder="Pto vta local"
                      value={account.arca_pto_vta_store ?? ''}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { arca_pto_vta_store: e.target.value })}
                    />
                    <input
                      className="input"
                      type="number"
                      placeholder="Pto vta online"
                      value={account.arca_pto_vta_online ?? ''}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { arca_pto_vta_online: e.target.value })}
                    />
                    <input
                      className="input"
                      type="number"
                      placeholder="Cbte tipo local"
                      value={account.arca_cbte_tipo_store ?? ''}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { arca_cbte_tipo_store: e.target.value })}
                    />
                    <input
                      className="input"
                      type="number"
                      placeholder="Cbte tipo online"
                      value={account.arca_cbte_tipo_online ?? ''}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { arca_cbte_tipo_online: e.target.value })}
                    />
                    <input
                      className="input"
                      type="number"
                      placeholder="Orden"
                      value={account.sort_order ?? 100}
                      disabled={!canEditBusinessSettings}
                      onChange={(e) => updateArcaAccount(idx, { sort_order: e.target.value })}
                    />
                    <div className="rounded-lg border border-dashed border-gray-200 px-3 py-2 text-xs text-gray-500">
                      Emisor fiscal:{' '}
                      <strong>{account.issuer_cuit || account.arca_cuit || 'sin configurar'}</strong>
                    </div>
                    <input
                      className="input md:col-span-2"
                      placeholder={
                        account?.arca_cert_path_configured
                          ? `Cert path (actual: ${account?.arca_cert_path_masked || 'configurado'})`
                          : 'Cert path'
                      }
                      value={account.arca_cert_path || ''}
                      disabled={!canEditOnlineCredentials}
                      onChange={(e) => updateArcaAccount(idx, { arca_cert_path: e.target.value })}
                    />
                    <input
                      className="input md:col-span-2"
                      placeholder={
                        account?.arca_key_path_configured
                          ? `Key path (actual: ${account?.arca_key_path_masked || 'configurado'})`
                          : 'Key path'
                      }
                      value={account.arca_key_path || ''}
                      disabled={!canEditOnlineCredentials}
                      onChange={(e) => updateArcaAccount(idx, { arca_key_path: e.target.value })}
                    />
                  </div>
                </section>
              ))}
            </div>
            <button
              className="btn"
              type="button"
              onClick={saveArcaAccounts}
              disabled={saving || !arcaAccounts.length || (!canEditBusinessSettings && !canEditOnlineCredentials)}
            >
              Guardar cuentas ARCA
            </button>
          </section>

          <section className="space-y-3 rounded-xl border border-gray-200 bg-white/60 p-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Integracion Tienda Nube</h3>
            <p className="text-xs text-gray-500">Estos campos son solo para el enlace de tienda online y webhooks.</p>
            <div className="grid grid-cols-1 gap-3 rounded-lg border border-gray-200 bg-white p-3 md:grid-cols-2">
              <div className="text-sm">
                <span className="font-semibold">store_id:</span> {settings?.tiendanube_store_id || 'sin configurar'}
              </div>
              <div className="text-sm">
                <span className="font-semibold">client_id:</span> {settings?.tiendanube_client_id || 'sin configurar'}
              </div>
              <div className="text-sm">
                <span className="font-semibold">client_secret:</span>{' '}
                {settings?.tiendanube_client_secret_configured ? 'configurado' : 'no configurado'}
              </div>
              <div className="text-sm">
                <span className="font-semibold">access_token:</span>{' '}
                {settings?.tiendanube_access_token_configured ? 'configurado' : 'no configurado'}
              </div>
              <div className="text-sm md:col-span-2">
                <span className="font-semibold">webhook_secret:</span>{' '}
                {settings?.tiendanube_webhook_secret_configured ? 'configurado' : 'no configurado'}
              </div>
            </div>

            {canEditOnlineCredentials ? (
              <>
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
                      settings?.tiendanube_webhook_secret_configured
                        ? `Tienda Nube webhook secret (actual: ${settings?.tiendanube_webhook_secret_masked || 'configurado'})`
                        : 'Tienda Nube webhook secret (client_secret)'
                    }
                    value={settings?.tiendanube_webhook_secret || ''}
                    onChange={(e) => setSettings((v) => ({ ...v, tiendanube_webhook_secret: e.target.value }))}
                  />
                  <input
                    className="input md:col-span-2"
                    placeholder={
                      settings?.tiendanube_access_token_configured
                        ? `Tienda Nube access_token (actual: ${settings?.tiendanube_access_token_masked || 'configurado'})`
                        : 'Tienda Nube access_token'
                    }
                    value={settings?.tiendanube_access_token || ''}
                    onChange={(e) => setSettings((v) => ({ ...v, tiendanube_access_token: e.target.value }))}
                  />
                </div>

                <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-3">
                  <h4 className="text-sm font-semibold">Flujo tecnico OAuth</h4>
                  <p className="text-xs text-gray-500">
                    1) Reautoriza en Tienda Nube. 2) Pega store_id y access_token del cURL. 3) Aplica token.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn-secondary" type="button" onClick={openTiendaNubeReauthorize} disabled={oauthSaving}>
                      Reautorizar Tienda Nube
                    </button>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <input
                      className="input"
                      placeholder="store_id"
                      value={oauthForm.store_id}
                      onChange={(e) => setOauthForm((v) => ({ ...v, store_id: e.target.value }))}
                    />
                    <input
                      className="input md:col-span-2"
                      placeholder="access_token"
                      value={oauthForm.access_token}
                      onChange={(e) => setOauthForm((v) => ({ ...v, access_token: e.target.value }))}
                    />
                    <input
                      className="input md:col-span-2"
                      placeholder="webhook_secret opcional (si rota)"
                      value={oauthForm.webhook_secret}
                      onChange={(e) => setOauthForm((v) => ({ ...v, webhook_secret: e.target.value }))}
                    />
                    <button className="btn" type="button" onClick={applyTiendaNubeToken} disabled={oauthSaving}>
                      Aplicar token
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-xs text-amber-700">
                Este bloque es de solo lectura. Las credenciales online sensibles se gestionan con usuario tecnico.
              </p>
            )}
          </section>

          <button className="btn" type="submit" disabled={saving || !canSaveSettings}>
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
                        disabled={!canEditBusinessSettings}
                        onChange={(e) => updateAccount(idx, { label: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <select
                        className="input"
                        value={row.payment_method || ''}
                        disabled={!canEditBusinessSettings}
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
                        disabled={!canEditBusinessSettings}
                        onChange={(e) => updateAccount(idx, { provider: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        className="input"
                        type="number"
                        value={row.sort_order || 100}
                        disabled={!canEditBusinessSettings}
                        onChange={(e) => updateAccount(idx, { sort_order: e.target.value })}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="checkbox"
                        checked={!!row.active}
                        disabled={!canEditBusinessSettings}
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
          <button
            className="btn"
            type="button"
            onClick={saveAccounts}
            disabled={saving || !accounts.length || !canEditBusinessSettings}
          >
            Guardar cuentas
          </button>
        </div>

        {canEditBusinessSettings ? (
          <>
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
                          onClick={(e) => toggleActionMenu(row.id, e.currentTarget)}
                          disabled={saving}
                        >
                          {'\u22EE'}
                        </button>
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
          </>
        ) : (
          <div className="card">
            <p className="text-sm text-gray-600">
              La gestion de usuarios y permisos queda reservada para perfiles con edicion de configuracion.
            </p>
          </div>
        )}

        {err ? <p className="text-sm text-red-700">{err}</p> : null}
        {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
      </div>
      {actionMenuRow && actionMenuPos
        ? createPortal(
            <div
              className="fixed z-[80] w-48 rounded-lg border border-neutral-200 bg-white py-1 shadow-lg"
              style={{ top: actionMenuPos.top, left: actionMenuPos.left }}
              data-user-actions-menu="true"
            >
              <button
                ref={actionMenuFirstButtonRef}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100"
                type="button"
                onClick={() => {
                  closeActionMenu();
                  toggleActive(actionMenuRow);
                }}
                disabled={saving}
              >
                {actionMenuRow.activo ? 'Desactivar' : 'Activar'}
              </button>
              <button
                className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100"
                type="button"
                onClick={() => {
                  closeActionMenu();
                  openPermEditor(actionMenuRow);
                }}
                disabled={saving}
              >
                Permisos personalizados
              </button>
              <button
                className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100 disabled:text-neutral-400"
                type="button"
                onClick={() => {
                  closeActionMenu();
                  resendRecoveryMail(actionMenuRow);
                }}
                disabled={saving || !actionMenuRow.activo}
              >
                Reenviar mail
              </button>
              <button
                className="block w-full px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50"
                type="button"
                onClick={() => {
                  closeActionMenu();
                  deleteUser(actionMenuRow);
                }}
                disabled={saving}
              >
                Eliminar
              </button>
            </div>,
            document.body,
          )
        : null}
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
                  {modalEditable && roleLockedPermissions.size > 0 ? (
                    <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      {`Hay ${roleLockedPermissions.size} permiso(s) bloqueado(s) por politica de rol para este usuario.`}
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
