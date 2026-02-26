#!/usr/bin/env python3
"""Generate OpenClaw cron job commands for competitor monitoring.

Usage:
    python3 setup_cron.py --print          # Print cron add commands
    python3 setup_cron.py --execute        # Execute cron add commands via openclaw CLI
    python3 setup_cron.py --slack-channel <channel_id>  # Set Slack delivery channel
    python3 setup_cron.py --timezone "US/Pacific"

This generates three cron jobs:
    1. Hourly: Scrape critical (hourly) sources + detect + alert
    2. Daily:  Full scrape + detect + analyze + alert + update KB
    3. Weekly: Source discovery + partnership scan + summary report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def build_cron_jobs(
    slack_channel: str = "",
    timezone: str = "US/Pacific",
    testing: bool = False,
) -> list[dict]:
    """Build the three cron job definitions."""

    delivery_args = ""
    if slack_channel:
        delivery_args = f" --deliver --to \"{slack_channel}\""

    # Testing mode: every 10 min instead of hourly, every 30 min instead of daily
    hourly_cron = "*/10 * * * *" if testing else "0 * * * *"
    daily_cron = "*/30 * * * *" if testing else "0 7 * * *"
    weekly_cron = "0 * * * *" if testing else "0 9 * * 1"

    jobs = [
        {
            "name": "competitor-hourly-scrape",
            "description": "Scrape hourly sources, detect changes, alert on significant findings",
            "cron": hourly_cron,
            "message": (
                "Run the competitor-monitoring skill: "
                "1) List all sources with schedule_group=hourly. "
                "2) Scrape each one using scrape.py. "
                "3) Run detect_changes.py --all to find changes. "
                "4) For any changes with severity high or critical, analyze them and send alerts. "
                "5) Use format_slack.py to format alerts."
            ),
            "command": (
                f'openclaw cron add --name "competitor-hourly-scrape" '
                f'--cron "{hourly_cron}" --tz "{timezone}" '
                f'--session isolated '
                f'--message "Run the competitor-monitoring skill: '
                f'1) List all sources with schedule_group=hourly. '
                f'2) Scrape each one using scrape.py. '
                f'3) Run detect_changes.py --all to find changes. '
                f'4) For any high/critical changes, analyze them and send alerts. '
                f'5) Use format_slack.py to format alerts."'
                f'{delivery_args}'
            ),
        },
        {
            "name": "competitor-daily-monitor",
            "description": "Full daily scrape, detect, analyze, alert, and update knowledge base",
            "cron": daily_cron,
            "message": (
                "Run the competitor-monitoring skill — FULL DAILY RUN: "
                "1) Run manage_sources.py list to get all active sources. "
                "2) Scrape ALL sources using scrape.py. "
                "3) Run detect_changes.py --all. "
                "4) For every detected change, analyze it following the analysis template. "
                "5) Save each analysis using save_analysis.py. "
                "6) Send alerts for medium+ severity changes via format_slack.py --send. "
                "7) Run detect_partnerships.py --all --save. "
                "8) Knowledge base is auto-updated by the watcher. "
                "9) LLM-enhanced insights are generated automatically if ANTHROPIC_API_KEY is set."
            ),
            "command": (
                f'openclaw cron add --name "competitor-daily-monitor" '
                f'--cron "{daily_cron}" --tz "{timezone}" '
                f'--session isolated '
                f'--message "Run the competitor-monitoring skill — FULL DAILY RUN: '
                f'1) List and scrape ALL active sources. '
                f'2) Run detect_changes.py --all. '
                f'3) Analyze every detected change following the analysis template. '
                f'4) Save analyses with save_analysis.py. '
                f'5) Alert on medium+ severity via format_slack.py --send. '
                f'6) Run detect_partnerships.py --all --save. '
                f'7) Update competitor knowledge base."'
                f'{delivery_args}'
            ),
        },
        {
            "name": "competitor-weekly-discovery",
            "description": "Discover new sources, scan partnerships, generate weekly report",
            "cron": weekly_cron,
            "message": (
                "Run the competitor-monitoring skill — WEEKLY DISCOVERY: "
                "1) For each competitor, run discover_sources.py with --save to find new pages. "
                "2) Use web_search to find recent news about each competitor. "
                "3) Run detect_partnerships.py --all --save. "
                "4) Run analyze_sentiment.py --all to gauge market sentiment. "
                "5) Run strategic_reasoning.py --days 7 for cross-competitor market trends. "
                "6) Generate the weekly report with generate_report.py --weekly --format markdown (includes executive summary). "
                "7) Format and send the report via format_slack.py --report --send. "
                "8) Knowledge base is auto-updated by the pipeline."
            ),
            "command": (
                f'openclaw cron add --name "competitor-weekly-discovery" '
                f'--cron "{weekly_cron}" --tz "{timezone}" '
                f'--session isolated '
                f'--message "Run the competitor-monitoring skill — WEEKLY DISCOVERY: '
                f'1) Discover new sources for each competitor with discover_sources.py --save. '
                f'2) Search for competitor news via web_search. '
                f'3) Detect partnerships with detect_partnerships.py --all --save. '
                f'4) Analyze sentiment with analyze_sentiment.py --all. '
                f'5) Generate weekly report with generate_report.py --weekly. '
                f'6) Send report via format_slack.py --report --send and send_email.py. '
                f'7) Update competitor knowledge base."'
                f'{delivery_args}'
            ),
        },
    ]

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Set up OpenClaw cron jobs")
    parser.add_argument("--print", action="store_true", dest="print_only", help="Print commands only")
    parser.add_argument("--execute", action="store_true", help="Execute cron add commands")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--slack-channel", default="", help="Slack channel ID for delivery")
    parser.add_argument("--timezone", default="US/Pacific", help="IANA timezone")
    parser.add_argument("--testing", action="store_true",
                        help="Use shorter intervals for testing (10min/30min/1hr)")
    args = parser.parse_args()

    jobs = build_cron_jobs(
        slack_channel=args.slack_channel,
        timezone=args.timezone,
        testing=args.testing,
    )

    if args.json:
        print(json.dumps(jobs, indent=2))
        return

    for job in jobs:
        print(f"\n# {job['name']}: {job['description']}")
        print(f"# Schedule: {job['cron']} ({args.timezone})")
        print(job["command"])
        print()

    if args.execute:
        print("=" * 60)
        print("Executing cron add commands...")
        print("=" * 60)
        for job in jobs:
            print(f"\nAdding: {job['name']}...")
            try:
                result = subprocess.run(
                    job["command"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    print(f"  ✓ {job['name']} added successfully")
                    if result.stdout.strip():
                        print(f"  {result.stdout.strip()}")
                else:
                    print(f"  ✗ Failed: {result.stderr.strip()}")
            except FileNotFoundError:
                print("  ✗ Error: 'openclaw' command not found. Is OpenClaw installed?")
                sys.exit(1)
            except subprocess.TimeoutExpired:
                print(f"  ✗ Timeout adding {job['name']}")

        print("\nDone. Verify with: openclaw cron list")
    elif not args.json:
        print("# Run with --execute to add these jobs, or copy commands above.")


if __name__ == "__main__":
    main()
