import { useEffect, useState } from 'react';
import { createSource, getCompetitors } from '../api/client';
import type { Competitor } from '../types';

interface Props {
  onClose: () => void;
  onCreated: () => void;
  preselectedCompetitorId?: string;
}

const PAGE_TYPES = ['pricing', 'product', 'tech_stack', 'partnerships', 'blog', 'news', 'changelog', 'careers', 'landing', 'other'];
const SCRAPE_METHODS = ['static', 'dynamic'];
const SCHEDULES = ['hourly', 'daily', 'weekly'];

export default function SourceForm({ onClose, onCreated, preselectedCompetitorId }: Props) {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [competitorId, setCompetitorId] = useState(preselectedCompetitorId || '');
  const [url, setUrl] = useState('');
  const [pageType, setPageType] = useState('pricing');
  const [scrapeMethod, setScrapeMethod] = useState('static');
  const [schedule, setSchedule] = useState('daily');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getCompetitors().then(setCompetitors).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!competitorId || !url.trim()) {
      setError('Competitor and URL are required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await createSource({
        competitor_id: competitorId,
        url: url.trim(),
        page_type: pageType,
        scrape_method: scrapeMethod,
        schedule_group: schedule,
      });
      onCreated();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to add source');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-slate-800">Add Source URL</h2>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Competitor *</label>
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={competitorId}
              onChange={e => setCompetitorId(e.target.value)}
            >
              <option value="">Select competitor...</option>
              {competitors.map(c => (
                <option key={c._id} value={c._id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">URL *</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://competitor.com/pricing"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700">Page Type</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={pageType}
                onChange={e => setPageType(e.target.value)}
              >
                {PAGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Scrape Method</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={scrapeMethod}
                onChange={e => setScrapeMethod(e.target.value)}
              >
                {SCRAPE_METHODS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Schedule</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={schedule}
                onChange={e => setSchedule(e.target.value)}
              >
                {SCHEDULES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? 'Adding...' : 'Add Source'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
