#!/usr/bin/env bash
# ============================================================================
#  Competitor Monitoring — Live Demo (via OpenClaw)
#
#  This script uses OpenClaw to run the competitor-monitoring skill,
#  which scrapes competitor sites, detects changes, generates AI insights,
#  and sends rich Slack alerts.
#
#  Usage:
#    ./demo.sh                  # Full pipeline via OpenClaw → Slack alerts
#    ./demo.sh --dry-run        # Detect + analyze but don't send to Slack
#    ./demo.sh --baseline       # Scrape baseline (run BEFORE making changes)
# ============================================================================
set -e

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
MAGENTA="\033[35m"
RESET="\033[0m"

divider() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
}

timestamp() {
    date "+%H:%M:%S"
}

DRY_RUN=""
BASELINE=""
for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN="--dry-run" ;;
        --baseline) BASELINE="yes" ;;
    esac
done

# ── Banner ──────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "${BOLD}${CYAN}  ┌──────────────────────────────────────────────────────────┐${RESET}"
echo -e "${BOLD}${CYAN}  │  🦞  Competitor Monitoring — Live Demo via OpenClaw      │${RESET}"
echo -e "${BOLD}${CYAN}  │      Scrape → Detect → AI Analysis → Slack Alert        │${RESET}"
echo -e "${BOLD}${CYAN}  └──────────────────────────────────────────────────────────┘${RESET}"
echo ""

# ── Pre-flight checks ──────────────────────────────────────────────────────
echo -e "${BOLD}[$(timestamp)] Pre-flight checks...${RESET}"

# Check OpenClaw
if ! command -v openclaw &>/dev/null; then
    echo -e "${RED}  ✗ openclaw CLI not found. Install from https://docs.openclaw.ai${RESET}"
    exit 1
fi
OPENCLAW_VERSION=$(openclaw --version 2>&1 | head -1)
echo -e "${GREEN}  ✓ OpenClaw installed (${OPENCLAW_VERSION})${RESET}"

# Check skill
if ! openclaw skills list 2>&1 | grep -q "competitor"; then
    echo -e "${RED}  ✗ competitor-monitoring skill not found${RESET}"
    exit 1
fi
echo -e "${GREEN}  ✓ competitor-monitoring skill ready${RESET}"

# Check .env
if [ ! -f .env ]; then
    echo -e "${RED}  ✗ .env file not found${RESET}"
    exit 1
fi
echo -e "${GREEN}  ✓ .env found${RESET}"

if ! grep -q "SLACK_WEBHOOK_URL" .env; then
    echo -e "${RED}  ✗ SLACK_WEBHOOK_URL not set in .env${RESET}"
    exit 1
fi
echo -e "${GREEN}  ✓ Slack webhook configured${RESET}"

# Check test site
if curl -s --max-time 3 http://localhost:8888/status &>/dev/null; then
    TEST_VERSION=$(curl -s http://localhost:8888/status 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
    echo -e "${GREEN}  ✓ Test site running (version: ${TEST_VERSION})${RESET}"
else
    echo -e "${YELLOW}  ⚠ Test site not running at localhost:8888${RESET}"
    echo -e "${YELLOW}    Start it:  ~/miniconda3/bin/python3 test-site/server.py${RESET}"
    exit 1
fi

divider

# ── Baseline mode: just scrape, no detection ────────────────────────────────
if [ "$BASELINE" = "yes" ]; then
    echo -e "${BOLD}[$(timestamp)] BASELINE MODE — Scraping current state (${TEST_VERSION})...${RESET}"
    echo ""
    echo -e "  ${MAGENTA}Asking OpenClaw to scrape all sources and store baselines...${RESET}"
    echo ""

    openclaw agent --local --session-id "competitor-demo" --message \
        "Run the competitor-monitoring skill. Scrape ALL active sources using scrape.py. Just scrape — do NOT run change detection or send alerts. List each source you scrape and confirm success. Use ~/miniconda3/bin/python3 for all script execution." \
        2>&1 | tee /tmp/openclaw-baseline.log

    divider
    echo -e "${BOLD}[$(timestamp)] ✅ Baseline captured!${RESET}"
    echo ""
    echo -e "  ${BOLD}Next steps:${RESET}"
    echo -e "    1. Switch the test site to v2:  ${CYAN}curl http://localhost:8888/switch/v2${RESET}"
    echo -e "    2. Run detection:               ${CYAN}./demo.sh${RESET}"
    echo ""
    exit 0
fi

# ── Full pipeline via OpenClaw ──────────────────────────────────────────────
echo -e "${BOLD}[$(timestamp)] Launching OpenClaw agent...${RESET}"
echo ""
echo -e "  ${MAGENTA}🦞 OpenClaw is running the competitor-monitoring skill${RESET}"
echo -e "  ${MAGENTA}   Pipeline: Scrape → Detect Changes → AI Insights → Slack Alerts${RESET}"
echo ""

# Build the OpenClaw message based on flags
if [ -n "$DRY_RUN" ]; then
    OPENCLAW_MSG="Run the competitor-monitoring skill — FULL PIPELINE (DRY RUN):
1) List all active sources with manage_sources.py list.
2) Scrape each source using scrape.py with the correct --source-id and --page-type.
3) Run detect_changes.py --all to detect changes.
4) For each detected change, generate deep insights using generate_insights.py.
5) Format rich Slack alerts using format_slack.py for each change.
6) Print the formatted alerts but DO NOT send to Slack (this is a dry run).
7) Print a summary of all changes found with severity and type.
Use ~/miniconda3/bin/python3 for all scripts. All scripts are in skills/competitor-monitoring/scripts/."
else
    OPENCLAW_MSG="Run the competitor-monitoring skill — FULL PIPELINE:
1) List all active sources with manage_sources.py list.
2) Scrape each source using scrape.py with the correct --source-id and --page-type.
3) Run detect_changes.py --all to detect changes.
4) For each detected change, generate deep insights using generate_insights.py.
5) Format rich Slack alerts using format_slack.py --rich-change and SEND them with --send.
6) Print a summary of all changes found with severity, type, and whether Slack alert was sent.
Use ~/miniconda3/bin/python3 for all scripts. All scripts are in skills/competitor-monitoring/scripts/."
fi

openclaw agent --local --session-id "competitor-demo" --message "$OPENCLAW_MSG" 2>&1 | tee /tmp/openclaw-demo.log

divider

# ── Summary ─────────────────────────────────────────────────────────────────
echo -e "${BOLD}[$(timestamp)] ✅ Demo complete!${RESET}"
echo ""
echo -e "  ${BOLD}What OpenClaw did:${RESET}"
echo -e "    1. 🦞 Read the competitor-monitoring skill definition"
echo -e "    2. 📡 Scraped all monitored competitor pages"
echo -e "    3. 🔍 Compared snapshots to detect changes"
echo -e "    4. 🧠 Generated AI-powered strategic insights"
if [ -n "$DRY_RUN" ]; then
echo -e "    5. 📋 Formatted Slack alerts (dry run — not sent)"
else
echo -e "    5. 📨 Sent rich Slack alerts with severity, impact, and recommendations"
fi
echo ""
echo -e "  ${BOLD}Check results:${RESET}"
echo -e "    • ${CYAN}Slack${RESET} — look for alerts with severity badges and recommended actions"
echo -e "    • ${CYAN}Dashboard${RESET} — refresh your Render dashboard to see new changes"
echo ""
echo -e "  ${BOLD}Full log:${RESET} /tmp/openclaw-demo.log"
echo ""
