import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import type { Competitor, Source, Change, Analysis, Partnership, PaginatedResponse } from '../types';
import { getCompetitor, getSources, getChanges, getAnalyses, getPartnerships } from '../api/client';
import ChangeCard from '../components/ChangeCard';
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

type Tab = 'sources' | 'changes' | 'analyses' | 'partnerships';

export default function CompetitorDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [comp, setComp] = useState<Competitor | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [changesData, setChangesData] = useState<PaginatedResponse<Change> | null>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [partnerships, setPartnerships] = useState<Partnership[]>([]);
  const [tab, setTab] = useState<Tab>('sources');
  const [loading, setLoading] = useState(true);
  const [showSourceForm, setShowSourceForm] = useState(false);

  const load = async () => {
    if (!slug) return;
    try {
      const c = await getCompetitor(slug);
      setComp(c);
      const [src, chg, ana, part] = await Promise.all([
        getSources({ competitor_id: c._id }),
        getChanges({ competitor_id: c._id, limit: 30 }),
        getAnalyses({ competitor_id: c._id, limit: 20 }),
        getPartnerships({ competitor_id: c._id }),
      ]);
      setSources(src);
      setChangesData(chg);
      setAnalyses(ana);
      setPartnerships(part);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [slug]);

  if (loading) return <LoadingSpinner />;
  if (!comp) return <p className="text-slate-500">Competitor not found</p>;

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'sources', label: 'Sources', count: sources.length },
    { key: 'changes', label: 'Changes', count: changesData?.total || 0 },
    { key: 'analyses', label: 'Analyses', count: analyses.length },
    { key: 'partnerships', label: 'Partnerships', count: partnerships.length },
  ];

  return (
    <div>
      <Link to="/competitors" className="text-sm text-indigo-600 hover:underline">&larr; Back to competitors</Link>

      <div className="mt-4">
        <h1 className="text-2xl font-bold text-slate-800">{comp.name}</h1>
        <p className="text-sm text-slate-400 mt-0.5">{comp.domain}</p>
        {comp.description && <p className="text-sm text-slate-600 mt-2">{comp.description}</p>}
        <div className="flex gap-2 mt-2">
          {comp.industry && <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">{comp.industry}</span>}
          {comp.tags.map(t => (
            <span key={t} className="px-2 py-0.5 text-xs bg-indigo-50 text-indigo-600 rounded">{t}</span>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mt-6 bg-slate-100 rounded-lg p-1 w-fit">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t.key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label} ({t.count})
          </button>
        ))}
      </div>

      <div className="mt-4">
        {/* Sources tab */}
        {tab === 'sources' && (
          <div>
            <div className="flex justify-end mb-3">
              <button
                onClick={() => setShowSourceForm(true)}
                className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
              >
                + Add Source
              </button>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                  <tr>
                    <th className="text-left px-4 py-3">URL</th>
                    <th className="text-left px-4 py-3">Type</th>
                    <th className="text-left px-4 py-3">Schedule</th>
                    <th className="text-left px-4 py-3">Last Scraped</th>
                    <th className="text-center px-4 py-3">Failures</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map(s => (
                    <tr key={s._id} className={`border-t border-slate-100 ${s.consecutive_failures > 0 ? 'bg-amber-50' : ''}`}>
                      <td className="px-4 py-3 max-w-sm truncate">
                        <a href={s.url} target="_blank" rel="noopener" className="text-indigo-600 hover:underline">{s.url}</a>
                      </td>
                      <td className="px-4 py-3"><span className="px-2 py-0.5 text-xs bg-slate-100 rounded">{s.page_type}</span></td>
                      <td className="px-4 py-3 text-xs text-slate-500">{s.schedule_group}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{timeAgo(s.last_scraped_at)}</td>
                      <td className="px-4 py-3 text-center text-xs">{s.consecutive_failures || 0}</td>
                    </tr>
                  ))}
                  {sources.length === 0 && (
                    <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No sources yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {showSourceForm && (
              <SourceForm
                onClose={() => setShowSourceForm(false)}
                onCreated={load}
                preselectedCompetitorId={comp._id}
              />
            )}
          </div>
        )}

        {/* Changes tab */}
        {tab === 'changes' && (
          <div className="space-y-2">
            {changesData?.items.map(c => <ChangeCard key={c._id} change={c} />) }
            {changesData?.items.length === 0 && <p className="text-sm text-slate-400 py-6 text-center">No changes detected</p>}
          </div>
        )}

        {/* Analyses tab */}
        {tab === 'analyses' && (
          <div className="space-y-3">
            {analyses.length === 0 && <p className="text-sm text-slate-400 py-6 text-center">No analyses yet</p>}
            {analyses.map(a => (
              <div key={a._id} className="bg-white rounded-lg border border-slate-200 p-4">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="bg-slate-100 px-2 py-0.5 rounded">{a.analysis_type}</span>
                  <span className="ml-auto">{timeAgo(a.generated_at)}</span>
                </div>
                <p className="text-sm font-medium text-slate-800 mt-2">{a.content?.summary}</p>
                {a.content?.impact_assessment && <p className="text-sm text-slate-600 mt-1">{a.content.impact_assessment}</p>}
              </div>
            ))}
          </div>
        )}

        {/* Partnerships tab */}
        {tab === 'partnerships' && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                <tr>
                  <th className="text-left px-4 py-3">Partner</th>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-left px-4 py-3">Confidence</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Discovered</th>
                </tr>
              </thead>
              <tbody>
                {partnerships.map(p => (
                  <tr key={p._id} className="border-t border-slate-100">
                    <td className="px-4 py-3 font-medium text-slate-800">{p.partner_name}</td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 text-xs bg-slate-100 rounded">{p.partnership_type}</span></td>
                    <td className="px-4 py-3 text-xs">{(p.confidence * 100).toFixed(0)}%</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{p.status}</td>
                    <td className="px-4 py-3 text-xs text-slate-400">{timeAgo(p.discovered_at)}</td>
                  </tr>
                ))}
                {partnerships.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No partnerships detected</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
