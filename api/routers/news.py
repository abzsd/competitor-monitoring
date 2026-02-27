"""News items endpoints — Tavily-sourced competitor news."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pymongo import DESCENDING

import db
from api.schemas import NewsItemOut

router = APIRouter(prefix="/news", tags=["news"])


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    return doc


@router.get("", response_model=list[NewsItemOut])
def list_news(
    competitor_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_relevance: float = Query(0.0, ge=0.0, le=1.0),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {"discovered_at": {"$gte": cutoff}}
    if competitor_id:
        query["competitor_id"] = competitor_id
    if category:
        query["search_category"] = category
    if min_relevance > 0:
        query["relevance_score"] = {"$gte": min_relevance}

    docs = list(
        db.news_items()
        .find(query)
        .sort("discovered_at", DESCENDING)
        .limit(limit)
    )
    return [_enrich(d) for d in docs]


@router.get("/count")
def news_count(days: int = Query(7, ge=1, le=365)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = db.news_items().count_documents({"discovered_at": {"$gte": cutoff}})
    high_relevance = db.news_items().count_documents({
        "discovered_at": {"$gte": cutoff},
        "relevance_score": {"$gte": 0.7},
    })
    return {"total": total, "high_relevance": high_relevance, "days": days}
