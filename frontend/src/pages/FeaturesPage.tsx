const features = [
  {
    category: 'LLM-Powered Intelligence',
    color: 'violet',
    icon: '\uD83E\uDDE0',
    items: [
      {
        title: 'Deep Strategic Analysis',
        description:
          'Uses Claude API to produce rich, strategic insights from every detected change \u2014 not just keyword templates, but real competitive intelligence with impact assessment and recommended actions.',
        tags: ['Claude API', 'generate_insights.py'],
      },
      {
        title: 'Sentiment & Positioning Analysis',
        description:
          'LLM-powered sentiment analysis replaces simple keyword scoring. Understands nuanced messaging shifts, tone changes, and competitive positioning across product and marketing pages.',
        tags: ['NLP', 'analyze_sentiment.py'],
      },
      {
        title: 'Executive Summary Reports',
        description:
          'Weekly AI-generated strategy memos that synthesize all detected changes into an executive briefing with key takeaways, risk assessments, and strategic recommendations.',
        tags: ['Reporting', 'generate_report.py'],
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
          'Automatically searches the web for competitor news, funding rounds, and partnership announcements \u2014 catching signals before they even appear on competitor websites.',
        tags: ['Web Search', 'news_search.py'],
      },
      {
        title: 'Deep Investigation',
        description:
          'When a major change is detected, the agent automatically follows links, researches context, and gathers supporting evidence to build a complete intelligence picture.',
        tags: ['Auto-Research', 'investigate.py'],
      },
      {
        title: 'Partnership Network Detection',
        description:
          'Discovers partnerships from news sources, press releases, and integration directories \u2014 going far beyond just monitoring the competitor\'s own partnerships page.',
        tags: ['Partnerships', 'detect_partnerships.py'],
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
          'Connects dots across multiple competitors to identify market-wide shifts. When 3 of 5 competitors raise prices, the system recognizes this as a market trend, not isolated events.',
        tags: ['Multi-Competitor', 'Strategic AI'],
      },
      {
        title: 'Living Knowledge Base',
        description:
          'Automatically maintains and updates a structured knowledge base with learnings from every analysis cycle. Each scan makes the system smarter and more context-aware.',
        tags: ['Knowledge Base', 'competitor_kb.md'],
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
          'Selenium-powered scraping for JavaScript-heavy pages that static HTTP requests can\'t handle. Renders SPAs, interacts with elements, and captures dynamically loaded content.',
        tags: ['Selenium', 'Dynamic Pages'],
      },
      {
        title: 'Autonomous Source Discovery',
        description:
          'Crawls competitor domains to automatically discover new pages worth monitoring \u2014 new pricing pages, feature announcements, career pages, and more. No manual URL entry needed.',
        tags: ['Auto-Discovery', 'discover_sources.py'],
      },
      {
        title: 'Adaptive Crawl Frequency',
        description:
          'Automatically increases monitoring frequency when a competitor is actively changing, and reduces it during quiet periods. Sources that change often get checked more frequently.',
        tags: ['Smart Scheduling', 'Adaptive'],
      },
      {
        title: 'Self-Correcting Pipeline',
        description:
          'When scraping fails, the agent automatically retries with different strategies \u2014 switching from static to dynamic scraping, adjusting timeouts, and rotating approaches until it succeeds.',
        tags: ['Fault Tolerance', 'Auto-Retry'],
      },
    ],
  },
];

const CATEGORY_STYLES: Record<string, { badge: string; border: string; glow: string }> = {
  violet: {
    badge: 'bg-violet-100 text-violet-700',
    border: 'border-violet-200 hover:border-violet-300',
    glow: 'hover:shadow-violet-100',
  },
  blue: {
    badge: 'bg-blue-100 text-blue-700',
    border: 'border-blue-200 hover:border-blue-300',
    glow: 'hover:shadow-blue-100',
  },
  amber: {
    badge: 'bg-amber-100 text-amber-700',
    border: 'border-amber-200 hover:border-amber-300',
    glow: 'hover:shadow-amber-100',
  },
  emerald: {
    badge: 'bg-emerald-100 text-emerald-700',
    border: 'border-emerald-200 hover:border-emerald-300',
    glow: 'hover:shadow-emerald-100',
  },
};

export default function FeaturesPage() {
  return (
    <div className="max-w-5xl">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-slate-800 tracking-tight">
          Agent Capabilities
        </h1>
        <p className="text-base text-slate-500 mt-2 max-w-2xl">
          An autonomous AI agent that monitors competitor websites, detects
          changes, generates strategic insights, and delivers actionable
          intelligence to your team — 24/7, without human intervention.
        </p>
        <div className="flex gap-3 mt-4">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            12 capabilities
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">
            4 intelligence layers
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
            Fully autonomous
          </span>
        </div>
      </div>

      {/* Pipeline overview */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-10">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
          How it works
        </h2>
        <div className="flex items-center justify-between gap-2">
          {[
            { step: 'Scrape', desc: 'Monitor pages', icon: '\uD83D\uDCE1' },
            { step: 'Detect', desc: 'Find changes', icon: '\uD83D\uDD0D' },
            { step: 'Analyze', desc: 'AI insights', icon: '\uD83E\uDDE0' },
            { step: 'Research', desc: 'Deep context', icon: '\uD83D\uDCDA' },
            { step: 'Alert', desc: 'Slack + Dashboard', icon: '\uD83D\uDCE8' },
          ].map((s, i) => (
            <div key={s.step} className="flex items-center gap-2 flex-1">
              <div className="text-center flex-1">
                <div className="text-2xl mb-1">{s.icon}</div>
                <div className="text-sm font-semibold text-slate-800">{s.step}</div>
                <div className="text-xs text-slate-400">{s.desc}</div>
              </div>
              {i < 4 && (
                <div className="text-slate-300 text-lg shrink-0">&rarr;</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Feature categories */}
      {features.map((cat) => {
        const styles = CATEGORY_STYLES[cat.color] || CATEGORY_STYLES.violet;
        return (
          <div key={cat.category} className="mb-10">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-2xl">{cat.icon}</span>
              <div>
                <h2 className="text-lg font-bold text-slate-800">
                  {cat.category}
                </h2>
                <p className="text-xs text-slate-400">
                  {cat.items.length} capabilities
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {cat.items.map((item) => (
                <div
                  key={item.title}
                  className={`bg-white rounded-xl border ${styles.border} p-5 transition-all hover:shadow-md ${styles.glow}`}
                >
                  <h3 className="text-sm font-bold text-slate-800 mb-2">
                    {item.title}
                  </h3>
                  <p className="text-xs text-slate-500 leading-relaxed mb-3">
                    {item.description}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className={`px-2 py-0.5 rounded text-xs font-medium ${styles.badge}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {/* Tech stack footer */}
      <div className="bg-slate-50 rounded-xl border border-slate-200 p-6 mb-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Tech Stack
        </h2>
        <div className="flex flex-wrap gap-2">
          {[
            'Python',
            'FastAPI',
            'React + TypeScript',
            'MongoDB Atlas',
            'Claude API',
            'OpenClaw',
            'Slack Webhooks',
            'Selenium',
            'Tailwind CSS',
          ].map((tech) => (
            <span
              key={tech}
              className="px-3 py-1 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-600"
            >
              {tech}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
