#!/usr/bin/env python3
"""Detect changes between consecutive snapshots and store change records.

Usage:
    python3 detect_changes.py --all                    # Check all active sources
    python3 detect_changes.py --competitor <slug>      # Check sources for one competitor
    python3 detect_changes.py --source-id <id>         # Check a single source

Output:
    JSON array of detected changes with diffs.
    The OpenClaw agent reads this output to perform analysis.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from datetime import datetime, timezone

from deepdiff import DeepDiff

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
from models import ChangeType, Severity

# ---------------------------------------------------------------------------
# Severity classification rules
# ---------------------------------------------------------------------------

# Keywords for detecting change types from diff content
PRICE_KEYWORDS = {"price", "cost", "/mo", "/yr", "per month", "per year", "billing", "subscription"}

PARTNERSHIP_KEYWORDS = {
    "partnership", "partner", "integration", "collaborate", "collaboration",
    "powered by", "works with", "acquisition", "acquired", "merger",
    "strategic alliance", "joint venture", "reseller",
}

PRODUCT_KEYWORDS = {
    "feature", "introducing", "new:", "now available", "launch", "beta",
    "general availability", "capability", "module", "upgrade",
}

# Signal keywords for severity boosting (run on ALL change types)
FUNDING_SIGNAL = re.compile(
    r"\$\s?[\d,]+\.?\d*\s*(million|M|billion|B)\b",
    re.IGNORECASE,
)
LAUNCH_SIGNAL_KEYWORDS = ["launching", "introducing", "announcing", "now available",
                          "general availability", "public beta", "we're excited to announce"]
HIRING_SIGNAL_KEYWORDS = ["hiring", "we're growing", "open roles", "join our team",
                          "new office", "expanding"]
ACQUISITION_KEYWORDS = ["acquired", "acquisition", "merger", "acquires"]


def _detect_diff_signals(text_diff: str) -> set[str]:
    """Detect strategic signals from diff text. Returns a set of signal types."""
    added_text = "\n".join(l[1:] for l in text_diff.splitlines() if l.startswith("+")).lower()
    signals = set()
    if FUNDING_SIGNAL.search(added_text):
        signals.add("funding")
    if any(kw in added_text for kw in LAUNCH_SIGNAL_KEYWORDS):
        signals.add("product_launch")
    if any(kw in added_text for kw in HIRING_SIGNAL_KEYWORDS):
        signals.add("hiring")
    if any(kw in added_text for kw in ACQUISITION_KEYWORDS):
        signals.add("acquisition")
    if any(kw in added_text for kw in PARTNERSHIP_KEYWORDS):
        signals.add("partnership")
    return signals


def classify_change_type(source_doc: dict, text_diff: str) -> ChangeType:
    """Infer the change type from the source's page_type and diff content."""
    page_type = source_doc.get("page_type", "other")

    # Page type takes priority for strongly-typed pages
    if page_type == "pricing":
        return ChangeType.PRICING_CHANGE
    if page_type == "tech_stack":
        return ChangeType.TECH_STACK_CHANGE
    if page_type == "partnerships":
        return ChangeType.PARTNERSHIP_NEW
    if page_type == "product":
        return ChangeType.PRODUCT_UPDATE

    # For other page types, classify based on diff content
    diff_lower = text_diff.lower()
    added_text = "\n".join(l[1:] for l in diff_lower.splitlines() if l.startswith("+"))

    # Only classify as pricing if strong pricing signals (not just "$" in any text)
    price_hits = sum(1 for kw in PRICE_KEYWORDS if kw in added_text)
    if price_hits >= 2:
        return ChangeType.PRICING_CHANGE

    if any(kw in added_text for kw in PARTNERSHIP_KEYWORDS):
        return ChangeType.PARTNERSHIP_NEW

    if any(kw in added_text for kw in PRODUCT_KEYWORDS):
        return ChangeType.PRODUCT_UPDATE

    return ChangeType.CONTENT_UPDATE


def classify_severity(
    change_type: ChangeType,
    text_diff: str,
    before_text: str,
    after_text: str,
    structured_diff: dict,
) -> Severity:
    """Assign severity using signals + type rules. Agent may refine during analysis."""

    # Calculate how much content changed
    if before_text:
        change_ratio = abs(len(after_text) - len(before_text)) / max(len(before_text), 1)
    else:
        change_ratio = 1.0

    # Detect strategic signals from the diff (runs for ALL change types)
    signals = _detect_diff_signals(text_diff)

    # Funding or acquisition is always critical
    if "funding" in signals or "acquisition" in signals:
        return Severity.CRITICAL

    # Type-specific rules
    if change_type == ChangeType.PRICING_CHANGE:
        if structured_diff.get("changed"):
            return Severity.CRITICAL
        return Severity.HIGH

    if change_type == ChangeType.PARTNERSHIP_NEW:
        return Severity.HIGH

    if change_type == ChangeType.PRODUCT_UPDATE:
        if "product_launch" in signals:
            return Severity.HIGH
        if change_ratio > 0.3:
            return Severity.HIGH
        return Severity.MEDIUM

    if change_type == ChangeType.TECH_STACK_CHANGE:
        return Severity.MEDIUM

    # Content updates — signal-aware severity
    if "product_launch" in signals or "partnership" in signals:
        return Severity.HIGH
    if "hiring" in signals:
        return Severity.MEDIUM
    if change_ratio > 0.3:
        return Severity.MEDIUM
    if change_ratio > 0.1:
        return Severity.LOW
    return Severity.LOW


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def compute_text_diff(before: str, after: str, context_lines: int = 3) -> str:
    """Compute a unified diff between two text strings."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile="before",
        tofile="after",
        n=context_lines,
    )
    return "".join(diff)


def compute_structured_diff(before_data: dict, after_data: dict) -> dict:
    """Compute structured diff between two structured data dicts."""
    if not before_data and not after_data:
        return {"changed": [], "added": [], "removed": []}

    diff = DeepDiff(before_data, after_data, ignore_order=True, verbose_level=2)
    result = {"changed": [], "added": [], "removed": []}

    # Values changed
    for path, change in diff.get("values_changed", {}).items():
        result["changed"].append({
            "path": path,
            "old_value": str(change.get("old_value", "")),
            "new_value": str(change.get("new_value", "")),
        })

    # Items added
    for path, value in diff.get("dictionary_item_added", {}).items():
        result["added"].append({"path": path, "value": str(value)})
    for path, value in diff.get("iterable_item_added", {}).items():
        result["added"].append({"path": path, "value": str(value)})

    # Items removed
    for path, value in diff.get("dictionary_item_removed", {}).items():
        result["removed"].append({"path": path, "value": str(value)})
    for path, value in diff.get("iterable_item_removed", {}).items():
        result["removed"].append({"path": path, "value": str(value)})

    return result


def generate_summary(change_type: ChangeType, text_diff: str, source_doc: dict, structured_diff: dict | None = None) -> str:
    """Generate a human-readable summary a non-technical person can understand."""
    page_type = source_doc.get("page_type", "page")
    diff_lines = text_diff.splitlines()
    added_lines = [l[1:].strip() for l in diff_lines if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]
    removed_lines = [l[1:].strip() for l in diff_lines if l.startswith("-") and not l.startswith("---") and l[1:].strip()]

    # Extract specific value changes from structured_diff
    highlights = []
    if structured_diff and structured_diff.get("changed"):
        for item in structured_diff["changed"][:5]:
            old_v = str(item.get("old_value", ""))[:80]
            new_v = str(item.get("new_value", ""))[:80]
            if old_v and new_v:
                highlights.append(f"{old_v} → {new_v}")

    if structured_diff and structured_diff.get("added"):
        for item in structured_diff["added"][:3]:
            val = str(item.get("value", ""))[:80]
            if val:
                highlights.append(f"New: {val}")

    # Build summary based on change type
    if change_type == ChangeType.PRICING_CHANGE:
        if highlights:
            return f"Pricing updated — {'; '.join(highlights[:3])}"
        prices_old = re.findall(r"\$[\d,.]+", " ".join(removed_lines))
        prices_new = re.findall(r"\$[\d,.]+", " ".join(added_lines))
        if prices_old and prices_new:
            return f"Pricing changed from {', '.join(prices_old[:3])} to {', '.join(prices_new[:3])}"
        return f"Pricing page updated with {len(added_lines)} changes"

    if change_type == ChangeType.PRODUCT_UPDATE:
        key = [l for l in added_lines if any(kw in l.lower() for kw in ["feature", "introducing", "new", "launch", "now", "support"])]
        if key:
            return f"Product update — {key[0][:120]}"
        if highlights:
            return f"Product update — {'; '.join(highlights[:2])}"
        return f"Product page updated with {len(added_lines)} additions"

    if change_type == ChangeType.PARTNERSHIP_NEW:
        partners = [l for l in added_lines if any(kw in l.lower() for kw in ["partner", "integration", "collaborat", "works with", "powered by"])]
        if partners:
            return f"New partnership — {partners[0][:120]}"
        return f"Partnership page updated with {len(added_lines)} new entries"

    if change_type == ChangeType.TECH_STACK_CHANGE:
        if highlights:
            return f"Tech stack change — {'; '.join(highlights[:3])}"
        return f"Tech stack updated"

    if change_type == ChangeType.PAGE_ADDED:
        return f"New {page_type} page discovered"

    if change_type == ChangeType.PAGE_REMOVED:
        return f"{page_type.title()} page removed"

    # Generic content update
    interesting = [l for l in added_lines if len(l) > 20 and not l.startswith(("<", "{", "//"))]
    if interesting:
        return f"Content updated — {interesting[0][:120]}"
    return f"{page_type.title()} page updated with {len(added_lines)} changes"


# ---------------------------------------------------------------------------
# Detection pipeline
# ---------------------------------------------------------------------------

def detect_for_source(source_doc: dict) -> dict | None:
    """Detect changes for a single source. Returns a change dict or None."""
    source_id = source_doc["_id"]

    # Get latest two snapshots
    latest = db.get_latest_snapshot(source_id)
    if not latest:
        return None

    previous = db.get_previous_snapshot(source_id, latest["scraped_at"])
    if not previous:
        return None  # First snapshot — nothing to compare

    # Fast path: hash comparison
    if latest.get("content_hash") == previous.get("content_hash"):
        return None  # No change

    # Compute detailed diffs
    before_text = previous.get("extracted_text", "")
    after_text = latest.get("extracted_text", "")
    text_diff = compute_text_diff(before_text, after_text)

    before_struct = previous.get("structured_data", {})
    after_struct = latest.get("structured_data", {})
    structured_diff = compute_structured_diff(before_struct, after_struct)

    # Skip trivially small changes
    diff_lines = [l for l in text_diff.splitlines()
                  if l.startswith("+") or l.startswith("-")]
    if len(diff_lines) < 2:
        return None

    # Classify
    change_type = classify_change_type(source_doc, text_diff)
    severity = classify_severity(change_type, text_diff, before_text, after_text, structured_diff)
    summary = generate_summary(change_type, text_diff, source_doc, structured_diff)

    # Build change document
    now = datetime.now(timezone.utc)
    change_doc = {
        "_id": str(__import__("bson").ObjectId()),
        "source_id": source_id,
        "competitor_id": source_doc.get("competitor_id", ""),
        "snapshot_before_id": previous["_id"],
        "snapshot_after_id": latest["_id"],
        "detected_at": now,
        "change_type": change_type.value,
        "severity": severity.value,
        "summary": summary,
        "text_diff": text_diff[:10000],  # Cap diff size
        "structured_diff": structured_diff,
        "is_analyzed": False,
        "analysis_id": None,
        "is_alerted": False,
        "created_at": now,
    }

    db.save_change(change_doc)
    return change_doc


def detect_all(source_filter: dict | None = None) -> list[dict]:
    """Run detection across sources matching the filter."""
    if source_filter:
        source_docs = db.get_active_sources(**source_filter)
    else:
        source_docs = db.get_active_sources()

    results = []
    for source_doc in source_docs:
        change = detect_for_source(source_doc)
        if change:
            results.append(change)

    return results


# ---------------------------------------------------------------------------
# Output formatting (for the agent to read)
# ---------------------------------------------------------------------------

def format_change_for_insights(change: dict, source_doc: dict | None = None) -> dict:
    """Return change + full old/new snapshot data for generate_insights.py."""
    agent_data = format_change_for_agent(change, source_doc)

    old_snapshot = db.get_snapshot_by_id(change["snapshot_before_id"]) if change.get("snapshot_before_id") else None
    new_snapshot = db.get_snapshot_by_id(change["snapshot_after_id"]) if change.get("snapshot_after_id") else None

    def _snapshot_payload(snap: dict | None) -> dict:
        if not snap:
            return {"extracted_text": "", "structured_data": {}}
        return {
            "extracted_text": snap.get("extracted_text", ""),
            "structured_data": snap.get("structured_data", {}),
        }

    return {
        "change": agent_data,
        "old_snapshot": _snapshot_payload(old_snapshot),
        "new_snapshot": _snapshot_payload(new_snapshot),
        "source": {
            "url": source_doc.get("url", "") if source_doc else "",
            "page_type": source_doc.get("page_type", "") if source_doc else "",
            "competitor_slug": agent_data.get("competitor_slug", ""),
        },
    }


def format_change_for_agent(change: dict, source_doc: dict | None = None) -> dict:
    """Format a change into a concise dict the agent can analyze."""
    # Get competitor info
    competitor = None
    if change.get("competitor_id"):
        competitor = db.get_competitor_by_id(change["competitor_id"])

    return {
        "change_id": change["_id"],
        "competitor": competitor.get("name", "Unknown") if competitor else "Unknown",
        "competitor_slug": competitor.get("slug", "") if competitor else "",
        "source_url": source_doc.get("url", "") if source_doc else "",
        "page_type": source_doc.get("page_type", "") if source_doc else "",
        "change_type": change["change_type"],
        "severity": change["severity"],
        "summary": change["summary"],
        "text_diff": change["text_diff"][:5000],  # Truncate for LLM context
        "structured_diff": change.get("structured_diff", {}),
        "detected_at": change["detected_at"].isoformat() if isinstance(change["detected_at"], datetime) else str(change["detected_at"]),
    }


# ---------------------------------------------------------------------------
# Auto-analyze + alert pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(results: list[dict], analyze: bool, alert: bool, no_llm: bool) -> list[dict]:
    """For each detected change, optionally generate insights, save analysis, and send rich Slack alert."""
    if not analyze and not alert:
        return results

    from generate_insights import generate_insights, set_llm_enabled
    from format_slack import format_change_alert, format_change_alert_rich, send_to_slack

    if no_llm:
        set_llm_enabled(False)

    output = []
    for change in results:
        source_doc = db.get_source_by_id(change["source_id"]) if change.get("source_id") else None
        data = format_change_for_insights(change, source_doc)

        # Generate deep insights
        insights = generate_insights(
            data["change"], data["old_snapshot"], data["new_snapshot"], data["source"]
        )

        # Save as analysis to DB (visible on dashboard)
        if analyze:
            now = datetime.now(timezone.utc)
            analysis_doc = {
                "_id": str(__import__("bson").ObjectId()),
                "change_id": change["_id"],
                "competitor_id": change.get("competitor_id", ""),
                "analysis_type": "deep_analysis",
                "generated_at": now,
                "content": {
                    "summary": insights.get("before_after_summary", ""),
                    "impact_assessment": insights.get("impact_headline", ""),
                    "actionable_insights": [a.get("action", "") for a in insights.get("actions", [])],
                    "category": change.get("change_type", "content_update"),
                    "confidence": insights.get("llm_confidence", 0.8),
                    # Investigation-style fields for rich dashboard display
                    "what_happened": insights.get("before_after_summary", ""),
                    "why_it_matters": insights.get("impact_headline", ""),
                    "market_context": insights.get("strategic_context", ""),
                    "recommended_response": "\n".join(
                        f"[{a.get('priority', 'medium').upper()}] {a.get('action', '')} — {a.get('team', '')}"
                        for a in insights.get("actions", [])
                    ),
                    "key_facts": insights.get("before_after_details", [])[:10],
                    "sources_cited": [data["source"].get("url", "")] if data["source"].get("url") else [],
                    "risk_level": change.get("severity", "medium"),
                },
                "created_at": now,
            }
            db.save_analysis(analysis_doc)
            db.mark_change_analyzed(change["_id"], analysis_doc["_id"])
            print(f"  [analysis] Saved analysis {analysis_doc['_id']} for change {change['_id']}", file=sys.stderr)

        # Send rich Slack alert
        if alert:
            payload = format_change_alert_rich(data["change"], insights)
            result = send_to_slack(payload)
            if result.get("status") == "sent":
                db.mark_change_alerted(change["_id"])
                print(f"  [alert] Sent rich Slack alert for {change['change_type']} ({change['severity']})", file=sys.stderr)
            else:
                print(f"  [alert] Failed to send: {result.get('error', 'unknown')}", file=sys.stderr)

        output.append({
            "change": format_change_for_agent(change, source_doc),
            "insights": insights,
        })

    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Detect changes between snapshots")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Check all active sources")
    group.add_argument("--competitor", help="Competitor slug")
    group.add_argument("--source-id", help="Single source ID")
    parser.add_argument("--with-snapshots", action="store_true",
                        help="Include full snapshot data for insights generation")
    parser.add_argument("--analyze", action="store_true",
                        help="Auto-generate deep insights and save analysis to DB")
    parser.add_argument("--alert", action="store_true",
                        help="Auto-send rich Slack alerts with deep analysis")
    parser.add_argument("--no-llm", action="store_true",
                        help="Disable LLM enhancement (rule-based analysis only)")
    args = parser.parse_args()

    try:
        if args.source_id:
            source_doc = db.get_source_by_id(args.source_id)
            if not source_doc:
                print(json.dumps({"error": f"Source not found: {args.source_id}"}), file=sys.stderr)
                sys.exit(1)
            change = detect_for_source(source_doc)
            results = [change] if change else []
        elif args.competitor:
            competitor = db.get_competitor_by_slug(args.competitor)
            if not competitor:
                print(json.dumps({"error": f"Competitor not found: {args.competitor}"}), file=sys.stderr)
                sys.exit(1)
            results = detect_all({"competitor_id": competitor["_id"]})
        else:  # --all
            results = detect_all()

        if not results:
            print("No changes detected.", file=sys.stderr)
            print(json.dumps([]))
            return

        # If --analyze or --alert, run the full pipeline
        if args.analyze or args.alert:
            output = _run_pipeline(results, args.analyze, args.alert, args.no_llm)
            print(json.dumps(output, indent=2, default=str))
        else:
            # Legacy: just format for agent consumption
            formatter = format_change_for_insights if args.with_snapshots else format_change_for_agent
            output = []
            for change in results:
                source_doc = db.get_source_by_id(change["source_id"]) if change.get("source_id") else None
                output.append(formatter(change, source_doc))
            print(json.dumps(output, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()