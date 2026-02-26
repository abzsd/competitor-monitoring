import { useEffect, useState } from 'react';
import type { Analysis, Alert } from '../types';
import { getAnalyses, getAlerts } from '../api/client';
import SeverityBadge from '../components/SeverityBadge';
import LoadingSpinner from '../components/LoadingSpinner';

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function AnalysesPage() {
  const [tab, setTab] = useState<'analyses' | 'alerts'>('analyses');
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getAnalyses({ limit: 50 }),
      getAlerts({ hours: 168 }),
    ])
      .then(([a, al]) => { setAnalyses(a); setAlerts(al); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800">Analyses & Alerts</h1>

      <div className="flex gap-1 mt-4 bg-slate-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('analyses')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === 'analyses' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Analyses ({analyses.length})
        </button>
        <button
          onClick={() => setTab('alerts')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === 'alerts' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Alerts ({alerts.length})
        </button>
      </div>

      {tab === 'analyses' && (
        <div className="mt-4 space-y-3">
          {analyses.length === 0 && <p className="text-sm text-slate-400 py-8 text-center">No analyses yet</p>}
          {analyses.map(a => (
            <div key={a._id} className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">{a.analysis_type}</span>
                <span className="text-xs text-slate-400">{a.competitor_name}</span>
                <span className="text-xs text-slate-400 ml-auto">{timeAgo(a.generated_at)}</span>
              </div>
              <p className="text-sm font-medium text-slate-800 mt-2">{a.content?.summary || '(no summary)'}</p>
              {a.content?.impact_assessment && (
                <p className="text-sm text-slate-600 mt-1">{a.content.impact_assessment}</p>
              )}
              {a.content?.actionable_insights?.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {a.content.actionable_insights.map((insight, i) => (
                    <li key={i} className="text-sm text-slate-600 flex gap-2">
                      <span className="text-indigo-500">-</span> {insight}
                    </li>
                  ))}
                </ul>
              )}
              {a.content?.confidence > 0 && (
                <div className="mt-2 text-xs text-slate-400">
                  Confidence: {(a.content.confidence * 100).toFixed(0)}%
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'alerts' && (
        <div className="mt-4 bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3">Subject</th>
                <th className="text-left px-4 py-3">Competitor</th>
                <th className="text-left px-4 py-3">Severity</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Sent</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map(a => (
                <tr key={a._id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 max-w-md truncate">{a.subject || '(no subject)'}</td>
                  <td className="px-4 py-3 text-slate-600">{a.competitor_name}</td>
                  <td className="px-4 py-3"><SeverityBadge severity={a.severity} /></td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${a.status === 'sent' ? 'text-emerald-600' : a.status === 'failed' ? 'text-red-600' : 'text-slate-400'}`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{timeAgo(a.sent_at)}</td>
                </tr>
              ))}
              {alerts.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">No alerts in the last 7 days</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
