---
name: competitor-monitoring
description: >
  Agentic competitor monitoring system. Monitors competitor websites for changes,
  analyzes their significance using Claude LLM, discovers new sources autonomously,
  adapts crawling frequency, self-corrects on errors, generates strategic intelligence
  reports, and alerts via Slack.
user-invocable: true
metadata:
  openclaw:
    emoji: "🔍"
    requires:
      bins: ["python3"]
      env: ["MONGODB_URI", "TAVILY_API_KEY"]
---

# Competitor Monitoring Skill

You are a competitive intelligence agent. Your job is to monitor competitor websites, detect meaningful changes, analyze their business significance using AI reasoning, and alert the team.

## Agentic Capabilities

This system includes the following agentic behaviors:

- **LLM-Powered Analysis** — Claude enhances rule-based insights with strategic reasoning (set `ANTHROPIC_API_KEY` in `.env`)
- **Strategic Reasoning** — Cross-competitor trend analysis connects dots across all monitored competitors
- **Executive Summaries** — LLM-generated narrative briefings for weekly/monthly reports
- **Adaptive Crawling** — Automatically increases scrape frequency for active competitors, decreases for quiet ones
- **Autonomous Discovery** — Crawls page links (not just sitemaps) to find new monitorable pages
- **Self-Correction** — Retries with alternate strategies (different UA, dynamic Selenium) when scraping fails
- **Dynamic Browser Scraping** — Uses headless Chrome via Selenium for JS-heavy pages
- **Knowledge Base Updates** — Auto-maintains `references/competitor_kb.md` with learnings from each analysis
- **LLM Sentiment Analysis** — Claude-enhanced article sentiment analysis (falls back to keyword scoring)
- **Proactive News Search** — Tavily-powered web search finds competitor news, funding, and partnerships before they appear on websites
- **Deep Investigation** — When major changes are detected, automatically researches broader context via web search and full article extraction
- **Partnership Network Detection** — Discovers partnerships from news sources and press releases beyond just the competitor's own pages

## Available Scripts

All scripts are in `{baseDir}/scripts/`. Run them with `~/miniconda3/bin/python3` (required for MongoDB Atlas TLS support).

**IMPORTANT: Always use full absolute paths when running scripts.** Example:
```
~/miniconda3/bin/python3 {baseDir}/scripts/manage_sources.py list
~/miniconda3/bin/python3 {baseDir}/scripts/scrape.py http://localhost:8888/pricing --source-id <id>
~/miniconda3/bin/python3 {baseDir}/scripts/detect_changes.py --all
```
Never use `cd` + relative paths. Always pass the full path to the script.

| Script | Purpose |
|--------|---------|
| `manage_sources.py seed` | Seed competitors and sources from config into MongoDB |
| `manage_sources.py list [--competitor <slug>]` | List all monitored sources |
| `manage_sources.py add --url <url> --competitor <slug> --page-type <type>` | Add a new source |
| `scrape.py <url> [--source-id <id>] [--competitor-id <id>] [--page-type <type>]` | Scrape a URL and store snapshot |
| `scrape.py <url> --stdin` | Store HTML piped from browser tool |
| `detect_changes.py --all` | Detect changes across all sources |
| `detect_changes.py --competitor <slug>` | Detect changes for one competitor |
| `discover_sources.py <domain> [--competitor-id <id>] [--save]` | Discover new pages from sitemaps |
| `save_analysis.py --competitor-id <id> --change-ids <ids> --analysis '<json>'` | Save your analysis to MongoDB |
| `detect_partnerships.py --all [--save]` | Detect partnerships across all competitors |
| `detect_partnerships.py --competitor <slug> [--save]` | Detect partnerships for one competitor |
| `detect_partnerships.py --scan-text "<text>" --competitor-id <id>` | Scan arbitrary text for partnerships |
| `detect_partnerships.py --all --search-news --save` | Detect partnerships from snapshots + Tavily news search |
| `news_search.py --competitor <slug>` | Search Tavily for recent competitor news |
| `news_search.py --all [--days 14]` | Search news for all competitors (default: 7 days) |
| `news_search.py --all --no-alert` | Search without sending Slack alerts |
| `investigate.py --change-id <id>` | Deep investigation on a significant change |
| `investigate.py --change-json '<json>'` | Investigate from inline change JSON |
| `investigate.py --change-id <id> --no-extract` | Investigate without full article extraction (faster) |
| `analyze_sentiment.py --all` | Analyze news sentiment for all competitors |
| `analyze_sentiment.py --competitor <slug>` | Analyze news sentiment for one competitor |
| `generate_report.py --weekly [--competitor <slug>] [--format json\|markdown\|html]` | Generate weekly report |
| `generate_report.py --monthly [--competitor <slug>]` | Generate monthly report |
| `generate_insights.py --change-json '<json>'` | Generate LLM-enhanced analysis of a change |
| `generate_insights.py --change-json '<json>' --no-llm` | Generate rule-based analysis only (no LLM) |
| `strategic_reasoning.py --days 30` | Cross-competitor strategic analysis |
| `strategic_reasoning.py --days 7 --competitor <slug>` | Strategic analysis for one competitor |
| `format_slack.py --change '<json>' [--send]` | Format change alert as Slack Block Kit (basic) |
| `format_slack.py --rich-change '<json>' [--send]` | Format change + insights as rich Slack alert |
| `format_slack.py --analysis '<json>' [--send]` | Format analysis as Slack Block Kit |
| `format_slack.py --report '<json>' [--send]` | Format report as Slack Block Kit |
| `watcher.py [--interval 600] [--competitor <slug>]` | Continuous polling watcher (scrape -> detect -> insights -> alert) |
| `watcher.py --once [--dry-run]` | Run one watcher cycle then exit |
| `watcher.py --once --no-llm` | Run one cycle without LLM (rule-based only) |
| `setup_cron.py --print` | Show OpenClaw cron job commands |
| `setup_cron.py --execute --slack-channel <id>` | Register cron jobs with OpenClaw |
| `setup_cron.py --testing` | Use shorter cron intervals (10min/30min) for testing |
| `db.py setup` | Initialize MongoDB indexes |

## Core Workflows

### 1. Scrape Competitor Sources

When asked to scrape competitors:

1. Run `manage_sources.py list` to see all active sources
2. For each source:
   - If `scrape_method` is `static`: run `scrape.py <url> --source-id <id> --page-type <type>`
   - If `scrape_method` is `dynamic`: use the **browser** tool to navigate to the URL, wait for content to load, then get the page HTML and pipe it: `echo '<html>' | python3 scrape.py <url> --source-id <id> --stdin`
3. Check the output: `has_change: true` means new content was detected

For schedule-based scraping:
- `--schedule-group hourly` sources: pricing pages, critical product pages
- `--schedule-group daily` sources: all other pages
- `--schedule-group weekly` sources: careers, about pages

### 2. Detect Changes

After scraping, run change detection:

1. Run `detect_changes.py --all` (or `--competitor <slug>` for one competitor)
2. The output is a JSON array of detected changes with diffs
3. Each change has: `change_type`, `severity`, `text_diff`, `structured_diff`

### 3. Analyze Changes (YOU do this — not a script)

For each detected change, YOU analyze it as a competitive intelligence analyst:

1. Read the change diff output carefully
2. Read `{baseDir}/references/analysis_template.md` for the expected format
3. Consider:
   - **What changed?** Summarize the specific change
   - **Why does it matter?** Assess impact on our business
   - **What can we do?** Provide actionable insights
   - **What can we poach?** Identify ideas worth adopting
4. Save your analysis: `save_analysis.py --competitor-id <id> --change-ids <ids> --analysis '<json>'`

The analysis JSON format:
```json
{
  "summary": "One-line description of what changed",
  "impact_assessment": "Why this matters to our business",
  "actionable_insights": ["Action 1", "Action 2"],
  "category": "pricing|product|tech_stack|partnership|content|other",
  "confidence": 0.85
}
```

### 4. Send Alerts

After analysis, alert on changes with severity `medium` or higher:

**Rich Alerts (preferred — deep insights included):**
1. Run `detect_changes.py --all --with-snapshots` to get changes with full snapshot data
2. For each change, generate insights: `generate_insights.py --change '<change>' --old-snapshot '<old>' --new-snapshot '<new>'`
3. Format and send: `format_slack.py --rich-change '{"change": ..., "insights": ...}' --send`

**Basic Alerts (simple one-line summary):**
1. Format the change data: `format_slack.py --change '<change_json>' --send`
2. Or format an analysis: `format_slack.py --analysis '<analysis_json>' --send`

Rich alerts include: plan-by-plan pricing comparison, impact analysis, poachable ideas, recommended actions with team assignments, and detected signals (funding, product launches, hiring).

### 4b. Continuous Watcher (alternative to cron)

For real-time monitoring without cron jobs, use the watcher:

```
python3 watcher.py                         # Poll every 10 min, all competitors
python3 watcher.py --interval 60           # Poll every 60 seconds (testing)
python3 watcher.py --competitor testrival   # Watch one competitor
python3 watcher.py --once --dry-run        # One cycle, print alerts without sending
```

The watcher runs the full pipeline in a loop: scrape → detect changes → generate insights → format rich alert → send to Slack. It replaces the need for separate cron job steps.

The watcher also periodically discovers new pages on competitor domains (every 10 cycles by default) and auto-registers them for monitoring. Disable with `--no-discover`.

### 5. Discover New Sources

When asked to discover sources or on weekly schedule:

1. Run `discover_sources.py <domain> --competitor-id <id>` to find new pages
2. Review the discovered URLs — evaluate if they're worth monitoring
3. For valuable pages, run `manage_sources.py add` to register them
4. Use `web_search` to find news articles and announcements about the competitor

### 6. Detect Partnerships

Partnership detection combines multiple signals:

1. Run `detect_partnerships.py --all --save` to scan all competitor snapshots for partnership signals
2. Check the `detect_changes.py` output for `change_type: partnership_new`
3. Use the built-in news search mode: `detect_partnerships.py --all --search-news --save`
   This searches Tavily for partnership/integration news and extracts partner names automatically.
   News-discovered partnerships start at 0.5 confidence (lower than page-scraped partnerships).
4. For news articles found, feed the text to: `detect_partnerships.py --scan-text "<text>" --competitor-id <id>`
5. Review detected partnerships — the script assigns confidence scores:
   - 0.7+ = likely real, auto-saved with `--save`
   - 0.4-0.7 = possible, needs your review
   - Below 0.4 = filtered out
6. For confirmed partnerships, also save an analysis: `save_analysis.py --type partnership_analysis`

### 6b. Proactive News Search

Search for recent competitor news proactively:

1. Run `news_search.py --all` to search Tavily for funding, partnerships, product launches, and acquisitions
2. Each result is scored for relevance (0-1) using LLM analysis
3. Items with relevance >= 0.7 automatically trigger Slack alerts
4. All items are saved to the `news_items` collection for historical tracking
5. Use `--days 14` to widen the search window (default: 7 days)
6. Use `--no-alert` during testing to suppress Slack messages
7. For detected partnership news, feed relevant text to `detect_partnerships.py --scan-text`

### 6c. Deep Investigation

For significant (high/critical severity) changes, run a deep investigation:

1. Run `investigate.py --change-id <id>` to research a specific change
2. The script automatically:
   - Extracts key entities, dollar amounts, and keywords from the change
   - Searches Tavily for related news, press releases, and analyst coverage
   - Extracts full content from the top 3 most relevant URLs
   - Uses LLM to synthesize a comprehensive investigation report
   - Saves the investigation to the `analyses` collection (type: "investigation")
   - Marks the change as analyzed
3. The output includes: what happened, why it matters, market context, recommended response
4. Use `--no-extract` to skip full article extraction (faster but less context)

### 7. Market Sentiment & Performance

To analyze what's getting noticed:

1. Run `analyze_sentiment.py --all` to get automated sentiment scores from Google News RSS
2. Each competitor gets: overall score (-1 to 1), positive/negative signals, opportunity signals
3. **Opportunity signals** are negative events (layoffs, outages, complaints) that create openings for us
4. Supplement with `web_search` for: `"<competitor name>" review OR launch OR announcement OR funding`
5. YOU should interpret the raw sentiment data with nuance — the keyword scoring is a starting point
6. Identify what's working for them that we could adopt ("poachable" ideas)

### 8. Weekly Summary Report

Generate a weekly competitive intelligence digest:

1. Run `generate_report.py --weekly` to compile changes, analyses, and partnerships from the past 7 days
2. The report includes: severity breakdown, per-competitor sections, top actionable insights
3. For richer context, also run `analyze_sentiment.py --all` and incorporate sentiment trends
4. Use `web_search` for any breaking competitive news not captured by scrapers
5. Send the report to Slack: `generate_report.py --weekly --format json | python3 format_slack.py --report "$(cat)" --send`
6. YOU should add your own executive commentary on top of the generated report — what's the narrative?

For monthly reports: `generate_report.py --monthly`
For a specific competitor: `generate_report.py --weekly --competitor <slug>`

## Important Guidelines

- **Rate limiting**: Wait at least 2 seconds between requests to the same domain
- **Error handling**: If a scrape fails, note it but continue with other sources. After 10 consecutive failures for a source, flag it for review.
- **Universal extraction**: The scraper extracts structured data (headings, stats, sections, CTAs, features) from ALL page types — not just pricing/product. This means any page produces rich change analysis.
- **Auto-discovery**: The watcher periodically discovers new pages via sitemaps and auto-registers them. All relevant URLs are monitored, not just known path patterns.
- **Signal detection**: Funding, product launches, hiring, and partnership signals are detected across ALL change types and boost severity automatically.
- **Content focus**: Ignore cosmetic changes (styling, layout). Focus on substantive content changes.
- **Severity guide**:
  - **Critical**: Pricing changes >20%, acquisitions, major product launches
  - **High**: Any pricing change, new partnerships, major feature changes
  - **Medium**: Product page updates, tech stack changes, notable blog posts
  - **Low**: Minor text edits, blog posts about culture/hiring
- **Knowledge base**: Automatically updated after each analysis by `update_knowledge_base()`. Manual updates via `{baseDir}/references/competitor_kb.md`.
- **Auto-disable**: Sources are automatically disabled after 10 consecutive scrape failures. A warning is logged at 3 failures. Check for disabled sources periodically and investigate.
- **Self-correction**: After 3 failures, the watcher tries alternate scraping strategies (different User-Agent, Selenium). After 5, it reduces frequency. After 10, it disables the source.
- **Adaptive crawling**: The watcher automatically promotes daily→hourly when competitors are active (>2 changes/day) and demotes hourly→daily when quiet (<0.1/day).
- **LLM graceful degradation**: If `ANTHROPIC_API_KEY` is not set or has no credits, all features work in rule-based mode. No crashes or errors — just simpler insights.
- **Dynamic scraping**: Set `scrape_method: dynamic` on a source to use Selenium. The self-correction logic may auto-switch sources to dynamic if static consistently fails.
- **Slack formatting**: Always prefer `format_slack.py` for Slack alerts — it produces rich Block Kit messages with structured fields, severity colors, and diff previews.
