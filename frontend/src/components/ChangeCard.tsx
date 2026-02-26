import { useState } from 'react';
import type { Change } from '../types';
import SeverityBadge from './SeverityBadge';
import { getChange } from '../api/client';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ChangeCard({ change }: { change: Change }) {
  const [expanded, setExpanded] = useState(false);
  const [diff, setDiff] = useState<string | null>(null);

  const handleExpand = async () => {
    if (!expanded && !diff) {
      try {
        const detail = await getChange(change._id);
        setDiff(detail.text_diff || '(no diff available)');
      } catch {
        setDiff('(failed to load diff)');
      }
    }
    setExpanded(e => !e);
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between cursor-pointer" onClick={handleExpand}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <SeverityBadge severity={change.severity} />
            <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
              {change.change_type?.replace(/_/g, ' ')}
            </span>
            <span className="text-xs text-slate-400">{change.competitor_name}</span>
          </div>
          <p className="text-sm font-medium text-slate-800 mt-1.5 truncate">{change.summary || '(no summary)'}</p>
          <p className="text-xs text-slate-400 mt-1">{change.source_url}</p>
        </div>
        <div className="text-xs text-slate-400 whitespace-nowrap ml-4">
          {change.detected_at ? timeAgo(change.detected_at) : ''}
        </div>
      </div>
      {expanded && diff && (
        <pre className="mt-3 p-3 bg-slate-900 text-slate-200 rounded-lg text-xs overflow-x-auto max-h-80 whitespace-pre-wrap">
          {diff.split('\n').map((line, i) => {
            let cls = '';
            if (line.startsWith('+')) cls = 'text-emerald-400';
            else if (line.startsWith('-')) cls = 'text-red-400';
            else if (line.startsWith('@')) cls = 'text-blue-400';
            return <div key={i} className={cls}>{line}</div>;
          })}
        </pre>
      )}
    </div>
  );
}
