"""Analysis read endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import db
from api.schemas import AnalysisOut

router = APIRouter(prefix="/analyses", tags=["analyses"])


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    # Flatten nested Pydantic-serialised content if needed
    if hasattr(doc.get("content"), "model_dump"):
        doc["content"] = doc["content"].model_dump()
    return doc


@router.get("", response_model=list[AnalysisOut])
def list_analyses(
    competitor_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    docs = db.get_recent_analyses(competitor_id=competitor_id, limit=limit)
    return [_enrich(d) for d in docs]


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: str):
    doc = db.get_analysis_by_id(analysis_id)
    if not doc:
        raise HTTPException(404, "Analysis not found")
    return _enrich(doc)
