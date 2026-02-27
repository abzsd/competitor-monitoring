import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { DashboardStats, ActivityLogEntry } from '../types';
import { getDashboard, triggerScan, getActivity } from '../api/client';
import StatCard from '../components/StatCard';
import SeverityBadge from '../components/SeverityBadge';
import LoadingSpinner from '../components/LoadingSpinner';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const STATUS_DOT: Record<string, string> = {
  info: 'bg-blue-400',
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  error: 'bg-red-400',
};

const STATUS_TEXT: Record<string, string> = {
  info: 'text-blue-600',
  success: 'text-emerald-600',
  warning: 'text-amber-600',
  error: 'text-red-600',
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  const load = () => {
    Promise.all([getDashboard(), getActivity(20)])
      .then(([s, a]) => { setStats(s); setActivity(a); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await triggerScan();
      setScanResult(`Scanned ${result.sources_scraped} sources, found ${result.changes_found} new change(s)`);
      load();
    } catch {
      setScanResult('Scan failed — check server logs');
    } finally {
      setScanning(false);
    }
  };

  // Poll activity log while scanning
  useEffect(() => {
    if (!scanning) return;
    const id = setInterval(() => {
      getActivity(20).then(setActivity).catch(() => {});
    }, 3000);
    return () => clearInterval(id);
  }, [scanning]);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <LoadingSpinner />;
  if (!stats) return <p className="text-slate-500">Failed to load dashboard</p>;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Live overview of your competitive intelligence pipeline</p>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
        >
          {scanning ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Scanning...
            </>
          ) : (
            'Run Scan Now'
          )}
        </button>
      </div>
      {scanResult && (
        <div className="mt-3 p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-700">
          {scanResult}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-5 gap-4 mt-6">
        <StatCard label="Competitors" value={stats.total_competitors} color="indigo" />
        <StatCard label="Active Sources" value={stats.active_sources} color="green" subtitle={stats.failing_sources > 0 ? `${stats.failing_sources} failing` : undefined} />
        <StatCard label="Changes (7d)" value={stats.total_changes_7d} color="amber" subtitle={`${stats.total_changes_30d} in 30d`} />
        <StatCard label="News Intel (7d)" value={stats.news_items_7d} color="blue" />
        <StatCard label="Alerts (24h)" value={stats.alerts_last_24h} color="red" />
      </div>

      {/* Failing sources warning */}
      {stats.failing_sources > 0 && (
        <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          {stats.failing_sources} source(s) have consecutive failures.{' '}
          <Link to="/sources" className="font-medium underline">View sources</Link>
        </div>
      )}

      {/* Changes by severity */}
      {Object.keys(stats.changes_by_severity).length > 0 && (
        <div className="mt-6 flex gap-3">
          {['critical', 'high', 'medium', 'low'].map(sev => {
            const count = stats.changes_by_severity[sev] || 0;
            if (!count) return null;
            const colors: Record<string, string> = {
              critical: 'bg-red-100 text-red-700',
              high: 'bg-orange-100 text-orange-700',
              medium: 'bg-yellow-100 text-yellow-700',
              low: 'bg-slate-100 text-slate-600',
            };
            return (
              <span key={sev} className={`px-3 py-1 rounded-full text-xs font-semibold ${colors[sev]}`}>
                {count} {sev}
              </span>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6 mt-6">
        {/* Recent changes — readable summaries */}
        <div className="col-span-2">
          <h2 className="text-base font-semibold text-slate-700 mb-3">Recent Changes</h2>
          {stats.recent_changes.length === 0 ? (
            <p className="text-sm text-slate-400">No changes detected yet</p>
          ) : (
            <div className="space-y-2">
              {stats.recent_changes.map(c => (
                <div key={c._id} className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-sm transition-shadow">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <SeverityBadge severity={c.severity} />
                        <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          {c.change_type?.replace(/_/g, ' ')}
                        </span>
                        <span className="text-xs text-slate-400">{c.competitor_name}</span>
                      </div>
                      <p className="text-sm font-medium text-slate-800 mt-1.5">{c.summary || '(no summary)'}</p>
                      <p className="text-xs text-slate-400 mt-1">{c.source_url}</p>
                    </div>
                    <div className="text-xs text-slate-400 whitespace-nowrap ml-4">
                      {c.detected_at ? timeAgo(c.detected_at) : ''}
                    </div>
                  </div>
                </div>
              ))}
              <Link to="/changes" className="block text-center text-sm text-indigo-600 hover:underline py-2">
                View all changes &rarr;
              </Link>
            </div>
          )}
        </div>

        {/* Right column: Activity Log + Competitor Activity */}
        <div className="space-y-6">
          {/* Activity Log */}
          <div>
            <h2 className="text-base font-semibold text-slate-700 mb-3">
              Activity Log
              {scanning && <span className="ml-2 inline-block h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />}
            </h2>
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden max-h-64 overflow-y-auto">
              {activity.length === 0 ? (
                <p className="px-3 py-4 text-center text-slate-400 text-xs">No activity yet — run a scan to see events here</p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {activity.map(a => (
                    <div key={a._id} className="px-3 py-2 flex items-start gap-2">
                      <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${STATUS_DOT[a.status] || 'bg-slate-300'}`} />
                      <div className="min-w-0 flex-1">
                        <p className={`text-xs font-medium truncate ${STATUS_TEXT[a.status] || 'text-slate-600'}`}>
                          {a.event.replace(/_/g, ' ')}
                        </p>
                        {a.detail && (
                          <p className="text-xs text-slate-500 truncate">{a.detail}</p>
                        )}
                      </div>
                      <span className="text-xs text-slate-300 whitespace-nowrap shrink-0">
                        {a.timestamp ? timeAgo(a.timestamp) : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Competitor Activity */}
          <div>
            <h2 className="text-base font-semibold text-slate-700 mb-3">Competitor Activity</h2>
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase">
                  <tr>
                    <th className="text-left px-3 py-2">Name</th>
                    <th className="text-right px-3 py-2">Sources</th>
                    <th className="text-right px-3 py-2">7d</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.competitor_activity.map(a => (
                    <tr key={a.slug} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <Link to={`/competitors/${a.slug}`} className="text-indigo-600 hover:underline font-medium">
                          {a.name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-right text-slate-500">{a.source_count}</td>
                      <td className="px-3 py-2 text-right">
                        <span className={a.change_count_7d > 0 ? 'text-amber-600 font-semibold' : 'text-slate-400'}>
                          {a.change_count_7d}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {stats.competitor_activity.length === 0 && (
                    <tr><td colSpan={3} className="px-3 py-4 text-center text-slate-400 text-xs">No competitors yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
