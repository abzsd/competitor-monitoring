"""Change read endpoints."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pymongo import DESCENDING

import db
from api.schemas import ChangeDetailOut, ChangeOut, PaginatedResponse

router = APIRouter(prefix="/changes", tags=["changes"])


def _humanize_summary(doc: dict) -> str:
    """Generate a human-readable summary from structured_diff if the existing summary is technical."""
    summary = doc.get("summary", "")
    # If summary already looks human-readable (doesn't have the old "+N/-N lines changed" pattern), keep it
    if "+/" not in summary and "lines changed" not in summary:
        return summary

    sdiff = doc.get("structured_diff") or {}
    change_type = doc.get("change_type", "")
    diff_text = doc.get("text_diff", "")
    added_lines = [l[1:].strip() for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++") and l[1:].strip()] if diff_text else []

    highlights = []
    for item in (sdiff.get("changed") or [])[:4]:
        old_v = str(item.get("old_value", ""))
        new_v = str(item.get("new_value", ""))
        path = str(item.get("path", ""))
        parts = [p.strip("'\"") for p in re.findall(r"\['([^']+)'\]", path)]
        field = " > ".join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else "")
        if old_v and new_v and field:
            highlights.append(f"{field}: {old_v} → {new_v}")

    if change_type == "pricing_change" and highlights:
        return f"Pricing updated — {'; '.join(highlights[:3])}"
    if change_type == "product_update":
        key = [l for l in added_lines if any(kw in l.lower() for kw in ["feature", "introducing", "new", "launch", "now"])]
        if key:
            return f"Product update — {key[0][:120]}"
        if highlights:
            return f"Product update — {'; '.join(highlights[:2])}"
    if change_type == "partnership_new":
        partners = [l for l in added_lines if any(kw in l.lower() for kw in ["partner", "integration", "collaborat"])]
        if partners:
            return f"New partnership — {partners[0][:120]}"
    if highlights:
        return f"Update — {'; '.join(highlights[:3])}"
    interesting = [l for l in added_lines if len(l) > 20 and not l.startswith(("<", "{"))]
    if interesting:
        return f"Content updated — {interesting[0][:120]}"

    return summary


def _enrich(doc: dict) -> dict:
    comp = db.get_competitor_by_id(doc.get("competitor_id", ""))
    doc["competitor_name"] = comp["name"] if comp else "Unknown"
    src = db.get_source_by_id(doc.get("source_id", ""))
    doc["source_url"] = src["url"] if src else ""
    doc["summary"] = _humanize_summary(doc)
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
    # Fetch structured_diff for summary enrichment but exclude text_diff (large)
    docs = list(
        db.changes()
        .find(query, {"text_diff": 0})
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
