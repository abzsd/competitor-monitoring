"""Partnership read endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pymongo import DESCENDING

import db
from api.schemas import PartnershipOut

router = APIRouter(prefix="/partnerships", tags=["partnerships"])


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    return doc


@router.get("", response_model=list[PartnershipOut])
def list_partnerships(
    competitor_id: Optional[str] = Query(None),
):
    if competitor_id:
        docs = db.get_partnerships_by_competitor(competitor_id)
    else:
        docs = list(db.partnerships().find().sort("discovered_at", DESCENDING).limit(100))
    return [_enrich(d) for d in docs]
