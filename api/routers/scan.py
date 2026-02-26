"""Trigger a scan cycle from the dashboard."""

from __future__ import annotations

import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["scan"])

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "competitor-monitoring", "scripts")
PYTHON = sys.executable


@router.post("/scan")
def trigger_scan():
    """Run one watcher cycle: scrape all sources → detect changes. Returns new changes found."""
    # Step 1: Scrape all active sources
    import db
    sources_list = db.get_active_sources()
    scraped = 0
    errors = []

    for src in sources_list:
        try:
            result = subprocess.run(
                [PYTHON, os.path.join(SCRIPTS_DIR, "scrape.py"),
                 src["url"], "--source-id", src["_id"], "--page-type", src.get("page_type", "other")],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                scraped += 1
            else:
                errors.append(f"{src['url']}: {result.stderr[:100]}")
        except subprocess.TimeoutExpired:
            errors.append(f"{src['url']}: timeout")
        except Exception as e:
            errors.append(f"{src['url']}: {str(e)[:100]}")

    # Step 2: Detect changes
    try:
        result = subprocess.run(
            [PYTHON, os.path.join(SCRIPTS_DIR, "detect_changes.py"), "--all"],
            capture_output=True, text=True, timeout=30,
        )
        import json
        changes_found = []
        if result.returncode == 0 and result.stdout.strip():
            try:
                changes_found = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
    except Exception as e:
        raise HTTPException(500, f"Detection failed: {e}")

    return {
        "status": "completed",
        "sources_scraped": scraped,
        "changes_found": len(changes_found),
        "errors": errors[:5],
    }
