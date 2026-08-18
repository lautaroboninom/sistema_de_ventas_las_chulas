import { useMemo, useState } from 'react';
import { postRetailProductoAgregarAtributo } from '../lib/api';
import { attrCode, dedupValues, isKnownAttrValue, splitValues, valuesForAttr } from '../lib/variantAttributes';
import InfoHint from './InfoHint';

function errMsg(error) {
  return error?.data?.detail || error?.message || 'Ocurrio un error inesperado';
}

/**
 * Agrega un atributo (por ejemplo Color) a un producto que ya tiene variantes.
 *
 * Completa las variantes que ya existen con el valor que tenian de hecho y crea
 * solo las combinaciones que faltan, en vez de dejar las viejas en cero al lado
 * de un juego nuevo de variantes.
 */
export default function ProductAddAttribute({
  product,
  attributes = [],
  attributeValuesByCode = {},
  disabled = false,
  onDone,
}) {
  const [attributeCodeSel, setAttributeCodeSel] = useState('');
  const [existingValue, setExistingValue] = useState('');
  const [newValuesText, setNewValuesText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const nuevos = useMemo(() => {
    const limpio = dedupValues(splitValues(newValuesText));
    const actual = String(existingValue || '').trim().toLowerCase();
    return limpio.filter((value) => value.toLowerCase() !== actual);
  }, [newValuesText, existingValue]);

  const valoresSugeridos = valuesForAttr(attributeValuesByCode, attributeCodeSel);
  const listId = `add-attr-values-${product?.id || 'x'}`;

  const valoresNuevosDesconocidos = nuevos.filter(
    (value) => !isKnownAttrValue(attributeValuesByCode, attributeCodeSel, value),
  );
  const existenteEsNuevo =
    !!String(existingValue || '').trim() && !isKnownAttrValue(attributeValuesByCode, attributeCodeSel, existingValue);
  const necesitaConfirmar = valoresNuevosDesconocidos.length > 0 || existenteEsNuevo;

  const puedeEnviar = !!attributeCodeSel && !!String(existingValue || '').trim() && !busy && !disabled;

  async function submit(e) {
    e.preventDefault();
    if (!puedeEnviar) return;
    setErr('');
    setMsg('');
    setBusy(true);
    try {
      const out = await postRetailProductoAgregarAtributo(product.id, {
        attribute_code: attrCode(attributeCodeSel),
        existing_value: String(existingValue).trim(),
        new_values: nuevos,
        confirm_new_value: necesitaConfirmar,
      });
      setMsg(
        `Listo: se completaron ${out?.actualizadas || 0} variante(s) existentes y se crearon ${out?.creadas || 0} nueva(s).`,
      );
      setAttributeCodeSel('');
      setExistingValue('');
      setNewValuesText('');
      if (typeof onDone === 'function') await onDone();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
    }
  }

  if (!product?.id) return null;

  return (
    <form onSubmit={submit} className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3 space-y-2">
      <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-950">
        <span>Agregar atributo a este producto</span>
        <InfoHint text="Usalo cuando un producto que ya cargaste empieza a venir en otra variante (por ejemplo, otro color). Completa las variantes actuales y crea solo las combinaciones que faltan." />
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div className="space-y-1">
          <label className="block text-xs text-emerald-900">Atributo nuevo</label>
          <select
            className="input"
            value={attributeCodeSel}
            onChange={(e) => setAttributeCodeSel(e.target.value)}
            disabled={busy || disabled}
          >
            <option value="">Elegi un atributo</option>
            {attributes.map((attr) => (
              <option key={attr.id} value={attr.code}>
                {attr.name}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label className="block text-xs text-emerald-900">Las variantes actuales son</label>
          <input
            className="input"
            list={listId}
            value={existingValue}
            onChange={(e) => setExistingValue(e.target.value)}
            placeholder="Ej: Negro"
            disabled={busy || disabled || !attributeCodeSel}
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="block text-xs text-emerald-900">Valores nuevos a agregar (separados por coma)</label>
        <input
          className="input"
          list={listId}
          value={newValuesText}
          onChange={(e) => setNewValuesText(e.target.value)}
          placeholder="Ej: Chocolate, Beige"
          disabled={busy || disabled || !attributeCodeSel}
        />
        <datalist id={listId}>
          {valoresSugeridos.map((item) => (
            <option key={item.id || item.value_label} value={item.value_label} />
          ))}
        </datalist>
      </div>

      <div className="rounded-lg border border-emerald-200 bg-white p-2 text-xs leading-6 text-neutral-700">
        {attributeCodeSel && String(existingValue || '').trim() ? (
          <>
            <p>
              Las variantes que ya tiene el producto pasan a ser{' '}
              <strong>{String(existingValue).trim()}</strong>.
            </p>
            {nuevos.length ? (
              <p>
                Se crean las combinaciones que falten para: <strong>{nuevos.join(', ')}</strong>.
              </p>
            ) : (
              <p>No se agregan valores nuevos: solo se completan las variantes actuales.</p>
            )}
          </>
        ) : (
          <p>Elegi el atributo y decinos que valor tienen hoy las variantes cargadas.</p>
        )}
      </div>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-emerald-800">{msg}</p> : null}

      <button className="btn" type="submit" disabled={!puedeEnviar}>
        {busy ? 'Aplicando...' : 'Aplicar al producto'}
      </button>
    </form>
  );
}
