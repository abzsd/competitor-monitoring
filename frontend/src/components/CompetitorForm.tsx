import { useState } from 'react';
import { createCompetitor } from '../api/client';

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function CompetitorForm({ onClose, onCreated }: Props) {
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [industry, setIndustry] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !domain.trim()) {
      setError('Name and domain are required');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await createCompetitor({
        name: name.trim(),
        domain: domain.trim(),
        industry: industry.trim(),
        description: description.trim(),
        tags: tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      });
      onCreated();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to create competitor');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-slate-800">Add Competitor</h2>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Name *</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Acme Corp"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Domain *</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={domain}
              onChange={e => setDomain(e.target.value)}
              placeholder="acmecorp.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Industry</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={industry}
              onChange={e => setIndustry(e.target.value)}
              placeholder="developer-tools"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Description</label>
            <textarea
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              rows={2}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief description of the competitor"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Tags (comma-separated)</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={tags}
              onChange={e => setTags(e.target.value)}
              placeholder="saas, api, developer-tools"
            />
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
              {loading ? 'Creating...' : 'Add Competitor'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
