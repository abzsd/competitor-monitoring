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

const riskColors: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

function InvestigationCard({ a }: { a: Analysis }) {
  const c = a.content;
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">investigation</span>
        {c.risk_level && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${riskColors[c.risk_level] || 'bg-slate-100 text-slate-600'}`}>
            {c.risk_level} risk
          </span>
        )}
        <span className="text-xs text-slate-400">{a.competitor_name}</span>
        <span className="text-xs text-slate-400 ml-auto">{timeAgo(a.generated_at)}</span>
      </div>

      {c.what_happened && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold text-slate-700">What happened</h3>
          <p className="text-sm text-slate-600 mt-1">{c.what_happened}</p>
        </div>
      )}

      {c.why_it_matters && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold text-slate-700">Why it matters</h3>
          <p className="text-sm text-slate-600 mt-1">{c.why_it_matters}</p>
        </div>
      )}

      {c.market_context && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold text-slate-700">Market context</h3>
          <p className="text-sm text-slate-600 mt-1">{c.market_context}</p>
        </div>
      )}

      {c.recommended_response && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold text-slate-700">Recommended response</h3>
          <p className="text-sm text-slate-600 mt-1">{c.recommended_response}</p>
        </div>
      )}

      {c.key_facts && c.key_facts.length > 0 && (
        <div className="mt-3">
          <h3 className="text-sm font-semibold text-slate-700">Key facts</h3>
          <ul className="mt-1 space-y-1">
            {c.key_facts.map((fact, i) => (
              <li key={i} className="text-sm text-slate-600 flex gap-2">
                <span className="text-indigo-500 shrink-0">*</span> {fact}
              </li>
            ))}
          </ul>
        </div>
      )}

      {c.sources_cited && c.sources_cited.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sources</h3>
          <div className="mt-1 flex flex-col gap-1">
            {c.sources_cited.map((src, i) => {
              try {
                const domain = new URL(src).hostname.replace('www.', '');
                return (
                  <a key={i} href={src} target="_blank" rel="noopener noreferrer"
                    className="text-xs text-indigo-600 hover:text-indigo-800 hover:underline truncate">
                    {domain}
                  </a>
                );
              } catch {
                return <span key={i} className="text-xs text-slate-500">{src}</span>;
              }
            })}
          </div>
        </div>
      )}

      {(c.confidence ?? 0) > 0 && (
        <div className="mt-2 text-xs text-slate-400">
          Confidence: {((c.confidence ?? 0) * 100).toFixed(0)}%
          {c.articles_analyzed ? ` | ${c.articles_analyzed} articles analyzed` : ''}
        </div>
      )}
    </div>
  );
}

function StandardAnalysisCard({ a }: { a: Analysis }) {
  const c = a.content;
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">{a.analysis_type}</span>
        <span className="text-xs text-slate-400">{a.competitor_name}</span>
        <span className="text-xs text-slate-400 ml-auto">{timeAgo(a.generated_at)}</span>
      </div>
      <p className="text-sm font-medium text-slate-800 mt-2">{c?.summary || '(no summary)'}</p>
      {c?.impact_assessment && (
        <p className="text-sm text-slate-600 mt-1">{c.impact_assessment}</p>
      )}
      {c?.actionable_insights && c.actionable_insights.length > 0 && (
        <ul className="mt-2 space-y-1">
          {c.actionable_insights.map((insight, i) => (
            <li key={i} className="text-sm text-slate-600 flex gap-2">
              <span className="text-indigo-500">-</span> {insight}
            </li>
          ))}
        </ul>
      )}
      {(c?.confidence ?? 0) > 0 && (
        <div className="mt-2 text-xs text-slate-400">
          Confidence: {((c.confidence ?? 0) * 100).toFixed(0)}%
        </div>
      )}
    </div>
  );
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

  const investigations = analyses.filter(a => a.analysis_type === 'investigation');
  const standardAnalyses = analyses.filter(a => a.analysis_type !== 'investigation');

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
        <div className="mt-4 space-y-6">
          {analyses.length === 0 && <p className="text-sm text-slate-400 py-8 text-center">No analyses yet</p>}

          {investigations.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
                Investigations ({investigations.length})
              </h2>
              <div className="space-y-3">
                {investigations.map(a => <InvestigationCard key={a._id} a={a} />)}
              </div>
            </div>
          )}

          {standardAnalyses.length > 0 && (
            <div>
              {investigations.length > 0 && (
                <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
                  Standard Analyses ({standardAnalyses.length})
                </h2>
              )}
              <div className="space-y-3">
                {standardAnalyses.map(a => <StandardAnalysisCard key={a._id} a={a} />)}
              </div>
            </div>
          )}
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
