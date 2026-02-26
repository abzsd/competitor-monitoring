"""Competitor CRUD endpoints."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException

import db
from api.schemas import CompetitorCreate, CompetitorOut, CompetitorUpdate

router = APIRouter(prefix="/competitors", tags=["competitors"])


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _enrich(doc: dict) -> dict:
    cid = doc["_id"]
    doc["source_count"] = len(db.get_active_sources(competitor_id=cid))
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    doc["recent_change_count"] = db.changes().count_documents(
        {"competitor_id": cid, "detected_at": {"$gte": cutoff}}
    )
    return doc


@router.get("", response_model=list[CompetitorOut])
def list_competitors():
    docs = db.get_all_active_competitors()
    return [_enrich(d) for d in docs]


@router.get("/{slug}", response_model=CompetitorOut)
def get_competitor(slug: str):
    doc = db.get_competitor_by_slug(slug)
    if not doc:
        raise HTTPException(404, f"Competitor not found: {slug}")
    return _enrich(doc)


@router.post("", response_model=CompetitorOut, status_code=201)
def create_competitor(body: CompetitorCreate):
    slug = body.slug or _slugify(body.name)
    if db.get_competitor_by_slug(slug):
        raise HTTPException(409, f"Competitor '{slug}' already exists")
    now = datetime.now(timezone.utc)
    doc = {
        "_id": str(ObjectId()),
        "name": body.name,
        "slug": slug,
        "domain": body.domain,
        "industry": body.industry,
        "description": body.description,
        "tags": body.tags,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.save_competitor(doc)
    return _enrich(doc)


@router.patch("/{slug}", response_model=CompetitorOut)
def update_competitor(slug: str, body: CompetitorUpdate):
    doc = db.get_competitor_by_slug(slug)
    if not doc:
        raise HTTPException(404, f"Competitor not found: {slug}")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)
    db.competitors().update_one({"_id": doc["_id"]}, {"$set": updates})
    doc.update(updates)
    return _enrich(doc)


@router.delete("/{slug}")
def deactivate_competitor(slug: str):
    doc = db.get_competitor_by_slug(slug)
    if not doc:
        raise HTTPException(404, f"Competitor not found: {slug}")
    db.competitors().update_one(
        {"_id": doc["_id"]},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"status": "deactivated", "slug": slug}
