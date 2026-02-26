import { NavLink } from 'react-router-dom';

const links = [
  { to: '/', label: 'Dashboard', icon: '⊞' },
  { to: '/competitors', label: 'Competitors', icon: '⊕' },
  { to: '/sources', label: 'Sources', icon: '◎' },
  { to: '/changes', label: 'Changes', icon: '△' },
  { to: '/analyses', label: 'Analyses', icon: '◆' },
];

export default function Sidebar() {
  return (
    <aside className="fixed top-0 left-0 h-screen w-60 bg-slate-900 text-white flex flex-col z-30">
      <div className="px-5 py-6 border-b border-slate-700">
        <h1 className="text-lg font-bold tracking-tight">Competitor Monitor</h1>
        <p className="text-xs text-slate-400 mt-0.5">Intelligence Dashboard</p>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(l => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <span className="text-base">{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-slate-700 text-xs text-slate-500">
        v1.0.0
      </div>
    </aside>
  );
}
