"""Alert read endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pymongo import DESCENDING

import db
from api.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    return doc


@router.get("", response_model=list[AlertOut])
def list_alerts(
    hours: int = Query(24, ge=1, le=720),
    status: str | None = Query(None),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query: dict = {"sent_at": {"$gte": cutoff}}
    if status:
        query["status"] = status
    docs = list(db.alerts().find(query).sort("sent_at", DESCENDING).limit(100))
    return [_enrich(d) for d in docs]
