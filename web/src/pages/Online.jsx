import { useState } from 'react';
import { postRetailOnlineSyncCatalogo, postRetailOnlineSyncStock } from '../lib/api';

function errMsg(error) {
  return error?.message || 'Ocurrió un error inesperado';
}

export default function OnlinePage() {
  const [limit, setLimit] = useState('200');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [catalogResult, setCatalogResult] = useState(null);
  const [stockResult, setStockResult] = useState(null);

  async function runCatalogSync() {
    setLoading(true);
    setErr('');
    try {
      const result = await postRetailOnlineSyncCatalogo({ limit: Number(limit || 200) });
      setCatalogResult(result);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
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
    }
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Online (Tienda Nube)</h1>
        <p className="text-sm text-gray-600">Sincronización manual de catálogo y stock. El sistema local es la fuente maestra de variantes y stock.</p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Límite de variantes</label>
          <input className="input" type="number" min="1" max="2000" value={limit} onChange={(e) => setLimit(e.target.value)} />
        </div>
        <button type="button" className="px-3 py-2 rounded border" onClick={runCatalogSync} disabled={loading}>
          Sync catálogo
        </button>
        <button type="button" className="btn" onClick={runStockSync} disabled={loading}>
          Sync stock
        </button>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado catálogo</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(catalogResult, null, 2)}</pre>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Resultado stock</h2>
        <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">{JSON.stringify(stockResult, null, 2)}</pre>
      </div>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
    </div>
  );
}

