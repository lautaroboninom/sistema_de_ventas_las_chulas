export default function Tabs({ value, onChange, items, extraRight }) {
  return (
    <div className="border-b mb-4 flex items-center">
      <div className="flex gap-2">
        {items.map((it) => (
          <button
            key={it.value}
            className={`px-3 py-2 rounded-t ${
              value === it.value
                ? "bg-white border border-b-0"
                : "text-gray-600 hover:text-black"
            }`}
            onClick={() => onChange(it.value)}
            type="button"
          >
            {it.label}
          </button>
        ))}
      </div>
      <div className="ml-auto">{extraRight}</div>
    </div>
  );
}

