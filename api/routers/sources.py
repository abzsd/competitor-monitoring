"""Source CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

import db
from api.schemas import SourceCreate, SourceOut, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    return doc


@router.get("", response_model=list[SourceOut])
def list_sources(
    competitor_id: Optional[str] = Query(None),
    schedule_group: Optional[str] = Query(None),
):
    docs = db.get_active_sources(competitor_id=competitor_id, schedule_group=schedule_group)
    return [_enrich(d) for d in docs]


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: str):
    doc = db.get_source_by_id(source_id)
    if not doc:
        raise HTTPException(404, "Source not found")
    return _enrich(doc)


@router.post("", response_model=SourceOut, status_code=201)
def create_source(body: SourceCreate):
    comp = db.get_competitor_by_id(body.competitor_id)
    if not comp:
        raise HTTPException(400, f"Competitor ID not found: {body.competitor_id}")
    if db.get_source_by_url(body.url):
        raise HTTPException(409, f"Source already exists: {body.url}")
    now = datetime.now(timezone.utc)
    doc = {
        "_id": str(ObjectId()),
        "competitor_id": body.competitor_id,
        "url": body.url,
        "page_type": body.page_type,
        "scrape_method": body.scrape_method,
        "scrape_config": {},
        "schedule_group": body.schedule_group,
        "discovery_method": "manual",
        "is_active": True,
        "consecutive_failures": 0,
        "created_at": now,
        "updated_at": now,
    }
    db.save_source(doc)
    return _enrich(doc)


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: str, body: SourceUpdate):
    doc = db.get_source_by_id(source_id)
    if not doc:
        raise HTTPException(404, "Source not found")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)
    db.sources().update_one({"_id": source_id}, {"$set": updates})
    doc.update(updates)
    return _enrich(doc)


@router.delete("/{source_id}")
def disable_source(source_id: str):
    doc = db.get_source_by_id(source_id)
    if not doc:
        raise HTTPException(404, "Source not found")
    db.disable_source(source_id)
    return {"status": "disabled", "source_id": source_id}
