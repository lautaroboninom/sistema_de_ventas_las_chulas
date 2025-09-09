// web/src/pages/DerivarIngreso.jsx
import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { getProveedoresExternos, postDerivarIngreso } from "../lib/api";

export default function DerivarIngreso() {
  const { id } = useParams(); // :id del ingreso
  const nav = useNavigate();
  const [loading, setLoading] = useState(false);
  const [proveedores, setProveedores] = useState([]);
  const [form, setForm] = useState({
    external_service_id: "",
    remit_deriv: "",
    fecha_deriv: new Date().toISOString().slice(0, 10),
    comentarios: "",
  });
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const rows = await getProveedoresExternos();
        setProveedores(rows || []);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.external_service_id) {
      setError("Seleccioná un proveedor externo.");
      return;
    }
    setLoading(true);
    try {
      await postDerivarIngreso(id, {
        external_service_id: Number(form.external_service_id),
        remit_deriv: form.remit_deriv || null,
        fecha_deriv: form.fecha_deriv || null,
        comentarios: form.comentarios || null,
      });
      nav("/tecnico");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-semibold mb-4">Derivar ingreso #{id}</h1>

      {error && <div className="p-3 mb-3 bg-red-100 text-red-700 rounded">{error}</div>}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm mb-1">Proveedor externo</label>
          <select
            name="external_service_id"
            value={form.external_service_id}
            onChange={onChange}
            className="input w-full"
          >
            <option value="">-- seleccionar --</option>
            {proveedores.map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm mb-1">Remito / referencia</label>
          <input
            name="remit_deriv"
            value={form.remit_deriv}
            onChange={onChange}
            className="input w-full"
            placeholder="Remito 123"
          />
        </div>

        <div>
          <label className="block text-sm mb-1">Fecha derivación</label>
          <input
            type="date"
            name="fecha_deriv"
            value={form.fecha_deriv}
            onChange={onChange}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm mb-1">Comentarios</label>
          <textarea
            name="comentarios"
            value={form.comentarios}
            onChange={onChange}
            className="input w-full"
            rows={3}
          />
        </div>

        <div className="flex gap-2">
          <button className="btn" disabled={loading}>
            {loading ? "Derivando..." : "Derivar"}
          </button>
          <Link to="/tecnico" className="btn-secondary">Cancelar</Link>
        </div>
      </form>
    </div>
  );
}
