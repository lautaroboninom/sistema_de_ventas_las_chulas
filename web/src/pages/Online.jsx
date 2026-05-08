import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  getRetailOnlineFailedJobsSummary,
  postRetailOnlineImportCatalogo,
  postRetailOnlineJobsProcess,
  postRetailOnlineRetryFailed,
  postRetailOnlineSyncCatalogo,
  postRetailOnlineSyncStock,
} from '../lib/api';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function ResultCard({ title, result, emptyText, intro }) {
  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      {result ? (
        <div className="space-y-2">
          {intro ? <p className="text-sm text-gray-600">{intro}</p> : null}
          <details className="rounded-lg border border-neutral-200 bg-gray-50">
            <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-neutral-700">Ver detalle tecnico</summary>
            <pre className="max-h-72 overflow-auto border-t border-neutral-200 p-2 text-xs">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      ) : (
        <p className="text-sm text-gray-500">{emptyText}</p>
      )}
    </div>
  );
}

export default function OnlinePage() {
  const [limit, setLimit] = useState('200');
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [err, setErr] = useState('');
  const [summaryErr, setSummaryErr] = useState('');
  const [importResult, setImportResult] = useState(null);
  const [catalogResult, setCatalogResult] = useState(null);
  const [stockResult, setStockResult] = useState(null);
  const [retryResult, setRetryResult] = useState(null);
  const [processResult, setProcessResult] = useState(null);
  const [failedSummary, setFailedSummary] = useState({
    failed_total: 0,
    by_type: {
      import_catalogo: 0,
      sync_catalogo: 0,
      sync_stock: 0,
    },
    items: [],
  });
  const actionMenuRef = useRef(null);

  async function loadFailedSummary() {
    setSummaryLoading(true);
    setSummaryErr('');
    try {
      const row = await getRetailOnlineFailedJobsSummary({ limit: 20 });
      setFailedSummary({
        failed_total: Number(row?.failed_total || 0),
        by_type: {
          import_catalogo: Number(row?.by_type?.import_catalogo || 0),
          sync_catalogo: Number(row?.by_type?.sync_catalogo || 0),
          sync_stock: Number(row?.by_type?.sync_stock || 0),
        },
        items: Array.isArray(row?.items) ? row.items : [],
      });
    } catch (error) {
      setSummaryErr(errMsg(error));
    } finally {
      setSummaryLoading(false);
    }
  }

  useEffect(() => {
    loadFailedSummary();
  }, []);

  useEffect(() => {
    if (!menuOpen) return undefined;
    function onMouseDown(event) {
      if (actionMenuRef.current && !actionMenuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [menuOpen]);

  async function runCatalogImport() {
    setLoading(true);
    setErr('');
    try {
      const result = await postRetailOnlineImportCatalogo({
        limit_products: Number(limit || 200),
        per_page: 50,
      });
      setImportResult(result);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
      await loadFailedSummary();
    }
  }

  async function runCatalogReconcile() {
    setLoading(true);
    setErr('');
    setMenuOpen(false);
    try {
      const result = await postRetailOnlineSyncCatalogo({ limit: Number(limit || 200) });
      setCatalogResult(result);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
      await loadFailedSummary();
    }
  }

  async function runStockSync() {
    setLoading(true);
    setErr('');
    try {
      const result = await postRetailOnlineSyncStock({ limit: Number(limit || 200) });
      setStockResult(result);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
      await loadFailedSummary();
    }
  }

  async function runRetryFailed() {
    setLoading(true);
    setErr('');
    try {
      const result = await postRetailOnlineRetryFailed({ limit: Number(limit || 20) });
      setRetryResult(result);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
      await loadFailedSummary();
    }
  }

  async function runJobsProcess() {
    setLoading(true);
    setErr('');
    try {
      const result = await postRetailOnlineJobsProcess({
        providers: ['arca', 'tiendanube'],
        limit: Number(limit || 20),
        max_attempts: 8,
      });
      setProcessResult(result);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
      await loadFailedSummary();
    }
  }

  const failedTotal = Number(failedSummary?.failed_total || 0);
  const hasFailed = failedTotal > 0;

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="h1">Online (Tienda Nube)</h1>
            <p className="text-sm text-gray-600">
              Esta pantalla conecta RetailHub con Tienda Nube. Los productos, variantes, precios y stock se toman desde
              RetailHub para mantener la tienda ordenada.
            </p>
          </div>
          <div className="relative" ref={actionMenuRef}>
            <button
              type="button"
              className="h-9 w-9 rounded border text-lg leading-none hover:bg-neutral-100"
              aria-label="Abrir menu de acciones online"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((prev) => !prev)}
              disabled={loading}
            >
              {'\u22EE'}
            </button>
            {menuOpen ? (
              <div className="absolute right-0 z-30 mt-1 w-56 rounded-lg border border-neutral-200 bg-white py-1 shadow-lg">
                <button
                  type="button"
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-neutral-100"
                  onClick={runCatalogReconcile}
                  disabled={loading}
                >
                  Corregir productos en Tienda Nube
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="card space-y-3 border-emerald-200 bg-emerald-50/60">
        <div>
          <h2 className="text-lg font-semibold text-emerald-950">Correccion automatica de productos en Tienda Nube</h2>
          <p className="mt-1 text-sm leading-6 text-emerald-900">
            Esta actualizacion ya esta preparada para que Tienda Nube reciba un solo producto con sus variantes adentro.
            Para productos nuevos o variantes nuevas no hace falta hacer nada extra: RetailHub los sincroniza con esta forma nueva.
          </p>
        </div>

        <div className="rounded-lg border border-emerald-200 bg-white p-3 text-sm leading-6 text-neutral-700">
          <p className="font-semibold text-neutral-900">Para corregir productos que ya estaban separados antes de esta actualizacion:</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            <li>
              Entrar a <Link to="/productos" className="font-semibold text-emerald-800 underline">Productos y variantes</Link> y revisar
              que cada variante tenga SKU.
            </li>
            <li>Tocar Corregir productos en Tienda Nube.</li>
            <li>Esperar a que termine y revisar Fallidos pendientes.</li>
            <li>Si quedan pendientes, tocar Reintentar fallidos.</li>
          </ol>
          <p className="mt-2 text-xs text-neutral-600">
            No borres productos duplicados desde Tienda Nube durante la correccion. RetailHub despublica productos viejos solo cuando ya pudo
            vincular todas las variantes correctamente.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn" onClick={runCatalogReconcile} disabled={loading}>
            {loading ? 'Procesando...' : 'Corregir productos en Tienda Nube'}
          </button>
          <button
            type="button"
            className={`px-3 py-2 rounded border ${
              hasFailed
                ? 'border-red-300 bg-red-50 text-red-700 font-semibold'
                : 'border-emerald-300 bg-white text-emerald-900 hover:bg-emerald-100'
            }`}
            onClick={runRetryFailed}
            disabled={loading}
          >
            Reintentar fallidos{hasFailed ? ` (${failedTotal})` : ''}
          </button>
        </div>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Limite de productos a procesar</label>
          <input className="input" type="number" min="1" max="2000" value={limit} onChange={(e) => setLimit(e.target.value)} />
        </div>
        <button type="button" className="btn" onClick={runCatalogImport} disabled={loading}>
          Importar desde Tienda Nube
        </button>
        <button type="button" className="btn" onClick={runStockSync} disabled={loading}>
          Sincronizar stock
        </button>
        <button
          type="button"
          className={`px-3 py-2 rounded border ${hasFailed ? 'border-red-300 bg-red-50 text-red-700 font-semibold' : 'hover:bg-neutral-100'}`}
          onClick={runRetryFailed}
          disabled={loading}
        >
          Reintentar fallidos{hasFailed ? ` (${failedTotal})` : ''}
        </button>
        <button type="button" className="btn-secondary" onClick={runJobsProcess} disabled={loading}>
          Procesar pendientes
        </button>
        <div className="md:col-span-4 flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`inline-flex rounded-full border px-3 py-1 ${
              hasFailed ? 'border-red-300 bg-red-50 text-red-700' : 'border-neutral-200 bg-neutral-50 text-neutral-700'
            }`}
          >
            Fallidos pendientes: {failedTotal}
          </span>
          <span className="inline-flex rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Importacion: {Number(failedSummary?.by_type?.import_catalogo || 0)}
          </span>
          <span className="inline-flex rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Correccion productos: {Number(failedSummary?.by_type?.sync_catalogo || 0)}
          </span>
          <span className="inline-flex rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Stock: {Number(failedSummary?.by_type?.sync_stock || 0)}
          </span>
          {summaryLoading ? <span className="text-gray-500">Actualizando estado...</span> : null}
        </div>
      </div>

      <ResultCard
        title="Resultado importacion"
        result={importResult}
        emptyText="Todavia no se importo catalogo desde Tienda Nube en esta sesion."
        intro="La importacion trae productos y variantes desde Tienda Nube hacia RetailHub."
      />

      <ResultCard
        title="Resultado correccion de productos"
        result={catalogResult}
        emptyText="Todavia no se ejecuto la correccion de productos en esta sesion."
        intro="La correccion agrupa variantes bajo su producto y vincula cada variante por SKU."
      />

      <ResultCard
        title="Resultado stock"
        result={stockResult}
        emptyText="Todavia no se sincronizo stock en esta sesion."
        intro="La sincronizacion de stock actualiza en Tienda Nube las cantidades disponibles que figuran en RetailHub."
      />

      <ResultCard
        title="Resultado reintento de fallidos"
        result={retryResult}
        emptyText="Todavia no se reintentaron pendientes en esta sesion."
        intro="El reintento vuelve a procesar acciones que antes no pudieron terminar."
      />

      <ResultCard
        title="Fallidos recientes"
        result={failedSummary}
        emptyText="No hay estado de pendientes cargado todavia."
        intro="Este estado muestra si quedaron acciones pendientes de Tienda Nube para revisar o reintentar."
      />

      <ResultCard
        title="Resultado procesar pendientes"
        result={processResult}
        emptyText="Todavia no se proceso la cola de pendientes en esta sesion."
        intro="Procesar pendientes intenta resolver trabajos de Tienda Nube y ARCA que quedaron en espera."
      />

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {summaryErr ? <p className="text-sm text-red-700">{summaryErr}</p> : null}
    </div>
  );
}
