"""Change read endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pymongo import DESCENDING

import db
from api.schemas import ChangeDetailOut, ChangeOut, PaginatedResponse

router = APIRouter(prefix="/changes", tags=["changes"])


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    src = db.get_source_by_id(doc.get("source_id", ""))
    doc["source_url"] = src["url"] if src else ""
    return doc


@router.get("", response_model=PaginatedResponse[ChangeOut])
def list_changes(
    competitor_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    change_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query: dict = {}
    if competitor_id:
        query["competitor_id"] = competitor_id
    if severity:
        query["severity"] = severity
    if change_type:
        query["change_type"] = change_type

    total = db.changes().count_documents(query)
    docs = list(
        db.changes()
        .find(query, {"text_diff": 0, "structured_diff": 0})
        .sort("detected_at", DESCENDING)
        .skip(offset)
        .limit(limit)
    )
    return PaginatedResponse(
        items=[_enrich(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{change_id}", response_model=ChangeDetailOut)
def get_change(change_id: str):
    doc = db.changes().find_one({"_id": change_id})
    if not doc:
        raise HTTPException(404, "Change not found")
    return _enrich(doc)
