import { useEffect, useRef, useState } from 'react';
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
              Primero importa catalogo desde Tienda Nube a RetailHub. Despues puedes sincronizar precios y stock
              desde RetailHub hacia Tienda Nube.
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
                  Reconciliar catalogo
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Limite de productos</label>
          <input className="input" type="number" min="1" max="2000" value={limit} onChange={(e) => setLimit(e.target.value)} />
        </div>
        <button type="button" className="btn" onClick={runCatalogImport} disabled={loading}>
          Importar catalogo
        </button>
        <button type="button" className="btn" onClick={runStockSync} disabled={loading}>
          Sync stock
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
          Proceso programado jobs
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
            Import catalogo: {Number(failedSummary?.by_type?.import_catalogo || 0)}
          </span>
          <span className="inline-flex rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Reconciliar catalogo: {Number(failedSummary?.by_type?.sync_catalogo || 0)}
          </span>
          <span className="inline-flex rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Sync stock: {Number(failedSummary?.by_type?.sync_stock || 0)}
          </span>
          {summaryLoading ? <span className="text-gray-500">Actualizando estado...</span> : null}
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado importacion</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(importResult, null, 2)}</pre>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado reconciliacion catalogo</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(catalogResult, null, 2)}</pre>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado stock</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(stockResult, null, 2)}</pre>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado reintento de fallidos</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(retryResult, null, 2)}</pre>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Fallidos recientes (online sync)</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(failedSummary, null, 2)}</pre>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado proceso de jobs (ARCA + online)</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(processResult, null, 2)}</pre>
      </div>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {summaryErr ? <p className="text-sm text-red-700">{summaryErr}</p> : null}
    </div>
  );
}
