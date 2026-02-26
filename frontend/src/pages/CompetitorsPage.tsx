import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Competitor } from '../types';
import { getCompetitors, deleteCompetitor } from '../api/client';
import CompetitorForm from '../components/CompetitorForm';
import LoadingSpinner from '../components/LoadingSpinner';

export default function CompetitorsPage() {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const load = () => {
    getCompetitors()
      .then(setCompetitors)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (slug: string, name: string) => {
    if (!confirm(`Deactivate "${name}"? This will stop monitoring.`)) return;
    try {
      await deleteCompetitor(slug);
      load();
    } catch { /* ignore */ }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Competitors</h1>
          <p className="text-sm text-slate-500 mt-1">{competitors.length} competitor(s) being monitored</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
        >
          + Add Competitor
        </button>
      </div>

      {competitors.length === 0 ? (
        <div className="mt-10 text-center">
          <p className="text-slate-400">No competitors added yet.</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-3 text-indigo-600 text-sm font-medium hover:underline"
          >
            Add your first competitor
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
          {competitors.map(c => (
            <div key={c._id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow">
              <div className="flex items-start justify-between">
                <div>
                  <Link to={`/competitors/${c.slug}`} className="text-lg font-semibold text-slate-800 hover:text-indigo-600">
                    {c.name}
                  </Link>
                  <p className="text-sm text-slate-400 mt-0.5">{c.domain}</p>
                </div>
                <button
                  onClick={() => handleDelete(c.slug, c.name)}
                  className="text-xs text-slate-400 hover:text-red-500"
                  title="Deactivate"
                >
                  ✕
                </button>
              </div>
              {c.industry && (
                <span className="inline-block mt-2 px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">
                  {c.industry}
                </span>
              )}
              {c.description && <p className="text-sm text-slate-500 mt-2 line-clamp-2">{c.description}</p>}
              <div className="flex gap-4 mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                <span><strong className="text-slate-700">{c.source_count}</strong> sources</span>
                <span><strong className="text-slate-700">{c.recent_change_count}</strong> changes (7d)</span>
              </div>
              {c.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {c.tags.map(t => (
                    <span key={t} className="px-1.5 py-0.5 text-xs bg-indigo-50 text-indigo-600 rounded">{t}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && <CompetitorForm onClose={() => setShowForm(false)} onCreated={load} />}
    </div>
  );
}
