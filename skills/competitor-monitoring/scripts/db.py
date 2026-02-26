"""MongoDB connection manager and CRUD helpers for the Competitor Monitoring system.

Usage:
    from db import get_db, competitors, sources, snapshots, changes, analyses, partnerships, alerts

All helpers accept and return plain dicts (serialized Pydantic models).
The calling script is responsible for model validation.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

# Load .env from project root (two levels up from scripts/)
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_client: Optional[MongoClient] = None
_db: Optional[Database] = None

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/competitor_monitoring")
DB_NAME = os.getenv("MONGODB_DB_NAME", "competitor_monitoring")


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Verify connectivity
        _client.admin.command("ping")
    return _client


def get_db() -> Database:
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db


def close():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------

def competitors() -> Collection:
    return get_db()["competitors"]


def sources() -> Collection:
    return get_db()["sources"]


def snapshots() -> Collection:
    return get_db()["snapshots"]


def changes() -> Collection:
    return get_db()["changes"]


def analyses() -> Collection:
    return get_db()["analyses"]


def partnerships() -> Collection:
    return get_db()["partnerships"]


def alerts() -> Collection:
    return get_db()["alerts"]


# ---------------------------------------------------------------------------
# Index setup (idempotent — safe to call on every startup)
# ---------------------------------------------------------------------------

def ensure_indexes():
    """Create all indexes. Call once at startup or via setup script."""
    # Competitors
    competitors().create_index("slug", unique=True)
    competitors().create_index("domain", unique=True)
    competitors().create_index("is_active")

    # Sources
    sources().create_index([("competitor_id", ASCENDING), ("page_type", ASCENDING)])
    sources().create_index("url", unique=True)
    sources().create_index([("schedule_group", ASCENDING), ("is_active", ASCENDING)])
    sources().create_index("last_scraped_at")

    # Snapshots
    snapshots().create_index([("source_id", ASCENDING), ("scraped_at", DESCENDING)])
    snapshots().create_index([("competitor_id", ASCENDING), ("scraped_at", DESCENDING)])
    snapshots().create_index("content_hash")
    snapshots().create_index([("has_change", ASCENDING), ("scraped_at", DESCENDING)])

    # Changes
    changes().create_index([("competitor_id", ASCENDING), ("detected_at", DESCENDING)])
    changes().create_index([("change_type", ASCENDING), ("severity", ASCENDING)])
    changes().create_index("is_analyzed")
    changes().create_index("is_alerted")

    # Analyses
    analyses().create_index([("competitor_id", ASCENDING), ("generated_at", DESCENDING)])
    analyses().create_index("analysis_type")
    analyses().create_index("change_ids")

    # Partnerships
    partnerships().create_index(
        [("competitor_id", ASCENDING), ("partner_name", ASCENDING)], unique=True
    )
    partnerships().create_index([("discovered_at", DESCENDING)])
    partnerships().create_index("partnership_type")

    # Alerts
    alerts().create_index([("competitor_id", ASCENDING), ("sent_at", DESCENDING)])
    alerts().create_index("status")
    alerts().create_index("analysis_id")


# ---------------------------------------------------------------------------
# Competitor CRUD
# ---------------------------------------------------------------------------

def save_competitor(doc: dict) -> str:
    result = competitors().insert_one(doc)
    return str(result.inserted_id)


def get_competitor_by_slug(slug: str) -> Optional[dict]:
    return competitors().find_one({"slug": slug})


def get_competitor_by_id(competitor_id: str) -> Optional[dict]:
    return competitors().find_one({"_id": competitor_id})


def get_all_active_competitors() -> list[dict]:
    return list(competitors().find({"is_active": True}))


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------

def save_source(doc: dict) -> str:
    result = sources().insert_one(doc)
    return str(result.inserted_id)


def get_source_by_url(url: str) -> Optional[dict]:
    return sources().find_one({"url": url})


def get_source_by_id(source_id: str) -> Optional[dict]:
    return sources().find_one({"_id": source_id})


def get_active_sources(
    competitor_id: Optional[str] = None,
    schedule_group: Optional[str] = None,
) -> list[dict]:
    query: dict[str, Any] = {"is_active": True}
    if competitor_id:
        query["competitor_id"] = competitor_id
    if schedule_group:
        query["schedule_group"] = schedule_group
    return list(sources().find(query))


def update_source_scrape_time(source_id: str):
    sources().update_one(
        {"_id": source_id},
        {"$set": {"last_scraped_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}}
    )


def increment_source_failures(source_id: str):
    sources().update_one(
        {"_id": source_id},
        {
            "$inc": {"consecutive_failures": 1},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        }
    )


def reset_source_failures(source_id: str):
    sources().update_one(
        {"_id": source_id},
        {"$set": {"consecutive_failures": 0, "updated_at": datetime.now(timezone.utc)}}
    )


def disable_source(source_id: str):
    sources().update_one(
        {"_id": source_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
    )


# ---------------------------------------------------------------------------
# Snapshot CRUD
# ---------------------------------------------------------------------------

def save_snapshot(doc: dict) -> str:
    result = snapshots().insert_one(doc)
    return str(result.inserted_id)


def get_snapshot_by_id(snapshot_id: str) -> Optional[dict]:
    return snapshots().find_one({"_id": snapshot_id})


def get_latest_snapshot(source_id: str) -> Optional[dict]:
    return snapshots().find_one(
        {"source_id": source_id},
        sort=[("scraped_at", DESCENDING)],
    )


def get_previous_snapshot(source_id: str, before: datetime) -> Optional[dict]:
    return snapshots().find_one(
        {"source_id": source_id, "scraped_at": {"$lt": before}},
        sort=[("scraped_at", DESCENDING)],
    )


def get_snapshot_history(source_id: str, limit: int = 10) -> list[dict]:
    return list(
        snapshots()
        .find({"source_id": source_id})
        .sort("scraped_at", DESCENDING)
        .limit(limit)
    )


# ---------------------------------------------------------------------------
# Change CRUD
# ---------------------------------------------------------------------------

def save_change(doc: dict) -> str:
    result = changes().insert_one(doc)
    return str(result.inserted_id)


def get_unanalyzed_changes() -> list[dict]:
    return list(changes().find({"is_analyzed": False}))


def get_unalerted_changes(min_severity: Optional[str] = None) -> list[dict]:
    query: dict[str, Any] = {"is_alerted": False}
    if min_severity:
        severity_order = ["low", "medium", "high", "critical"]
        idx = severity_order.index(min_severity)
        query["severity"] = {"$in": severity_order[idx:]}
    return list(changes().find(query))


def mark_change_analyzed(change_id: str, analysis_id: str):
    changes().update_one(
        {"_id": change_id},
        {"$set": {"is_analyzed": True, "analysis_id": analysis_id}}
    )


def mark_change_alerted(change_id: str):
    changes().update_one({"_id": change_id}, {"$set": {"is_alerted": True}})


def get_changes_by_competitor(
    competitor_id: str, limit: int = 50
) -> list[dict]:
    return list(
        changes()
        .find({"competitor_id": competitor_id})
        .sort("detected_at", DESCENDING)
        .limit(limit)
    )


# ---------------------------------------------------------------------------
# Analysis CRUD
# ---------------------------------------------------------------------------

def save_analysis(doc: dict) -> str:
    result = analyses().insert_one(doc)
    return str(result.inserted_id)


def get_analysis_by_id(analysis_id: str) -> Optional[dict]:
    return analyses().find_one({"_id": analysis_id})


def get_recent_analyses(
    competitor_id: Optional[str] = None, limit: int = 20
) -> list[dict]:
    query = {"competitor_id": competitor_id} if competitor_id else {}
    return list(
        analyses().find(query).sort("generated_at", DESCENDING).limit(limit)
    )


# ---------------------------------------------------------------------------
# Partnership CRUD
# ---------------------------------------------------------------------------

def save_partnership(doc: dict) -> str:
    result = partnerships().insert_one(doc)
    return str(result.inserted_id)


def get_partnerships_by_competitor(competitor_id: str) -> list[dict]:
    return list(partnerships().find({"competitor_id": competitor_id}))


def partnership_exists(competitor_id: str, partner_name: str) -> bool:
    return partnerships().find_one(
        {"competitor_id": competitor_id, "partner_name": partner_name}
    ) is not None


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------

def save_alert(doc: dict) -> str:
    result = alerts().insert_one(doc)
    return str(result.inserted_id)


def get_recent_alerts(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc).replace(
        hour=datetime.now(timezone.utc).hour - min(hours, datetime.now(timezone.utc).hour)
    )
    return list(alerts().find({"sent_at": {"$gte": cutoff}}))


def count_alerts_last_hour() -> int:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    return alerts().count_documents({"sent_at": {"$gte": cutoff}})


# ---------------------------------------------------------------------------
# Activity tracking (for adaptive crawling)
# ---------------------------------------------------------------------------

def get_source_change_frequency(source_id: str, days: int = 30) -> float:
    """Count changes for a source in the last N days. Returns changes per day."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = changes().count_documents({
        "source_id": source_id,
        "detected_at": {"$gte": cutoff},
    })
    return count / max(days, 1)


def get_competitor_activity_score(competitor_id: str, days: int = 14) -> float:
    """Aggregate change frequency across all sources for a competitor.

    Returns a score: total changes / days. Higher = more active.
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = changes().count_documents({
        "competitor_id": competitor_id,
        "detected_at": {"$gte": cutoff},
    })
    return count / max(days, 1)


def update_source_schedule(source_id: str, new_schedule: str) -> None:
    """Update the schedule_group for a source (hourly/daily/weekly)."""
    sources().update_one(
        {"_id": source_id},
        {"$set": {"schedule_group": new_schedule, "updated_at": datetime.now(timezone.utc)}},
    )


# ---------------------------------------------------------------------------
# Seed / Setup CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """Run directly to set up indexes: python3 db.py setup"""
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        print(f"Connecting to MongoDB: {MONGODB_URI}")
        ensure_indexes()
        print("All indexes created successfully.")
    else:
        print("Usage: python3 db.py setup")
