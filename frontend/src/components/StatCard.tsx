interface Props {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: 'indigo' | 'green' | 'amber' | 'red' | 'slate';
}

const colors = {
  indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  amber: 'bg-amber-50 text-amber-700 border-amber-200',
  red: 'bg-red-50 text-red-700 border-red-200',
  slate: 'bg-slate-50 text-slate-700 border-slate-200',
};

export default function StatCard({ label, value, subtitle, color = 'slate' }: Props) {
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <p className="text-xs font-semibold uppercase tracking-wider opacity-70">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {subtitle && <p className="text-xs mt-1 opacity-60">{subtitle}</p>}
    </div>
  );
}
