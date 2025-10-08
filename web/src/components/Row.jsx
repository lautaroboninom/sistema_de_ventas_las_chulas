export default function Row({ label, children, className = "" }) {
  return (
    <div className={`flex gap-3 py-1 ${className}`}>
      <div className="w-40 text-gray-500">{label}</div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

