#!/usr/bin/env python3
"""Cross-competitor strategic reasoning and market trend analysis.

Connects dots across multiple competitors to identify:
- Market trends (multiple competitors making similar moves)
- Convergence patterns (competitors heading in the same direction)
- Strategic threats and opportunities
- Recommended actions based on competitive landscape

Usage:
    python3 strategic_reasoning.py --days 30
    python3 strategic_reasoning.py --days 7 --competitor testrival

Output:
    JSON with trends, correlations, threats, opportunities, and recommendations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import db
import llm

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
from dotenv import load_dotenv
load_dotenv(_env_path)

KB_PATH = Path(__file__).parent.parent / "references" / "competitor_kb.md"


# ---------------------------------------------------------------------------
# Rule-based correlation engine
# ---------------------------------------------------------------------------

def correlate_changes(changes: list[dict]) -> list[dict]:
    """Find patterns across competitors: multiple doing similar things.

    Returns a list of correlations, each with:
      - pattern: description of the pattern
      - competitors: list of competitor names involved
      - significance: low/medium/high
      - change_type: the common change type
    """
    correlations = []

    # Group changes by type
    by_type = defaultdict(list)
    for c in changes:
        ct = c.get("change_type", "content_update")
        comp_id = c.get("competitor_id", "")
        comp = db.get_competitor_by_id(comp_id)
        comp_name = comp["name"] if comp else comp_id
        by_type[ct].append({
            "competitor": comp_name,
            "severity": c.get("severity", "low"),
            "summary": c.get("summary", ""),
        })

    # Detect convergence: 2+ competitors with same change type
    for change_type, entries in by_type.items():
        unique_competitors = list(set(e["competitor"] for e in entries))
        if len(unique_competitors) >= 2:
            significance = "high" if len(unique_competitors) >= 3 else "medium"
            type_label = change_type.replace("_", " ").title()
            correlations.append({
                "pattern": f"{len(unique_competitors)} competitors made {type_label} changes",
                "competitors": unique_competitors,
                "significance": significance,
                "change_type": change_type,
                "details": [f"{e['competitor']}: {e['summary']}" for e in entries],
            })

    # Detect severity clustering: multiple HIGH/CRITICAL changes
    critical_changes = [c for c in changes if c.get("severity") in ("high", "critical")]
    if len(critical_changes) >= 3:
        comp_ids = set(c.get("competitor_id") for c in critical_changes)
        comp_names = []
        for cid in comp_ids:
            comp = db.get_competitor_by_id(cid)
            if comp:
                comp_names.append(comp["name"])
        correlations.append({
            "pattern": f"{len(critical_changes)} high-severity changes detected across {len(comp_names)} competitors",
            "competitors": comp_names,
            "significance": "high",
            "change_type": "mixed",
            "details": [c.get("summary", "") for c in critical_changes[:5]],
        })

    # Detect keyword patterns across summaries
    all_summaries = " ".join(c.get("summary", "").lower() for c in changes)
    keyword_themes = {
        "AI/ML push": ["ai", "machine learning", "ml", "llm", "copilot", "intelligent"],
        "Price changes": ["price", "pricing", "cost", "plan", "tier"],
        "Enterprise focus": ["enterprise", "soc2", "hipaa", "compliance", "security"],
        "Expansion": ["hiring", "funding", "series", "raised", "office", "expansion"],
        "Partnerships": ["partner", "integration", "ecosystem", "marketplace"],
    }

    for theme, keywords in keyword_themes.items():
        hits = sum(1 for kw in keywords if kw in all_summaries)
        if hits >= 2:
            # Find which competitors are driving this theme
            theme_competitors = set()
            for c in changes:
                summary = c.get("summary", "").lower()
                if any(kw in summary for kw in keywords):
                    comp = db.get_competitor_by_id(c.get("competitor_id", ""))
                    if comp:
                        theme_competitors.add(comp["name"])
            if theme_competitors:
                correlations.append({
                    "pattern": f"Market trend: {theme}",
                    "competitors": sorted(theme_competitors),
                    "significance": "medium" if len(theme_competitors) < 3 else "high",
                    "change_type": "trend",
                    "details": [f"Detected across {len(theme_competitors)} competitor(s)"],
                })

    return correlations


# ---------------------------------------------------------------------------
# LLM-powered strategic analysis
# ---------------------------------------------------------------------------

def analyze_market_trends(days: int = 30, competitor_slug: str | None = None) -> dict:
    """Analyze market trends across all competitors using changes, partnerships, and KB.

    Returns dict with: trends, correlations, threats, opportunities, recommendations.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Gather changes
    if competitor_slug:
        comp = db.get_competitor_by_slug(competitor_slug)
        if not comp:
            return {"error": f"Competitor not found: {competitor_slug}"}
        changes = list(db.changes().find({
            "competitor_id": comp["_id"],
            "detected_at": {"$gte": cutoff},
        }))
    else:
        changes = list(db.changes().find({"detected_at": {"$gte": cutoff}}))

    # Gather partnerships
    partnerships = list(db.partnerships().find({"discovered_at": {"$gte": cutoff}}))

    # Rule-based correlations
    correlations = correlate_changes(changes)

    # Build summary for each competitor
    competitor_summaries = defaultdict(list)
    for c in changes:
        comp = db.get_competitor_by_id(c.get("competitor_id", ""))
        name = comp["name"] if comp else "Unknown"
        competitor_summaries[name].append({
            "type": c.get("change_type"),
            "severity": c.get("severity"),
            "summary": c.get("summary", ""),
        })

    partnership_summaries = []
    for p in partnerships:
        comp = db.get_competitor_by_id(p.get("competitor_id", ""))
        name = comp["name"] if comp else "Unknown"
        partnership_summaries.append({
            "competitor": name,
            "partner": p.get("partner_name"),
            "type": p.get("partnership_type"),
            "confidence": p.get("confidence", 0),
        })

    # Read KB for historical context
    kb_content = ""
    try:
        kb_content = KB_PATH.read_text()
    except FileNotFoundError:
        pass

    result = {
        "period_days": days,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "total_changes": len(changes),
        "total_partnerships": len(partnerships),
        "competitors_active": len(competitor_summaries),
        "correlations": correlations,
        "competitor_summaries": dict(competitor_summaries),
        "partnership_activity": partnership_summaries,
    }

    # Enhance with LLM if available
    if llm.is_available():
        llm_analysis = _llm_strategic_analysis(
            competitor_summaries, partnership_summaries, correlations, kb_content, days
        )
        if llm_analysis:
            result["strategic_analysis"] = llm_analysis

    return result


def _llm_strategic_analysis(
    competitor_summaries: dict,
    partnerships: list[dict],
    correlations: list[dict],
    kb_content: str,
    days: int,
) -> dict | None:
    """Ask Claude to synthesize strategic insights across competitors."""
    prompt = """You are a VP of Competitive Strategy. Analyze the competitive landscape data below and return a JSON object with:

- "market_trends": Array of 3-5 market-level trends you observe (each a string)
- "threats": Array of 2-4 strategic threats (each with "threat" and "severity" keys)
- "opportunities": Array of 2-4 strategic opportunities (each with "opportunity" and "urgency" keys, urgency = high/medium/low)
- "recommendations": Array of 3-5 specific recommended actions (each with "action", "priority" high/medium/low, "team", "rationale" keys)
- "executive_headline": One sentence summarizing the competitive landscape this period

Be specific. Reference competitor names, numbers, and concrete facts. No vague platitudes."""

    context = f"""COMPETITIVE INTELLIGENCE — Last {days} days

CHANGES BY COMPETITOR:
{json.dumps(dict(competitor_summaries), indent=2, default=str)[:3000]}

PARTNERSHIP ACTIVITY:
{json.dumps(partnerships, indent=2, default=str)[:1000]}

DETECTED PATTERNS:
{json.dumps(correlations, indent=2, default=str)[:1000]}

HISTORICAL CONTEXT (Knowledge Base):
{kb_content[:2000]}"""

    return llm.analyze(prompt, context, max_tokens=2000)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Cross-competitor strategic reasoning")
    parser.add_argument("--days", type=int, default=30, help="Analysis window in days (default: 30)")
    parser.add_argument("--competitor", type=str, default=None, help="Filter to one competitor (slug)")
    args = parser.parse_args()

    try:
        result = analyze_market_trends(days=args.days, competitor_slug=args.competitor)
        print(json.dumps(result, indent=2, default=str))

        # Summary to stderr
        n_changes = result.get("total_changes", 0)
        n_corr = len(result.get("correlations", []))
        n_partners = result.get("total_partnerships", 0)
        has_llm = "strategic_analysis" in result
        print(
            f"\nStrategic Analysis: {n_changes} changes, {n_partners} partnerships, "
            f"{n_corr} pattern(s) detected, LLM={'yes' if has_llm else 'no'}",
            file=sys.stderr,
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()