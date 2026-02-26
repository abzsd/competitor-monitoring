import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { DashboardStats } from '../types';
import { getDashboard, triggerScan } from '../api/client';
import StatCard from '../components/StatCard';
import ChangeCard from '../components/ChangeCard';
import LoadingSpinner from '../components/LoadingSpinner';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  const load = () => {
    getDashboard()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await triggerScan();
      setScanResult(`Scanned ${result.sources_scraped} sources, found ${result.changes_found} new change(s)`);
      load(); // Refresh dashboard
    } catch {
      setScanResult('Scan failed — check server logs');
    } finally {
      setScanning(false);
    }
  };

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
      <div className="grid grid-cols-4 gap-4 mt-6">
        <StatCard label="Competitors" value={stats.total_competitors} color="indigo" />
        <StatCard label="Active Sources" value={stats.active_sources} color="green" subtitle={stats.failing_sources > 0 ? `${stats.failing_sources} failing` : undefined} />
        <StatCard label="Changes (7d)" value={stats.total_changes_7d} color="amber" subtitle={`${stats.total_changes_30d} in 30d`} />
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
        {/* Recent changes */}
        <div className="col-span-2">
          <h2 className="text-base font-semibold text-slate-700 mb-3">Recent Changes</h2>
          {stats.recent_changes.length === 0 ? (
            <p className="text-sm text-slate-400">No changes detected yet</p>
          ) : (
            <div className="space-y-2">
              {stats.recent_changes.map(c => <ChangeCard key={c._id} change={c} />)}
            </div>
          )}
        </div>

        {/* Competitor activity */}
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
  );
}
