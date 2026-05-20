import InfoHint from './InfoHint';
import { appendToken, isKnownAttrValue, valuesForAttr } from '../lib/variantAttributes';

function HelpTitle({ as: Tag = 'h3', className = '', children, help }) {
  return (
    <Tag className={`inline-flex items-center gap-2 ${className}`}>
      <span>{children}</span>
      <InfoHint text={help} />
    </Tag>
  );
}

export function VariantAttributeRows({
  rows = [],
  attributes = [],
  attributeValuesByCode = {},
  getAvailableAttributesForRow,
  onUpdateRow,
  onRemoveRow,
  onAddRow,
  canAddRow = true,
  disabled = false,
  title = 'Atributos',
  help,
  emptyMessage = '',
  listIdPrefix = 'variant-attr-values',
  valuePlaceholder = 'Ej: S, Negro, 36',
  minRows = 1,
}) {
  return (
    <div className="space-y-2">
      <HelpTitle as="h4" className="text-sm font-semibold" help={help}>
        {title}
      </HelpTitle>
      {!rows.length && emptyMessage ? <p className="text-xs text-neutral-500">{emptyMessage}</p> : null}
      {rows.map((row, idx) => {
        const attrValues = valuesForAttr(attributeValuesByCode, row.attribute_code).slice(0, 10);
        const knownValue = isKnownAttrValue(attributeValuesByCode, row.attribute_code, row.value);
        const listId = `${listIdPrefix}-${idx}`;
        const options = typeof getAvailableAttributesForRow === 'function'
          ? getAvailableAttributesForRow(idx)
          : attributes;

        return (
          <div key={idx} className="grid grid-cols-1 gap-2 items-end md:grid-cols-12">
            <div className="md:col-span-5">
              <label className="block text-xs text-gray-500 mb-1">Atributo</label>
              <select
                className="input"
                value={row.attribute_code || ''}
                onChange={(e) =>
                  onUpdateRow(idx, {
                    attribute_code: e.target.value,
                    value: '',
                    attribute_value_id: undefined,
                    confirm_new_value: false,
                  })
                }
                required
                disabled={disabled}
              >
                <option value="">Seleccionar atributo</option>
                {options.map((item) => (
                  <option key={item.id} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-5">
              <label className="block text-xs text-gray-500 mb-1">Valor</label>
              <input
                className="input"
                list={listId}
                placeholder={valuePlaceholder}
                value={row.value || ''}
                onChange={(e) =>
                  onUpdateRow(idx, {
                    value: e.target.value,
                    attribute_value_id: undefined,
                    confirm_new_value: false,
                  })
                }
                required
                disabled={disabled}
              />
              <datalist id={listId}>
                {attrValues.map((item) => (
                  <option key={item.id} value={item.value_label} />
                ))}
              </datalist>
              {attrValues.length ? (
                <div className="mt-1 flex flex-wrap gap-1">
                  {attrValues.slice(0, 6).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="px-2 py-1 rounded border text-[11px] hover:bg-neutral-100"
                      onClick={() =>
                        onUpdateRow(idx, {
                          value: item.value_label,
                          attribute_value_id: item.id,
                          confirm_new_value: false,
                        })
                      }
                      disabled={disabled}
                    >
                      {item.value_label}
                    </button>
                  ))}
                </div>
              ) : null}
              {row.value && row.attribute_code && !knownValue ? (
                <button
                  type="button"
                  className={`mt-1 px-2 py-1 rounded border text-[11px] ${
                    row.confirm_new_value ? 'border-amber-300 bg-amber-50 text-amber-700' : 'hover:bg-neutral-100'
                  }`}
                  onClick={() => onUpdateRow(idx, { confirm_new_value: !row.confirm_new_value })}
                  disabled={disabled}
                >
                  {row.confirm_new_value ? 'Nuevo valor confirmado' : 'Crear valor nuevo'}
                </button>
              ) : null}
            </div>

            <div className="md:col-span-2">
              <button
                type="button"
                className="px-3 py-2 rounded border w-full"
                onClick={() => onRemoveRow(idx)}
                disabled={disabled || rows.length <= minRows}
              >
                Quitar
              </button>
            </div>
          </div>
        );
      })}

      <button
        type="button"
        className="px-3 py-2 rounded border"
        onClick={onAddRow}
        disabled={disabled || !canAddRow}
      >
        Agregar atributo
      </button>
    </div>
  );
}

export function VariantAttributeMultiRows({
  rows = [],
  attributes = [],
  attributeValuesByCode = {},
  getAvailableAttributesForRow,
  onUpdateRow,
  onRemoveRow,
  onAddRow,
  canAddRow = true,
  disabled = false,
  title = 'Atributos multivalor',
  help,
  listIdPrefix = 'variant-multi-attr-values',
  valuePlaceholder = 'Ej: azul, violeta, negro',
  minRows = 1,
}) {
  return (
    <div className="space-y-2">
      <HelpTitle as="h4" className="text-sm font-semibold" help={help}>
        {title}
      </HelpTitle>
      {rows.map((row, idx) => {
        const attrValues = valuesForAttr(attributeValuesByCode, row.attribute_code).slice(0, 12);
        const listId = `${listIdPrefix}-${idx}`;
        const options = typeof getAvailableAttributesForRow === 'function'
          ? getAvailableAttributesForRow(idx)
          : attributes;

        return (
          <div key={idx} className="grid grid-cols-1 gap-2 items-end md:grid-cols-12">
            <div className="md:col-span-4">
              <label className="block text-xs text-gray-500 mb-1">Atributo</label>
              <select
                className="input"
                value={row.attribute_code || ''}
                onChange={(e) => onUpdateRow(idx, { attribute_code: e.target.value, values_text: '' })}
                disabled={disabled}
              >
                <option value="">Seleccionar atributo</option>
                {options.map((item) => (
                  <option key={item.id} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-7">
              <label className="block text-xs text-gray-500 mb-1">Valores (coma, punto y coma o salto de linea)</label>
              <input
                className="input"
                list={listId}
                placeholder={valuePlaceholder}
                value={row.values_text || ''}
                onChange={(e) => onUpdateRow(idx, { values_text: e.target.value })}
                disabled={disabled}
              />
              <datalist id={listId}>
                {attrValues.map((item) => (
                  <option key={item.id} value={item.value_label} />
                ))}
              </datalist>
              {attrValues.length ? (
                <div className="mt-1 flex flex-wrap gap-1">
                  {attrValues.slice(0, 8).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="px-2 py-1 rounded border text-[11px] hover:bg-neutral-100"
                      onClick={() => onUpdateRow(idx, { values_text: appendToken(row.values_text, item.value_label) })}
                      disabled={disabled}
                    >
                      {item.value_label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="md:col-span-1">
              <button
                type="button"
                className="px-3 py-2 rounded border w-full"
                onClick={() => onRemoveRow(idx)}
                disabled={disabled || rows.length <= minRows}
              >
                Quitar
              </button>
            </div>
          </div>
        );
      })}

      <button
        type="button"
        className="px-3 py-2 rounded border"
        onClick={onAddRow}
        disabled={disabled || !canAddRow}
      >
        Agregar atributo
      </button>
    </div>
  );
}
