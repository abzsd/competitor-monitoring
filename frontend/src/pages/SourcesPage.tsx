import { useEffect, useState } from 'react';
import type { Source } from '../types';
import { getSources, deleteSource } from '../api/client';
import SourceForm from '../components/SourceForm';
import LoadingSpinner from '../components/LoadingSpinner';

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const load = () => {
    getSources()
      .then(setSources)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Disable this source?')) return;
    try {
      await deleteSource(id);
      load();
    } catch { /* ignore */ }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Sources</h1>
          <p className="text-sm text-slate-500 mt-1">{sources.length} active source(s)</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
        >
          + Add Source
        </button>
      </div>

      <div className="mt-6 bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
            <tr>
              <th className="text-left px-4 py-3">URL</th>
              <th className="text-left px-4 py-3">Competitor</th>
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Method</th>
              <th className="text-left px-4 py-3">Schedule</th>
              <th className="text-left px-4 py-3">Last Scraped</th>
              <th className="text-center px-4 py-3">Failures</th>
              <th className="text-right px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {sources.map(s => (
              <tr
                key={s._id}
                className={`border-t border-slate-100 hover:bg-slate-50 ${s.consecutive_failures > 0 ? 'bg-amber-50' : ''}`}
              >
                <td className="px-4 py-3 max-w-xs truncate">
                  <a href={s.url} target="_blank" rel="noopener" className="text-indigo-600 hover:underline">{s.url}</a>
                </td>
                <td className="px-4 py-3 text-slate-600">{s.competitor_name}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 text-xs bg-slate-100 rounded">{s.page_type}</span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">{s.scrape_method}</td>
                <td className="px-4 py-3 text-xs text-slate-500">{s.schedule_group}</td>
                <td className="px-4 py-3 text-xs text-slate-400">{timeAgo(s.last_scraped_at)}</td>
                <td className="px-4 py-3 text-center">
                  {s.consecutive_failures > 0 ? (
                    <span className="text-xs font-semibold text-amber-600">{s.consecutive_failures}</span>
                  ) : (
                    <span className="text-xs text-slate-300">0</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => handleDelete(s._id)} className="text-xs text-slate-400 hover:text-red-500">
                    Disable
                  </button>
                </td>
              </tr>
            ))}
            {sources.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">No sources yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && <SourceForm onClose={() => setShowForm(false)} onCreated={load} />}
    </div>
  );
}
