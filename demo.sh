#!/usr/bin/env bash
# ============================================================================
#  Competitor Monitoring — Live Demo
#
#  This script runs the full pipeline:
#    1. Scrape baseline (v1)
#    2. Switch mock site to v2 (simulating competitor updates)
#    3. Scrape again + detect changes + AI analysis + Slack alerts
#
#  Prerequisites:
#    - Test site running:  ~/miniconda3/bin/python3 test-site/server.py
#    - API server running: ~/miniconda3/bin/python3 -m uvicorn api.main:app --port 8000
#    - .env has MONGODB_URI, SLACK_WEBHOOK_URL, OPENAI_API_KEY
#
#  Usage:
#    ./demo.sh              # Full automated demo (baseline → switch → detect → Slack)
#    ./demo.sh --watch      # Start autonomous monitoring (polls every 30s)
#    ./demo.sh --dry-run    # Full demo but don't send Slack alerts
# ============================================================================
set -e

PYTHON="${HOME}/miniconda3/bin/python3"
SCRIPTS_DIR="skills/competitor-monitoring/scripts"

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
MAGENTA="\033[35m"
DIM="\033[2m"
RESET="\033[0m"

divider() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
}

ts() { date "+%H:%M:%S"; }

step() {
    echo -e "${BOLD}${GREEN}[$(ts)] STEP $1:${RESET} ${BOLD}$2${RESET}"
}

DRY_RUN=""
WATCH=""
for arg in "$@"; do
    case "$arg" in
        --dry-run)  DRY_RUN="--dry-run" ;;
        --watch)    WATCH="yes" ;;
    esac
done

# ── Banner ────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "${BOLD}${CYAN}  ┌──────────────────────────────────────────────────────────┐${RESET}"
echo -e "${BOLD}${CYAN}  │       Competitor Monitoring — Live Demo                  │${RESET}"
echo -e "${BOLD}${CYAN}  │       Scrape → Detect → AI Analysis → Slack Alert        │${RESET}"
echo -e "${BOLD}${CYAN}  └──────────────────────────────────────────────────────────┘${RESET}"
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────────
echo -e "${BOLD}[$(ts)] Pre-flight checks...${RESET}"

# Check Python
if [ ! -x "$PYTHON" ]; then
    echo -e "${RED}  ✗ Python not found at $PYTHON${RESET}"
    exit 1
fi
echo -e "${GREEN}  ✓ Python found${RESET}"

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
    TEST_VERSION=$(curl -s http://localhost:8888/status 2>/dev/null | $PYTHON -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
    echo -e "${GREEN}  ✓ Test site running (version: ${TEST_VERSION})${RESET}"
else
    echo -e "${YELLOW}  ⚠ Test site not running — starting it now...${RESET}"
    $PYTHON test-site/server.py &
    TEST_PID=$!
    sleep 2
    if curl -s --max-time 3 http://localhost:8888/status &>/dev/null; then
        echo -e "${GREEN}  ✓ Test site started (PID: $TEST_PID)${RESET}"
    else
        echo -e "${RED}  ✗ Failed to start test site${RESET}"
        exit 1
    fi
fi

# Check API server
if curl -s --max-time 3 http://localhost:8000/api/dashboard &>/dev/null; then
    echo -e "${GREEN}  ✓ API server running at localhost:8000${RESET}"
else
    echo -e "${DIM}  ─ API server not running (dashboard won't update live, but Slack will work)${RESET}"
fi

divider

# ════════════════════════════════════════════════════════════════════════════
#  WATCH MODE — Autonomous background monitoring
# ════════════════════════════════════════════════════════════════════════════
if [ "$WATCH" = "yes" ]; then
    echo -e "${BOLD}${MAGENTA}  AUTONOMOUS MONITORING MODE${RESET}"
    echo ""
    echo -e "  The watcher is now polling all competitor sources every ${BOLD}30s${RESET}."
    echo -e "  When it detects changes, it will:"
    echo -e "    • Generate AI-powered strategic insights"
    echo -e "    • Send rich Slack alerts with severity + recommendations"
    echo -e "    • Update the dashboard in real time"
    echo ""
    echo -e "  ${BOLD}To trigger changes (in another terminal):${RESET}"
    echo -e "    ${CYAN}curl http://localhost:8888/switch/v2${RESET}"
    echo ""
    echo -e "  ${DIM}Press Ctrl+C to stop.${RESET}"
    divider

    exec $PYTHON "$SCRIPTS_DIR/watcher.py" \
        --interval 30 \
        --no-discover \
        $DRY_RUN \
        2>&1
fi

# ════════════════════════════════════════════════════════════════════════════
#  FULL DEMO — Automated end-to-end flow
# ════════════════════════════════════════════════════════════════════════════

# ── Step 1: Reset to v1 (baseline version) ────────────────────────────────
step 1 "Reset test site to v1 (baseline)"
curl -s http://localhost:8888/switch/v1 | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(f'  → {d[\"message\"]}')" 2>/dev/null || echo "  → Switched to v1"
sleep 1

# ── Step 2: Scrape baseline ──────────────────────────────────────────────
step 2 "Scraping baseline (v1 — the 'before' state)"
echo ""
$PYTHON "$SCRIPTS_DIR/watcher.py" --once --dry-run --no-discover 2>&1 | while IFS= read -r line; do
    echo -e "  ${DIM}${line}${RESET}"
done
echo ""
echo -e "  ${GREEN}✓ Baseline captured — all sources scraped${RESET}"

divider

# ── Step 3: Switch to v2 (simulate competitor updates) ───────────────────
step 3 "Switching test site to v2 (simulating competitor updates)"
echo ""
echo -e "  ${YELLOW}Simulating: TestRival just updated their website!${RESET}"
echo -e "  ${DIM}  • Pricing increased 25-34% across all plans${RESET}"
echo -e "  ${DIM}  • New AI-powered features added${RESET}"
echo -e "  ${DIM}  • New partnership with DataFlow Analytics${RESET}"
echo -e "  ${DIM}  • New blog post about Series B funding${RESET}"
echo ""
curl -s http://localhost:8888/switch/v2 | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(f'  → {d[\"message\"]}')" 2>/dev/null || echo "  → Switched to v2"
sleep 2

divider

# ── Step 4: Run full pipeline (scrape + detect + insights + alerts) ──────
step 4 "Running full pipeline — Scrape → Detect → AI Insights → Slack"
echo ""
if [ -n "$DRY_RUN" ]; then
    echo -e "  ${YELLOW}(Dry run — alerts will be shown but not sent to Slack)${RESET}"
    echo ""
fi

$PYTHON "$SCRIPTS_DIR/watcher.py" --once --no-discover $DRY_RUN 2>&1 | while IFS= read -r line; do
    # Highlight important lines
    if echo "$line" | grep -qi "change detected\|CRITICAL\|HIGH\|alert sent\|slack"; then
        echo -e "  ${BOLD}${MAGENTA}${line}${RESET}"
    elif echo "$line" | grep -qi "scraping\|checking\|generating"; then
        echo -e "  ${CYAN}${line}${RESET}"
    else
        echo -e "  ${DIM}${line}${RESET}"
    fi
done

divider

# ── Done ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}${GREEN}[$(ts)] ✅ Demo complete!${RESET}"
echo ""
echo -e "  ${BOLD}What happened:${RESET}"
echo -e "    1. 📡 Scraped all monitored competitor pages (baseline v1)"
echo -e "    2. 🔄 Competitor updated their website (switched to v2)"
echo -e "    3. 📡 Re-scraped and compared against baseline"
echo -e "    4. 🔍 Detected pricing, product, and partnership changes"
echo -e "    5. 🧠 Generated AI-powered strategic insights"
if [ -n "$DRY_RUN" ]; then
echo -e "    6. 📋 Formatted rich Slack alerts (dry run — not sent)"
else
echo -e "    6. 📨 Sent rich Slack alerts with severity + recommendations"
fi
echo ""
echo -e "  ${BOLD}Check results:${RESET}"
echo -e "    • ${CYAN}Slack${RESET} — alerts with severity badges and recommended actions"
echo -e "    • ${CYAN}Dashboard${RESET} — http://localhost:8000 (or your Render URL)"
echo ""
