"""Trigger a scan cycle from the dashboard with live activity logging."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pymongo import DESCENDING

import db

router = APIRouter(tags=["scan"])

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "competitor-monitoring", "scripts")
PYTHON = sys.executable


def _log_activity(event: str, detail: str = "", status: str = "info", scan_id: str = ""):
    """Write a timestamped event to the activity_log collection."""
    db.activity_log().insert_one({
        "_id": str(ObjectId()),
        "scan_id": scan_id,
        "event": event,
        "detail": detail,
        "status": status,  # info, success, warning, error
        "timestamp": datetime.now(timezone.utc),
    })


@router.post("/scan")
def trigger_scan():
    """Run one watcher cycle: scrape all sources -> detect changes. Logs each step."""
    scan_id = str(ObjectId())
    sources_list = db.get_active_sources()

    _log_activity("scan_started", f"Starting scan of {len(sources_list)} source(s)", "info", scan_id)

    # Step 1: Scrape all active sources
    scraped = 0
    errors = []

    for src in sources_list:
        comp = db.get_competitor_by_id(src.get("competitor_id", ""))
        comp_name = comp["name"] if comp else "Unknown"
        _log_activity("scraping", f"Scraping {comp_name}: {src['url']}", "info", scan_id)
        try:
            result = subprocess.run(
                [PYTHON, os.path.join(SCRIPTS_DIR, "scrape.py"),
                 src["url"], "--source-id", src["_id"], "--page-type", src.get("page_type", "other")],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                scraped += 1
                _log_activity("scrape_ok", f"{comp_name}: {src['url']}", "success", scan_id)
            else:
                err_msg = result.stderr[:100] if result.stderr else "unknown error"
                errors.append(f"{src['url']}: {err_msg}")
                _log_activity("scrape_failed", f"{comp_name}: {err_msg}", "error", scan_id)
        except subprocess.TimeoutExpired:
            errors.append(f"{src['url']}: timeout")
            _log_activity("scrape_failed", f"{comp_name}: timeout", "error", scan_id)
        except Exception as e:
            errors.append(f"{src['url']}: {str(e)[:100]}")
            _log_activity("scrape_failed", f"{comp_name}: {str(e)[:100]}", "error", scan_id)

    _log_activity("detecting", f"Running change detection ({scraped} sources scraped)", "info", scan_id)

    # Step 2: Detect changes
    try:
        result = subprocess.run(
            [PYTHON, os.path.join(SCRIPTS_DIR, "detect_changes.py"), "--all"],
            capture_output=True, text=True, timeout=30,
        )
        changes_found = []
        if result.returncode == 0 and result.stdout.strip():
            try:
                changes_found = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
    except Exception as e:
        _log_activity("detection_failed", str(e), "error", scan_id)
        raise HTTPException(500, f"Detection failed: {e}")

    # Log each change found
    for c in changes_found:
        sev = c.get("severity", "low")
        ctype = c.get("change_type", "unknown").replace("_", " ").title()
        summary = c.get("summary", "")[:120]
        _log_activity(
            "change_detected",
            f"[{sev.upper()}] {ctype}: {summary}",
            "warning" if sev in ("medium", "low") else "error",
            scan_id,
        )

    _log_activity(
        "scan_completed",
        f"Done — {scraped} scraped, {len(changes_found)} change(s) found, {len(errors)} error(s)",
        "success",
        scan_id,
    )

    return {
        "status": "completed",
        "scan_id": scan_id,
        "sources_scraped": scraped,
        "changes_found": len(changes_found),
        "errors": errors[:5],
    }


@router.get("/activity")
def get_activity(limit: int = 30):
    """Get recent activity log entries for the dashboard."""
    docs = list(
        db.activity_log()
        .find()
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )
    for d in docs:
        d["_id"] = str(d["_id"])
        if "timestamp" in d:
            d["timestamp"] = d["timestamp"].isoformat()
    return docs
