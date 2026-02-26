"""Aggregate dashboard stats endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pymongo import DESCENDING

import db
from api.routers.changes import _humanize_summary
from api.schemas import AlertOut, ChangeOut, CompetitorActivity, DashboardStats

router = APIRouter(tags=["dashboard"])


def _enrich_change(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    src = db.get_source_by_id(doc.get("source_id", ""))
    doc["source_url"] = src["url"] if src else ""
    doc["summary"] = _humanize_summary(doc)
    return doc


def _enrich_alert(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    return doc


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard():
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)
    cutoff_24h = now - timedelta(hours=24)

    competitors_list = db.get_all_active_competitors()
    all_sources = db.get_active_sources()
    failing = db.sources().count_documents({"is_active": True, "consecutive_failures": {"$gt": 0}})

    changes_7d = db.changes().count_documents({"detected_at": {"$gte": cutoff_7d}})
    changes_30d = db.changes().count_documents({"detected_at": {"$gte": cutoff_30d}})
    alerts_24h = db.alerts().count_documents({"sent_at": {"$gte": cutoff_24h}})

    # Changes by severity
    sev_agg = db.changes().aggregate([
        {"$match": {"detected_at": {"$gte": cutoff_30d}}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
    ])
    changes_by_severity = {r["_id"]: r["count"] for r in sev_agg if r["_id"]}

    # Changes by type
    type_agg = db.changes().aggregate([
        {"$match": {"detected_at": {"$gte": cutoff_30d}}},
        {"$group": {"_id": "$change_type", "count": {"$sum": 1}}},
    ])
    changes_by_type = {r["_id"]: r["count"] for r in type_agg if r["_id"]}

    # Recent changes (last 10) — include structured_diff for humanized summaries
    recent_changes_raw = list(
        db.changes()
        .find({}, {"text_diff": 0})
        .sort("detected_at", DESCENDING)
        .limit(10)
    )
    recent_changes = [_enrich_change(c) for c in recent_changes_raw]

    # Recent alerts (last 5)
    recent_alerts_raw = list(
        db.alerts().find().sort("sent_at", DESCENDING).limit(5)
    )
    recent_alerts = [_enrich_alert(a) for a in recent_alerts_raw]

    # Competitor activity
    activity = []
    for comp in competitors_list:
        cid = comp["_id"]
        src_count = sum(1 for s in all_sources if s.get("competitor_id") == cid)
        chg_count = db.changes().count_documents(
            {"competitor_id": cid, "detected_at": {"$gte": cutoff_7d}}
        )
        score = db.get_competitor_activity_score(cid)
        activity.append(CompetitorActivity(
            name=comp["name"],
            slug=comp["slug"],
            activity_score=round(score, 3),
            source_count=src_count,
            change_count_7d=chg_count,
        ))

    return DashboardStats(
        total_competitors=len(competitors_list),
        total_sources=len(all_sources),
        active_sources=len(all_sources),
        failing_sources=failing,
        total_changes_7d=changes_7d,
        total_changes_30d=changes_30d,
        changes_by_severity=changes_by_severity,
        changes_by_type=changes_by_type,
        alerts_last_24h=alerts_24h,
        recent_changes=recent_changes,
        recent_alerts=recent_alerts,
        competitor_activity=activity,
    )
