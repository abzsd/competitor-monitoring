#!/usr/bin/env python3
"""Continuous polling watcher — scrape, detect, analyze, alert in a loop.

Usage:
    python3 watcher.py                        # Default: 10-minute intervals
    python3 watcher.py --interval 60          # Every 60 seconds
    python3 watcher.py --once                 # One cycle, then exit
    python3 watcher.py --competitor testrival  # Watch a single competitor
    python3 watcher.py --dry-run              # Detect + insights but don't send Slack

Each cycle:
    1. Scrape all active sources (or filtered by --competitor)
    2. Run change detection
    3. Generate deep insights for each change
    4. Format rich Slack alerts and send via webhook
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
from detect_changes import detect_for_source, format_change_for_insights
from discover_sources import discover_sources
from generate_insights import generate_insights, set_llm_enabled, update_knowledge_base
from format_slack import format_change_alert_rich, send_to_slack

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
from dotenv import load_dotenv
load_dotenv(_env_path)

PYTHON = sys.executable  # Same interpreter that runs this script
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Scrape helper — calls scrape.py as a subprocess
# ---------------------------------------------------------------------------

def scrape_source(source_doc: dict) -> bool:
    """Scrape a single source by invoking scrape.py. Returns True on success.

    If the subprocess fails 3+ times consecutively, attempts in-process
    recovery using scrape_with_recovery().
    """
    source_id = source_doc["_id"]
    url = source_doc.get("url", "")
    page_type = source_doc.get("page_type", "other")
    consecutive_failures = source_doc.get("consecutive_failures", 0)

    # If source has been failing repeatedly, try recovery mode directly
    if consecutive_failures >= 3:
        _log("WARN", f"  Source has {consecutive_failures} failures, trying recovery mode for {url}")
        try:
            from scrape import scrape_with_recovery, extract_text, extract_structured_data
            import xxhash
            from bson import ObjectId

            html, metadata = scrape_with_recovery(url, source_doc)
            extracted_text = extract_text(html)
            structured_data = extract_structured_data(html, page_type)
            content_hash = xxhash.xxh64(extracted_text.encode()).hexdigest()

            # Check for change
            prev = db.get_latest_snapshot(source_id)
            has_change = (not prev) or (prev.get("content_hash") != content_hash)

            now = datetime.now(timezone.utc)
            snapshot_doc = {
                "_id": str(ObjectId()),
                "source_id": source_id,
                "competitor_id": source_doc.get("competitor_id", ""),
                "url": url,
                "scraped_at": now,
                "content_hash": content_hash,
                "raw_html": html,
                "extracted_text": extracted_text,
                "structured_data": structured_data,
                "metadata": metadata,
                "has_change": has_change,
                "created_at": now,
            }
            db.save_snapshot(snapshot_doc)
            db.update_source_scrape_time(source_id)
            db.reset_source_failures(source_id)
            _log("INFO", f"  Recovery succeeded for {url} (method: {metadata.get('scrape_method', '?')})")
            return True
        except Exception as e:
            _log("ERROR", f"  Recovery also failed for {url}: {e}")
            db.increment_source_failures(source_id)
            return False

    # Normal mode: subprocess call to scrape.py
    cmd = [PYTHON, os.path.join(SCRIPTS_DIR, "scrape.py"), url,
           "--source-id", source_id, "--page-type", page_type]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            _log("ERROR", f"Scrape failed for {url}: {result.stderr.strip()}")
            return False
        return True
    except subprocess.TimeoutExpired:
        _log("ERROR", f"Scrape timed out for {url}")
        return False


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def discover_new_pages(competitor_slug: str | None = None) -> int:
    """Run discovery for competitors, auto-register new pages. Returns count of new sources."""
    from urllib.parse import urlparse
    import bson

    if competitor_slug:
        competitors = [db.get_competitor_by_slug(competitor_slug)]
        competitors = [c for c in competitors if c]
    else:
        competitors = list(db.competitors().find({"is_active": True}))

    total_new = 0
    for comp in competitors:
        domain = comp.get("domain", "")
        if not domain:
            # Extract domain from first source URL
            sources = db.get_active_sources(competitor_id=comp["_id"])
            if sources:
                domain = urlparse(sources[0].get("url", "")).netloc
        if not domain:
            continue

        try:
            discovered = discover_sources(domain, competitor_id=comp["_id"])
            for item in discovered:
                # Skip news URLs — they're not permanent monitorable sources
                if item.discovery_method.value == "news":
                    continue
                # Auto-register as a new source
                source_doc = {
                    "_id": str(bson.ObjectId()),
                    "competitor_id": comp["_id"],
                    "url": item.url,
                    "page_type": item.suggested_page_type.value,
                    "scrape_method": "static",
                    "schedule_group": "daily",
                    "is_active": True,
                    "consecutive_failures": 0,
                    "discovered_by": "watcher_auto",
                }
                db.sources().insert_one(source_doc)
                total_new += 1
                _log("INFO", f"  NEW SOURCE: {item.url} ({item.suggested_page_type.value})")
        except Exception as e:
            _log("WARN", f"  Discovery failed for {domain}: {e}")

    return total_new


def run_cycle(competitor_slug: str | None = None, dry_run: bool = False) -> dict:
    """Run one full pipeline cycle. Returns a summary dict."""
    cycle_start = datetime.now(timezone.utc)
    _log("INFO", f"=== Cycle started at {cycle_start.strftime('%H:%M:%S UTC')} ===")

    # 1. Get sources
    if competitor_slug:
        competitor = db.get_competitor_by_slug(competitor_slug)
        if not competitor:
            _log("ERROR", f"Competitor not found: {competitor_slug}")
            return {"error": f"Competitor not found: {competitor_slug}"}
        sources = db.get_active_sources(competitor_id=competitor["_id"])
    else:
        sources = db.get_active_sources()

    _log("INFO", f"Found {len(sources)} active source(s)")

    # 2. Scrape all sources
    scrape_ok = 0
    scrape_fail = 0
    for source in sources:
        if scrape_source(source):
            scrape_ok += 1
        else:
            scrape_fail += 1
    _log("INFO", f"Scraped: {scrape_ok} ok, {scrape_fail} failed")

    # 3. Detect changes
    changes = []
    for source in sources:
        change = detect_for_source(source)
        if change:
            changes.append((change, source))
    _log("INFO", f"Detected {len(changes)} change(s)")

    # 4. Generate insights + send alerts
    alerts_sent = 0
    alerts_failed = 0
    for change, source in changes:
        try:
            # Get full data for insights
            data = format_change_for_insights(change, source)
            insights = generate_insights(
                data["change"],
                data["old_snapshot"],
                data["new_snapshot"],
                data["source"],
            )

            # Update knowledge base with learnings
            try:
                competitor_name = source.get("competitor_name", "Unknown")
                if not competitor_name or competitor_name == "Unknown":
                    comp = db.get_competitor_by_id(source.get("competitor_id", ""))
                    competitor_name = comp.get("name", "Unknown") if comp else "Unknown"
                update_knowledge_base(competitor_name, insights, data["change"])
            except Exception as kb_err:
                _log("WARN", f"  KB update failed: {kb_err}")

            # Format rich Slack message
            payload = format_change_alert_rich(data["change"], insights)

            _log("INFO", f"  [{change['severity'].upper()}] {change['change_type']}: {source.get('url', '')}")

            if dry_run:
                print(json.dumps(payload, indent=2))
                _log("INFO", "  (dry-run — not sending to Slack)")
            else:
                result = send_to_slack(payload)
                if result.get("status") == "sent":
                    alerts_sent += 1
                    _log("INFO", "  -> Slack alert sent")
                else:
                    alerts_failed += 1
                    _log("WARN", f"  -> Slack failed: {result.get('error', '?')}")

                # Small delay between Slack messages to respect rate limits
                if len(changes) > 1:
                    time.sleep(1.5)

        except Exception as e:
            alerts_failed += 1
            _log("ERROR", f"  Pipeline error for {source.get('url', '')}: {e}")

    cycle_end = datetime.now(timezone.utc)
    duration = (cycle_end - cycle_start).total_seconds()

    summary = {
        "cycle_start": cycle_start.isoformat(),
        "duration_seconds": round(duration, 1),
        "sources_scraped": scrape_ok,
        "scrape_failures": scrape_fail,
        "changes_detected": len(changes),
        "alerts_sent": alerts_sent,
        "alerts_failed": alerts_failed,
    }

    _log("INFO", f"=== Cycle complete in {duration:.1f}s — "
         f"{len(changes)} changes, {alerts_sent} alerts sent ===\n")

    return summary


# ---------------------------------------------------------------------------
# Adaptive crawl frequency
# ---------------------------------------------------------------------------

ACTIVITY_HIGH_THRESHOLD = 2.0    # changes/day → promote to hourly
ACTIVITY_LOW_THRESHOLD = 0.1     # changes/day for 14 days → demote to daily


def adapt_crawl_frequency(competitor_slug: str | None = None) -> dict:
    """Adjust source scraping frequency based on competitor activity.

    High activity (>2 changes/day): promote daily → hourly
    Low activity (<0.1 changes/day over 14 days): demote hourly → daily

    Returns summary of changes made.
    """
    promotions = 0
    demotions = 0

    if competitor_slug:
        competitors = [db.get_competitor_by_slug(competitor_slug)]
        competitors = [c for c in competitors if c]
    else:
        competitors = list(db.competitors().find({"is_active": True}))

    for comp in competitors:
        comp_id = comp["_id"]
        comp_name = comp.get("name", comp.get("slug", ""))
        activity = db.get_competitor_activity_score(comp_id, days=14)

        sources = db.get_active_sources(competitor_id=comp_id)
        for source in sources:
            current_schedule = source.get("schedule_group", "daily")

            if activity > ACTIVITY_HIGH_THRESHOLD and current_schedule == "daily":
                db.update_source_schedule(source["_id"], "hourly")
                promotions += 1
                _log("INFO", f"  Adaptive: promoted {source.get('url', '')} to hourly "
                     f"({comp_name} activity={activity:.2f}/day)")

            elif activity < ACTIVITY_LOW_THRESHOLD and current_schedule == "hourly":
                db.update_source_schedule(source["_id"], "daily")
                demotions += 1
                _log("INFO", f"  Adaptive: demoted {source.get('url', '')} to daily "
                     f"({comp_name} activity={activity:.2f}/day)")

    return {"promotions": promotions, "demotions": demotions}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(level: str, message: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Continuous polling watcher for competitor monitoring"
    )
    parser.add_argument(
        "--interval", type=int, default=600,
        help="Seconds between cycles (default: 600 = 10 min)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one cycle and exit"
    )
    parser.add_argument(
        "--competitor", type=str, default=None,
        help="Watch a single competitor (slug)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Detect and analyze but don't send Slack alerts"
    )
    parser.add_argument(
        "--discover", action="store_true", default=True,
        help="Enable periodic new-page discovery (default: on)"
    )
    parser.add_argument(
        "--no-discover", action="store_true",
        help="Disable periodic new-page discovery"
    )
    parser.add_argument(
        "--discover-every", type=int, default=10,
        help="Run discovery every N cycles (default: 10)"
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Disable LLM enhancement (rule-based analysis only)"
    )
    args = parser.parse_args()
    do_discover = not args.no_discover

    if args.no_llm:
        set_llm_enabled(False)

    _log("INFO", f"Watcher starting — interval={args.interval}s, "
         f"competitor={args.competitor or 'all'}, dry_run={args.dry_run}, "
         f"discover={'every ' + str(args.discover_every) + ' cycles' if do_discover else 'off'}")

    try:
        if args.once:
            if do_discover:
                _log("INFO", "Running new-page discovery...")
                new_count = discover_new_pages(args.competitor)
                _log("INFO", f"Discovery complete: {new_count} new source(s) registered")
            summary = run_cycle(args.competitor, args.dry_run)
            print(json.dumps(summary, indent=2))
        else:
            cycle_num = 0
            while True:
                cycle_num += 1
                _log("INFO", f"--- Cycle #{cycle_num} ---")

                # Periodic discovery
                if do_discover and cycle_num % args.discover_every == 0:
                    _log("INFO", "Running new-page discovery...")
                    new_count = discover_new_pages(args.competitor)
                    _log("INFO", f"Discovery complete: {new_count} new source(s) registered")

                summary = run_cycle(args.competitor, args.dry_run)

                # Adapt crawl frequency based on activity
                try:
                    adapt_result = adapt_crawl_frequency(args.competitor)
                    if adapt_result["promotions"] or adapt_result["demotions"]:
                        _log("INFO", f"Adaptive crawling: {adapt_result['promotions']} promoted, "
                             f"{adapt_result['demotions']} demoted")
                except Exception as adapt_err:
                    _log("WARN", f"Adaptive crawl check failed: {adapt_err}")

                _log("INFO", f"Next cycle in {args.interval}s (Ctrl+C to stop)")
                time.sleep(args.interval)
    except KeyboardInterrupt:
        _log("INFO", "Watcher stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
