const styles: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-slate-100 text-slate-600 border-slate-200',
};

export default function SeverityBadge({ severity }: { severity: string }) {
  const s = severity?.toLowerCase() || 'low';
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${styles[s] || styles.low}`}>
      {s.toUpperCase()}
    </span>
  );
}
