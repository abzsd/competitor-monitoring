import { useEffect, useState } from 'react';
import type { Change, PaginatedResponse } from '../types';
import { getChanges } from '../api/client';
import ChangeCard from '../components/ChangeCard';
import LoadingSpinner from '../components/LoadingSpinner';

const SEVERITIES = ['', 'critical', 'high', 'medium', 'low'];
const CHANGE_TYPES = ['', 'pricing_change', 'product_update', 'tech_stack_change', 'partnership_new', 'content_update', 'page_added', 'page_removed'];

export default function ChangesPage() {
  const [data, setData] = useState<PaginatedResponse<Change> | null>(null);
  const [loading, setLoading] = useState(true);
  const [severity, setSeverity] = useState('');
  const [changeType, setChangeType] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 30;

  const load = () => {
    setLoading(true);
    const params: Record<string, string | number> = { limit, offset };
    if (severity) params.severity = severity;
    if (changeType) params.change_type = changeType;
    getChanges(params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [severity, changeType, offset]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800">Change History</h1>
      <p className="text-sm text-slate-500 mt-1">
        {data ? `${data.total} total change(s) detected` : 'Loading...'}
      </p>

      {/* Filters */}
      <div className="flex gap-3 mt-4">
        <select
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={severity}
          onChange={e => { setSeverity(e.target.value); setOffset(0); }}
        >
          <option value="">All severities</option>
          {SEVERITIES.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          value={changeType}
          onChange={e => { setChangeType(e.target.value); setOffset(0); }}
        >
          <option value="">All types</option>
          {CHANGE_TYPES.filter(Boolean).map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
        </select>
      </div>

      {loading ? <LoadingSpinner /> : (
        <>
          <div className="mt-4 space-y-2">
            {data?.items.map(c => <ChangeCard key={c._id} change={c} />) }
            {data?.items.length === 0 && (
              <p className="text-sm text-slate-400 py-8 text-center">No changes match your filters</p>
            )}
          </div>

          {/* Pagination */}
          {data && data.total > limit && (
            <div className="flex items-center justify-center gap-4 mt-6">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="px-3 py-1.5 text-sm bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-xs text-slate-500">
                {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
              </span>
              <button
                disabled={offset + limit >= data.total}
                onClick={() => setOffset(offset + limit)}
                className="px-3 py-1.5 text-sm bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
