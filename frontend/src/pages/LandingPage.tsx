import { Link } from 'react-router-dom';

const features = [
  {
    category: 'LLM-Powered Intelligence',
    color: 'violet',
    icon: '\uD83E\uDDE0',
    items: [
      {
        title: 'Deep Strategic Analysis',
        description:
          'Claude API produces rich strategic insights from every detected change — impact assessment, competitive implications, and recommended actions.',
      },
      {
        title: 'Sentiment & Positioning Analysis',
        description:
          'LLM-powered sentiment analysis understands nuanced messaging shifts, tone changes, and competitive positioning across pages.',
      },
      {
        title: 'Executive Summary Reports',
        description:
          'Weekly AI-generated strategy memos synthesizing all changes into executive briefings with risk assessments and recommendations.',
      },
    ],
  },
  {
    category: 'Research & Investigation',
    color: 'blue',
    icon: '\uD83D\uDD0D',
    items: [
      {
        title: 'Proactive News Search',
        description:
          'Automatically searches the web for competitor news, funding rounds, and partnership announcements before they hit their website.',
      },
      {
        title: 'Deep Investigation',
        description:
          'When a major change is detected, the agent follows links, researches context, and gathers evidence to build a complete intelligence picture.',
      },
      {
        title: 'Partnership Network Detection',
        description:
          'Discovers partnerships from news sources, press releases, and integration directories — beyond just the competitor\'s own pages.',
      },
    ],
  },
  {
    category: 'Cross-Competitor Intelligence',
    color: 'amber',
    icon: '\uD83C\uDFAF',
    items: [
      {
        title: 'Strategic Reasoning Engine',
        description:
          'Connects dots across multiple competitors. When 3 of 5 raise prices, it recognizes a market-wide shift, not isolated events.',
      },
      {
        title: 'Living Knowledge Base',
        description:
          'Automatically maintains a structured knowledge base with learnings from every cycle. Each scan makes the system smarter.',
      },
    ],
  },
  {
    category: 'Infrastructure & Automation',
    color: 'emerald',
    icon: '\u2699\uFE0F',
    items: [
      {
        title: 'Dynamic Browser Scraping',
        description:
          'Selenium-powered scraping for JS-heavy pages. Renders SPAs, interacts with elements, captures dynamically loaded content.',
      },
      {
        title: 'Autonomous Source Discovery',
        description:
          'Crawls competitor domains to discover new pages worth monitoring — pricing, features, careers. No manual URL entry needed.',
      },
      {
        title: 'Adaptive Crawl Frequency',
        description:
          'Auto-increases monitoring when a competitor is actively changing, reduces during quiet periods. Smart resource allocation.',
      },
      {
        title: 'Self-Correcting Pipeline',
        description:
          'Auto-retries with different strategies when scraping fails — switching methods, adjusting timeouts, rotating approaches.',
      },
    ],
  },
];

const COLORS: Record<string, { card: string; tag: string; dot: string }> = {
  violet: { card: 'border-violet-200 hover:border-violet-400 hover:shadow-violet-50', tag: 'bg-violet-100 text-violet-700', dot: 'bg-violet-500' },
  blue: { card: 'border-blue-200 hover:border-blue-400 hover:shadow-blue-50', tag: 'bg-blue-100 text-blue-700', dot: 'bg-blue-500' },
  amber: { card: 'border-amber-200 hover:border-amber-400 hover:shadow-amber-50', tag: 'bg-amber-100 text-amber-700', dot: 'bg-amber-500' },
  emerald: { card: 'border-emerald-200 hover:border-emerald-400 hover:shadow-emerald-50', tag: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-500' },
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Hero ────────────────────────────────────────── */}
      <header className="bg-slate-900 text-white">
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-24">
          <p className="text-indigo-400 text-sm font-semibold tracking-wider uppercase mb-3">
            Autonomous Competitive Intelligence
          </p>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight leading-tight max-w-3xl">
            Monitor competitors.<br />
            Detect changes.<br />
            Act before they do.
          </h1>
          <p className="text-slate-400 text-lg mt-5 max-w-2xl leading-relaxed">
            An AI-powered agent that scrapes competitor websites, detects pricing
            changes, product launches, and partnerships, then delivers strategic
            insights straight to your Slack — 24/7, fully autonomous.
          </p>
          <div className="flex items-center gap-4 mt-8">
            <Link
              to="/dashboard"
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg transition-colors text-sm"
            >
              Open Dashboard &rarr;
            </Link>
            <a
              href="#capabilities"
              className="px-6 py-3 border border-slate-600 hover:border-slate-400 text-slate-300 hover:text-white font-medium rounded-lg transition-colors text-sm"
            >
              View Capabilities
            </a>
          </div>

        </div>
      </header>

      {/* ── Pipeline ────────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 py-14">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-6">
          How it works
        </h2>
        <div className="bg-white rounded-2xl border border-slate-200 p-8">
          <div className="flex items-center justify-between gap-3">
            {[
              { step: 'Scrape', desc: 'Monitor competitor pages on schedule', icon: '\uD83D\uDCE1' },
              { step: 'Detect', desc: 'Compare snapshots, find changes', icon: '\uD83D\uDD0D' },
              { step: 'Analyze', desc: 'LLM generates strategic insights', icon: '\uD83E\uDDE0' },
              { step: 'Research', desc: 'Search news for deeper context', icon: '\uD83D\uDCDA' },
              { step: 'Alert', desc: 'Slack alerts + live dashboard', icon: '\uD83D\uDCE8' },
            ].map((s, i) => (
              <div key={s.step} className="flex items-center gap-3 flex-1">
                <div className="text-center flex-1">
                  <div className="text-3xl mb-2">{s.icon}</div>
                  <div className="text-sm font-bold text-slate-800">{s.step}</div>
                  <div className="text-xs text-slate-400 mt-1">{s.desc}</div>
                </div>
                {i < 4 && (
                  <div className="text-slate-200 text-2xl shrink-0">&rarr;</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Capabilities ────────────────────────────────── */}
      <section id="capabilities" className="max-w-6xl mx-auto px-6 pb-14">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-8">
          Agent Capabilities
        </h2>

        {features.map((cat) => {
          const c = COLORS[cat.color] || COLORS.violet;
          return (
            <div key={cat.category} className="mb-12">
              <div className="flex items-center gap-3 mb-5">
                <span className={`h-2.5 w-2.5 rounded-full ${c.dot}`} />
                <h3 className="text-xl font-bold text-slate-800">
                  {cat.icon} {cat.category}
                </h3>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${c.tag}`}>
                  {cat.items.length}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {cat.items.map((item) => (
                  <div
                    key={item.title}
                    className={`bg-white rounded-xl border ${c.card} p-5 transition-all hover:shadow-lg`}
                  >
                    <h4 className="text-sm font-bold text-slate-800 mb-2">
                      {item.title}
                    </h4>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {item.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </section>

      {/* ── Tech Stack ──────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 pb-14">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
          Built with
        </h2>
        <div className="flex flex-wrap gap-2">
          {[
            'Python', 'FastAPI', 'React + TypeScript', 'MongoDB Atlas',
            'Claude API', 'OpenClaw', 'Slack Block Kit', 'Selenium', 'Tailwind CSS',
          ].map((tech) => (
            <span
              key={tech}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-600"
            >
              {tech}
            </span>
          ))}
        </div>
      </section>

      {/* ── CTA Footer ──────────────────────────────────── */}
      <section className="bg-slate-900 text-white">
        <div className="max-w-6xl mx-auto px-6 py-14 text-center">
          <h2 className="text-2xl font-bold">Ready to see it in action?</h2>
          <p className="text-slate-400 mt-2">
            Open the dashboard to view live competitor intelligence.
          </p>
          <Link
            to="/dashboard"
            className="inline-block mt-6 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg transition-colors"
          >
            Open Dashboard &rarr;
          </Link>
        </div>
      </section>
    </div>
  );
}
