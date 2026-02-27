"""Change read endpoints."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pymongo import DESCENDING

import db
from api.schemas import ChangeDetailOut, ChangeOut, PaginatedResponse

router = APIRouter(prefix="/changes", tags=["changes"])


def _extract_prices(text: str) -> list[str]:
    """Pull dollar amounts from a string."""
    return re.findall(r"\$[\d,]+(?:\.\d{2})?(?:/\w+)?", text)


def _humanize_summary(doc: dict) -> str:
    """Generate a concise, human-readable summary from structured_diff."""
    summary = doc.get("summary", "")
    # If summary already looks human-readable, keep it
    if "+/" not in summary and "lines changed" not in summary:
        return summary

    sdiff = doc.get("structured_diff") or {}
    change_type = doc.get("change_type", "")
    changed = sdiff.get("changed") or []
    added = sdiff.get("added") or []
    removed = sdiff.get("removed") or []

    # ── Pricing changes: extract price numbers ──
    if change_type == "pricing_change":
        price_shifts = []
        for item in changed:
            old_v = str(item.get("old_value", ""))
            new_v = str(item.get("new_value", ""))
            old_prices = _extract_prices(old_v)
            new_prices = _extract_prices(new_v)
            if old_prices and new_prices and old_prices[0] != new_prices[0]:
                price_shifts.append(f"{old_prices[0]} → {new_prices[0]}")
        new_features = [str(a.get("value", ""))[:60] for a in added if "feature" in str(a.get("path", "")).lower()]
        parts = []
        if price_shifts:
            parts.append(f"Prices changed: {', '.join(price_shifts[:3])}")
        if new_features:
            parts.append(f"{len(new_features)} new feature(s) added")
        if removed:
            parts.append(f"{len(removed)} item(s) removed")
        if parts:
            return f"Pricing update — {'. '.join(parts)}"
        return f"Pricing page updated ({len(changed)} changes, {len(added)} additions)"

    # ── Product updates: look for new headings/features ──
    if change_type == "product_update":
        new_headings = []
        for a in added:
            val = str(a.get("value", ""))
            path = str(a.get("path", ""))
            if "heading" in path.lower():
                # Extract text from dict-like string
                m = re.search(r"'text':\s*'([^']+)'", val)
                if m:
                    new_headings.append(m.group(1))
        changed_headings = []
        for item in changed:
            path = str(item.get("path", ""))
            if "heading" in path.lower() or "text" in path.lower():
                new_v = str(item.get("new_value", ""))
                if len(new_v) < 80:
                    changed_headings.append(new_v)
        if new_headings:
            return f"Product update — New sections: {', '.join(new_headings[:3])}"
        if changed_headings:
            return f"Product update — {changed_headings[0]}"
        return f"Product page updated ({len(changed)} changes, {len(added)} additions)"

    # ── Partnership/blog: look for new headings and partner names ──
    if change_type in ("partnership_new", "content_update"):
        new_headings = []
        for a in added:
            val = str(a.get("value", ""))
            path = str(a.get("path", ""))
            if "heading" in path.lower():
                m = re.search(r"'text':\s*'([^']+)'", val)
                if m:
                    new_headings.append(m.group(1))
        changed_headings = []
        for item in changed:
            path = str(item.get("path", ""))
            if "heading" in path.lower() or "text" in path.lower():
                new_v = str(item.get("new_value", ""))
                if 10 < len(new_v) < 100:
                    changed_headings.append(new_v)
        label = "New partnership" if change_type == "partnership_new" else "Content update"
        if new_headings:
            return f"{label} — {'; '.join(new_headings[:2])}"
        if changed_headings:
            return f"{label} — {changed_headings[0]}"
        return f"{label} ({len(changed)} changes, {len(added)} additions)"

    # ── Page added/removed ──
    if change_type == "page_added":
        return "New page discovered and added to monitoring"
    if change_type == "page_removed":
        return "Page was removed or is no longer accessible"

    # ── Generic fallback: short counts ──
    parts = []
    if changed:
        parts.append(f"{len(changed)} field(s) changed")
    if added:
        parts.append(f"{len(added)} item(s) added")
    if removed:
        parts.append(f"{len(removed)} item(s) removed")
    if parts:
        return f"Update detected — {', '.join(parts)}"

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
