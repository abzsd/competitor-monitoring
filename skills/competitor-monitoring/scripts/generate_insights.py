#!/usr/bin/env python3
"""Generate insights for detected changes — rule-based + optional LLM enhancement.

Uses rule-based analysis as the foundation, then optionally enhances with
Claude (Anthropic API) for richer strategic insights.

Usage:
    python3 generate_insights.py --change-json '<json>'
    python3 generate_insights.py --change-file /path/to/change.json
    python3 generate_insights.py --change-json '<json>' --no-llm

The input JSON must have keys: change, old_snapshot, new_snapshot, source.
Output: InsightReport as JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm


# ---------------------------------------------------------------------------
# Price parsing helpers
# ---------------------------------------------------------------------------

def _parse_price(price_str: str) -> float | None:
    """Extract numeric price from strings like '$99/user/mo', 'Custom', etc."""
    if not price_str:
        return None
    cleaned = price_str.lower().strip()
    if any(w in cleaned for w in ["custom", "contact", "free", "n/a", "talk to", "get a quote"]):
        return None
    match = re.search(r"[\$\u20ac\u00a3]?\s*(\d[\d,]*\.?\d*)", price_str)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def _format_pct(pct: float | None) -> str:
    if pct is None:
        return "N/A"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def _pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return ((new - old) / old) * 100


# ---------------------------------------------------------------------------
# Feature diff helpers
# ---------------------------------------------------------------------------

def _normalize_feature(f: str) -> str:
    return re.sub(r"\s+", " ", f.strip().lower())


def _diff_features(old_feats: list[str], new_feats: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return (added, removed, unchanged) feature lists."""
    old_norm = {_normalize_feature(f): f for f in old_feats}
    new_norm = {_normalize_feature(f): f for f in new_feats}
    added = [new_norm[k] for k in new_norm if k not in old_norm]
    removed = [old_norm[k] for k in old_norm if k not in new_norm]
    unchanged = [old_norm[k] for k in old_norm if k in new_norm]
    return added, removed, unchanged


# ---------------------------------------------------------------------------
# Trial / billing change detection
# ---------------------------------------------------------------------------

def _detect_trial_changes(text_diff: str) -> list[str]:
    notes = []
    old_trial = re.search(r"-.*?(\d+)[- ]day.*?(?:free )?trial", text_diff, re.IGNORECASE)
    new_trial = re.search(r"\+.*?(\d+)[- ]day.*?(?:free )?trial", text_diff, re.IGNORECASE)
    if old_trial and new_trial:
        old_d, new_d = int(old_trial.group(1)), int(new_trial.group(1))
        if old_d != new_d:
            direction = "reduced" if new_d < old_d else "extended"
            notes.append(f"Trial period {direction} from {old_d} to {new_d} days")
    if re.search(r"\+.*credit card.*required", text_diff, re.IGNORECASE):
        notes.append("Credit card now required for trial signup")
    elif re.search(r"-.*credit card.*required", text_diff, re.IGNORECASE):
        notes.append("Credit card no longer required for trial")
    if re.search(r"\+.*annual.*contract.*required", text_diff, re.IGNORECASE):
        notes.append("Annual contract now required")
    return notes


# ---------------------------------------------------------------------------
# Signal detection (for content/blog)
# ---------------------------------------------------------------------------

FUNDING_PATTERN = re.compile(
    r"\+.*?\$\s?([\d,]+\.?\d*)\s*(million|M|billion|B)\b.*?"
    r"(series\s+[A-Z]|funding|round|raised|investment|valuation)",
    re.IGNORECASE,
)
LAUNCH_KEYWORDS = ["launching", "introducing", "announcing", "now available", "general availability", "public beta", "we're excited to announce"]
HIRING_KEYWORDS = ["hiring", "we're growing", "team of", "new office", "expanding to", "open roles", "join our team", "500+", "200+"]
PARTNERSHIP_KEYWORDS = ["partnership", "strategic alliance", "integration with", "powered by", "collaboration with", "joint"]


def _detect_signals(text_diff: str) -> list[dict]:
    signals = []
    added_lines = "\n".join(l[1:] for l in text_diff.splitlines() if l.startswith("+"))

    for m in FUNDING_PATTERN.finditer(text_diff):
        amount = m.group(1).replace(",", "")
        unit = "M" if m.group(2).upper().startswith("M") else "B"
        signals.append({"type": "funding", "detail": f"${amount}{unit} {m.group(3).strip()}"})

    for kw in LAUNCH_KEYWORDS:
        if kw.lower() in added_lines.lower():
            # Extract the sentence containing the keyword
            for line in added_lines.splitlines():
                if kw.lower() in line.lower() and len(line.strip()) > 20:
                    signals.append({"type": "product_launch", "detail": line.strip()[:200]})
                    break
            break

    for kw in HIRING_KEYWORDS:
        if kw.lower() in added_lines.lower():
            signals.append({"type": "hiring", "detail": f"Hiring signal detected: '{kw}' mentioned in new content"})
            break

    for kw in PARTNERSHIP_KEYWORDS:
        if kw.lower() in added_lines.lower():
            for line in added_lines.splitlines():
                if kw.lower() in line.lower() and len(line.strip()) > 15:
                    signals.append({"type": "partnership", "detail": line.strip()[:200]})
                    break
            break

    return signals


# ---------------------------------------------------------------------------
# Match plans across snapshots
# ---------------------------------------------------------------------------

def _match_plans(old_plans: list[dict], new_plans: list[dict]) -> tuple[list[tuple], list[dict], list[dict]]:
    """Match old and new plans by name. Returns (matched_pairs, new_only, old_only)."""
    old_by_name = {}
    for p in old_plans:
        key = _normalize_feature(p.get("name", ""))
        if key:
            old_by_name[key] = p

    matched = []
    new_only = []
    matched_old_keys = set()

    for np in new_plans:
        key = _normalize_feature(np.get("name", ""))
        if key in old_by_name:
            matched.append((old_by_name[key], np))
            matched_old_keys.add(key)
        else:
            new_only.append(np)

    old_only = [old_by_name[k] for k in old_by_name if k not in matched_old_keys]
    return matched, new_only, old_only


# ===================================================================
# PRICING CHANGE ANALYZER
# ===================================================================

def analyze_pricing_change(change: dict, old_snap: dict, new_snap: dict, source: dict) -> dict:
    competitor = change.get("competitor", "Competitor")
    old_sd = old_snap.get("structured_data", {})
    new_sd = new_snap.get("structured_data", {})
    old_plans = old_sd.get("plans", [])
    new_plans = new_sd.get("plans", [])
    text_diff = change.get("text_diff", "")

    matched, new_only, removed = _match_plans(old_plans, new_plans)

    plan_comparisons = []
    price_increases = []
    price_decreases = []
    all_features_added = []
    all_features_removed = []

    for old_p, new_p in matched:
        old_price_val = _parse_price(old_p.get("price", ""))
        new_price_val = _parse_price(new_p.get("price", ""))
        pct = _pct_change(old_price_val, new_price_val)

        old_feats = old_p.get("features", [])
        new_feats = new_p.get("features", [])
        added, removed_f, unchanged = _diff_features(old_feats, new_feats)
        all_features_added.extend(added)
        all_features_removed.extend(removed_f)

        notes = _detect_trial_changes(text_diff)

        comp = {
            "plan_name": new_p.get("name", old_p.get("name", "Unknown")),
            "old_price": old_p.get("price", "N/A"),
            "new_price": new_p.get("price", "N/A"),
            "price_change_pct": round(pct, 1) if pct is not None else None,
            "features_added": added,
            "features_removed": removed_f,
            "features_unchanged_count": len(unchanged),
            "notes": notes,
        }
        plan_comparisons.append(comp)

        if pct is not None and pct > 0:
            price_increases.append((comp["plan_name"], pct))
        elif pct is not None and pct < 0:
            price_decreases.append((comp["plan_name"], pct))

    # Build narrative
    details = []
    for pc in plan_comparisons:
        pct_str = f" ({_format_pct(pc['price_change_pct'])})" if pc["price_change_pct"] is not None else ""
        details.append(f"{pc['plan_name']}: {pc['old_price']} → {pc['new_price']}{pct_str}")
        for f in pc["features_added"][:3]:
            details.append(f"  + Added: {f}")
        for f in pc["features_removed"][:3]:
            details.append(f"  - Removed: {f}")
    for np in new_only:
        details.append(f"NEW PLAN: {np.get('name', '?')} at {np.get('price', '?')}")
    for rp in removed:
        details.append(f"REMOVED PLAN: {rp.get('name', '?')}")

    trial_notes = _detect_trial_changes(text_diff)
    for n in trial_notes:
        details.append(f"Billing: {n}")

    # Summary
    if price_increases:
        biggest = max(price_increases, key=lambda x: x[1])
        summary = f"{competitor} raised prices across {len(price_increases)} plan(s). Largest increase: {biggest[0]} at {_format_pct(biggest[1])}."
    elif price_decreases:
        summary = f"{competitor} reduced prices across {len(price_decreases)} plan(s)."
    elif new_only:
        summary = f"{competitor} introduced {len(new_only)} new pricing plan(s)."
    else:
        summary = f"{competitor} updated pricing page structure and features."

    if all_features_added:
        summary += f" {len(all_features_added)} feature(s) added across plans."
    if trial_notes:
        summary += f" {trial_notes[0]}."

    # Impact
    impact_headline = ""
    impact_details = []
    affected_workflows = []

    if price_increases:
        max_pct = max(p[1] for p in price_increases)
        if max_pct > 20:
            impact_headline = f"Significant price increase ({_format_pct(max_pct)} on {price_increases[0][0]}) creates a major competitive opportunity."
            impact_details.append(f"Customers on {competitor}'s plans may experience sticker shock at renewal — prime time for competitive outreach")
            impact_details.append(f"Our pricing now has a larger gap advantage if we hold current prices")
            affected_workflows.extend(["Sales outreach to competitor customers", "Pricing comparison page", "Win/loss analysis"])
        else:
            impact_headline = f"Moderate price increase ({_format_pct(max_pct)}) — marginal impact but signals confidence in value proposition."
            impact_details.append(f"{competitor} is testing pricing power, suggesting strong retention metrics")
            affected_workflows.extend(["Pricing comparison page", "Sales battle cards"])

    if price_decreases:
        impact_headline = f"Price reduction signals competitive pressure or market repositioning."
        impact_details.append("May attract price-sensitive customers away from us")
        impact_details.append("Could indicate weaker-than-expected demand or investor pressure to grow")
        affected_workflows.extend(["Sales battle cards", "Pricing strategy review"])

    if all_features_added:
        ai_features = [f for f in all_features_added if any(w in f.lower() for w in ["ai", "ml", "intelligent", "smart", "predict"])]
        if ai_features:
            impact_details.append(f"AI/ML features added ({', '.join(ai_features[:3])}) — competitor investing heavily in AI differentiation")
            affected_workflows.append("Product AI roadmap")
        compliance_features = [f for f in all_features_added if any(w in f.lower() for w in ["hipaa", "soc", "iso", "gdpr", "compliance", "residency"])]
        if compliance_features:
            impact_details.append(f"Compliance features added ({', '.join(compliance_features[:3])}) — expanding into regulated industries")
            affected_workflows.append("Enterprise compliance roadmap")

    if trial_notes:
        for tn in trial_notes:
            if "reduced" in tn.lower() or "credit card" in tn.lower():
                impact_details.append(f"{tn} — higher friction may reduce their conversion rate, creating an opportunity for our freemium/trial advantage")
                affected_workflows.append("Marketing landing pages")

    # Poachable ideas
    poachable = []
    if all_features_added:
        for f in all_features_added[:5]:
            poachable.append(f"Consider adding: {f}")
    if new_only:
        for np in new_only:
            poachable.append(f"New '{np.get('name', '?')}' tier at {np.get('price', '?')} — evaluate if we need a similar tier")

    # Actions
    actions = []
    if price_increases:
        actions.append({"action": "Update pricing comparison page to highlight our price advantage", "priority": "high", "team": "marketing"})
        actions.append({"action": f"Launch targeted outreach to {competitor} customers facing price increases", "priority": "high", "team": "sales"})
        actions.append({"action": "Prepare competitive win/loss talking points with new pricing data", "priority": "medium", "team": "sales"})
    if price_decreases:
        actions.append({"action": "Review our pricing positioning — competitor is undercutting", "priority": "high", "team": "product"})
    if all_features_added:
        actions.append({"action": f"Assess feature parity gaps: {', '.join(all_features_added[:3])}", "priority": "medium", "team": "product"})
    if trial_notes:
        actions.append({"action": "Emphasize our trial advantage (longer/no CC) in marketing copy", "priority": "medium", "team": "marketing"})

    return {
        "change_type": change.get("change_type", "pricing_change"),
        "severity": change.get("severity", "high"),
        "competitor_name": competitor,
        "source_url": change.get("source_url", ""),
        "detected_at": change.get("detected_at", ""),
        "before_after_summary": summary,
        "before_after_details": details,
        "plan_comparisons": plan_comparisons,
        "new_plans": [{"name": p.get("name", "?"), "price": p.get("price", "?")} for p in new_only],
        "removed_plans": [{"name": p.get("name", "?"), "price": p.get("price", "?")} for p in removed],
        "impact_headline": impact_headline,
        "impact_details": impact_details,
        "affected_workflows": affected_workflows,
        "poachable_ideas": poachable,
        "actions": actions,
        "signals": [],
    }


# ===================================================================
# PRODUCT CHANGE ANALYZER
# ===================================================================

def analyze_product_change(change: dict, old_snap: dict, new_snap: dict, source: dict) -> dict:
    competitor = change.get("competitor", "Competitor")
    text_diff = change.get("text_diff", "")
    old_sd = old_snap.get("structured_data", {})
    new_sd = new_snap.get("structured_data", {})

    added_lines = [l[1:].strip() for l in text_diff.splitlines() if l.startswith("+") and len(l) > 3]
    removed_lines = [l[1:].strip() for l in text_diff.splitlines() if l.startswith("-") and len(l) > 3]

    # --- Structured comparisons ---
    section_diff = _compare_sections(
        old_sd.get("sections", []), new_sd.get("sections", [])
    )
    stat_changes = _compare_stats(old_sd.get("stats", []), new_sd.get("stats", []))
    old_ctas = old_sd.get("ctas", [])
    new_ctas = new_sd.get("ctas", [])
    ctas_added, ctas_removed = _compare_structured_lists(old_ctas, new_ctas)

    # Detect specific changes from diff text
    new_features = []
    tech_changes = []
    compliance_adds = []
    positioning_shifts = []

    for line in added_lines:
        lower = line.lower()
        if any(w in lower for w in ["ai", "ml", "intelligent", "smart", "copilot", "assistant", "predictive"]):
            new_features.append(line)
        elif any(w in lower for w in ["aws", "gcp", "azure", "kubernetes", "docker", "pytorch", "tensorflow", "react", "node", "python", "grpc", "graphql"]):
            tech_changes.append(line)
        elif any(w in lower for w in ["hipaa", "soc 2", "iso 27001", "gdpr", "compliance", "residency", "baa"]):
            compliance_adds.append(line)
        elif any(w in lower for w in ["all-in-one", "ai-powered", "platform for", "next generation", "reimagined"]):
            positioning_shifts.append(line)

    details = []

    # New page sections (from structured data)
    if section_diff["added"]:
        details.append(f"New page sections ({len(section_diff['added'])}):")
        for s in section_diff["added"][:5]:
            desc = f"  + *{s['heading']}*"
            if s.get("summary"):
                desc += f" — {s['summary'][:100]}"
            details.append(desc)

    if section_diff["removed"]:
        details.append(f"Sections removed ({len(section_diff['removed'])}):")
        for s in section_diff["removed"][:3]:
            details.append(f"  - ~{s['heading']}~")

    # Stats changes
    if stat_changes:
        details.append("Key metrics changed:")
        for sc in stat_changes[:5]:
            details.append(f"  {sc['metric']}: {sc['old_value']} → {sc['new_value']}")

    if new_features:
        details.append(f"AI/ML features detected ({len(new_features)}):")
        for f in new_features[:8]:
            details.append(f"  + {f}")
    if tech_changes:
        details.append(f"Tech stack changes ({len(tech_changes)}):")
        for t in tech_changes[:5]:
            details.append(f"  ~ {t}")
    if compliance_adds:
        details.append(f"Compliance additions ({len(compliance_adds)}):")
        for c in compliance_adds[:5]:
            details.append(f"  + {c}")
    if positioning_shifts:
        details.append("Positioning shifts:")
        for p in positioning_shifts[:3]:
            details.append(f"  ~ {p}")
    if ctas_added:
        details.append(f"New CTAs: {', '.join(ctas_added[:5])}")
    if removed_lines and not details:
        notable_removals = [l for l in removed_lines if len(l) > 30][:3]
        if notable_removals:
            details.append("Notable removals:")
            for r in notable_removals:
                details.append(f"  - {r}")

    # Summary
    parts = []
    if section_diff["added"]:
        parts.append(f"{len(section_diff['added'])} new section(s) added")
    if new_features:
        parts.append(f"{len(new_features)} AI/ML feature(s)")
    if stat_changes:
        parts.append(f"{len(stat_changes)} metric(s) changed")
    if tech_changes:
        parts.append(f"tech stack updates ({len(tech_changes)} changes)")
    if compliance_adds:
        parts.append(f"compliance additions ({', '.join(c.split()[0] for c in compliance_adds[:3])})")
    summary = f"{competitor} updated their product page: {'; '.join(parts)}." if parts else f"{competitor} made product page updates."

    # Impact
    impact_headline = ""
    impact_details = []
    affected_workflows = []

    if new_features:
        ai_count = len([f for f in new_features if any(w in f.lower() for w in ["ai", "ml", "smart", "predict"])])
        if ai_count > 0:
            impact_headline = f"{competitor} launched AI-powered features — significant product evolution that changes competitive dynamics."
            impact_details.append(f"{ai_count} AI-related features added, suggesting major R&D investment and likely a dedicated AI/ML team")
            impact_details.append("Customers evaluating PM tools will now compare AI capabilities as a key differentiator")
            impact_details.append("First-mover advantage on AI features could shift market expectations")
            affected_workflows.extend(["Product AI roadmap review", "Competitive demo scripting", "Sales battle cards"])
        else:
            impact_headline = f"{competitor} added new features, expanding their platform's breadth."
            impact_details.append("Feature additions may attract customers looking for an all-in-one solution")
            affected_workflows.extend(["Feature comparison matrix", "Product roadmap priorities"])

    if section_diff["added"]:
        for s in section_diff["added"][:3]:
            impact_details.append(f"New section '{s['heading']}' — evaluate competitive overlap and market positioning impact")
        affected_workflows.append("Competitive positioning review")

    if stat_changes:
        for sc in stat_changes:
            impact_details.append(f"Metric '{sc['metric']}' changed: {sc['old_value']} → {sc['new_value']} — verify and track growth trajectory")
        affected_workflows.append("Market intelligence tracking")

    if compliance_adds:
        impact_details.append(f"New compliance certifications ({', '.join(c[:20] for c in compliance_adds[:3])}) open regulated verticals (healthcare, finance, government)")
        impact_details.append("Enterprise buyers in regulated industries may now shortlist the competitor")
        affected_workflows.append("Enterprise compliance roadmap")

    if tech_changes:
        multi_cloud = any("gcp" in t.lower() or "azure" in t.lower() or "multi-cloud" in t.lower() for t in tech_changes)
        if multi_cloud:
            impact_details.append("Multi-cloud deployment suggests investment in enterprise flexibility and reduces vendor lock-in concerns")
            affected_workflows.append("Infrastructure strategy")

    if not impact_headline and section_diff["added"]:
        impact_headline = f"{competitor} expanded their product page with {len(section_diff['added'])} new section(s)."
    if not impact_headline:
        impact_headline = f"{competitor} updated product page — review for competitive implications."

    # Poachable
    poachable = []
    for f in new_features[:4]:
        poachable.append(f"Worth evaluating: {f}")
    for s in section_diff["added"][:3]:
        poachable.append(f"New section '{s['heading']}' — consider building similar capability")
    if compliance_adds:
        poachable.append(f"Compliance investment: {', '.join(compliance_adds[:2])} — opens enterprise segments")

    # Actions
    actions = []
    if new_features:
        actions.append({"action": "Update competitive feature comparison matrix", "priority": "high", "team": "product"})
        if any("ai" in f.lower() for f in new_features):
            actions.append({"action": "Accelerate AI feature roadmap to maintain parity", "priority": "high", "team": "engineering"})
            actions.append({"action": "Update sales demo to address AI feature gap", "priority": "medium", "team": "sales"})
    if compliance_adds:
        actions.append({"action": f"Evaluate compliance certifications: {', '.join(c[:15] for c in compliance_adds[:2])}", "priority": "medium", "team": "engineering"})
    if section_diff["added"]:
        actions.append({"action": f"Analyze new page sections: {', '.join(s['heading'] for s in section_diff['added'][:3])}", "priority": "medium", "team": "product"})
    if stat_changes:
        actions.append({"action": "Track competitor metric claims for competitive intelligence", "priority": "medium", "team": "marketing"})
    actions.append({"action": "Refresh competitive positioning document", "priority": "medium", "team": "marketing"})

    return {
        "change_type": change.get("change_type", "product_update"),
        "severity": change.get("severity", "medium"),
        "competitor_name": competitor,
        "source_url": change.get("source_url", ""),
        "detected_at": change.get("detected_at", ""),
        "before_after_summary": summary,
        "before_after_details": details,
        "plan_comparisons": [],
        "new_plans": [],
        "removed_plans": [],
        "impact_headline": impact_headline,
        "impact_details": impact_details,
        "affected_workflows": affected_workflows,
        "poachable_ideas": poachable,
        "actions": actions,
        "signals": _detect_signals(text_diff),
    }


# ===================================================================
# PARTNERSHIP CHANGE ANALYZER
# ===================================================================

def analyze_partnership_change(change: dict, old_snap: dict, new_snap: dict, source: dict) -> dict:
    competitor = change.get("competitor", "Competitor")
    old_sd = old_snap.get("structured_data", {})
    new_sd = new_snap.get("structured_data", {})
    old_partners = set(p.lower().strip() for p in old_sd.get("partners", []))
    new_partners_raw = new_sd.get("partners", [])
    new_partners = set(p.lower().strip() for p in new_partners_raw)

    added = new_partners - old_partners
    removed_p = old_partners - new_partners
    text_diff = change.get("text_diff", "")
    added_text = "\n".join(l[1:] for l in text_diff.splitlines() if l.startswith("+"))

    # Also use universal structured data for richer analysis
    section_diff = _compare_sections(
        old_sd.get("sections", []), new_sd.get("sections", [])
    )
    stat_changes = _compare_stats(old_sd.get("stats", []), new_sd.get("stats", []))

    TIER1 = {"salesforce", "microsoft", "google", "aws", "amazon", "apple", "meta", "oracle", "ibm", "sap", "adobe", "openai", "nvidia"}
    strategic = [p for p in added if any(t in p for t in TIER1)]
    tactical = [p for p in added if p not in strategic]

    details = []
    if strategic:
        details.append(f"STRATEGIC partners added ({len(strategic)}):")
        for p in strategic:
            # Find context from diff
            for line in added_text.splitlines():
                if p in line.lower() and len(line.strip()) > 20:
                    details.append(f"  * {line.strip()[:150]}")
                    break
            else:
                details.append(f"  * {p.title()}")
    if tactical:
        details.append(f"Technology/tactical partners added ({len(tactical)}):")
        for p in tactical[:8]:
            details.append(f"  + {p.title()}")
    if removed_p:
        details.append(f"Partners removed ({len(removed_p)}):")
        for p in removed_p:
            details.append(f"  - {p.title()}")

    # Add structural changes (new partner categories, stats changes)
    if section_diff["added"]:
        details.append(f"New page sections ({len(section_diff['added'])}):")
        for s in section_diff["added"][:5]:
            desc = f"  + *{s['heading']}*"
            if s.get("summary"):
                desc += f" — {s['summary'][:100]}"
            details.append(desc)
    if stat_changes:
        details.append("Ecosystem metrics changed:")
        for sc in stat_changes[:5]:
            details.append(f"  {sc['metric']}: {sc['old_value']} → {sc['new_value']}")

    # Summary
    if strategic:
        summary = f"{competitor} announced strategic partnerships with {', '.join(p.title() for p in strategic)}."
    elif added:
        summary = f"{competitor} added {len(added)} new partner(s) to their ecosystem."
    else:
        summary = f"{competitor} updated their partnerships page."
    if tactical:
        summary += f" Plus {len(tactical)} technology integration(s)."

    # Impact
    impact_headline = ""
    impact_details = []
    affected_workflows = []

    if strategic:
        impact_headline = f"Strategic partnership(s) with {', '.join(p.title() for p in strategic)} — this is a significant competitive move."
        for p in strategic:
            if "salesforce" in p:
                impact_details.append("Salesforce integration creates a powerful CRM-to-PM pipeline that enterprise buyers will value highly")
                impact_details.append("Joint go-to-market with Salesforce gives them access to Salesforce's massive enterprise customer base")
                affected_workflows.extend(["CRM integration roadmap", "Enterprise sales strategy"])
            elif "microsoft" in p:
                impact_details.append("Microsoft/Azure Marketplace presence simplifies enterprise procurement and gets them into Teams ecosystem")
                impact_details.append("Azure AD SSO + Teams integration creates deep lock-in for Microsoft-centric enterprises")
                affected_workflows.extend(["Microsoft ecosystem strategy", "Enterprise procurement"])
            elif "openai" in p:
                impact_details.append("OpenAI partnership signals serious AI investment and access to cutting-edge models")
                affected_workflows.append("AI/ML strategy review")
            else:
                impact_details.append(f"Partnership with {p.title()} expands their market reach and integration ecosystem")
    if tactical:
        impact_details.append(f"{len(tactical)} new integrations expand their ecosystem breadth — may attract teams using those tools")
        affected_workflows.append("Integration roadmap priorities")

    if section_diff["added"]:
        for s in section_diff["added"][:3]:
            impact_details.append(f"New partner category '{s['heading']}' — signals expansion into new market segments")
        if not impact_headline:
            impact_headline = f"{competitor} restructured their partnerships page with {len(section_diff['added'])} new section(s)."
    if stat_changes:
        for sc in stat_changes:
            impact_details.append(f"Ecosystem metric '{sc['metric']}' changed: {sc['old_value']} → {sc['new_value']}")
        affected_workflows.append("Market intelligence tracking")
    if not impact_headline:
        impact_headline = f"{competitor} updated their partnerships ecosystem."

    # Poachable
    poachable = []
    for p in strategic:
        poachable.append(f"Explore our own partnership opportunity with {p.title()}")
    for p in tactical[:3]:
        poachable.append(f"Consider building a {p.title()} integration")

    # Actions
    actions = []
    if strategic:
        actions.append({"action": f"Assess our own partnership opportunities with {', '.join(p.title() for p in strategic)}", "priority": "high", "team": "partnerships"})
        actions.append({"action": "Update competitive positioning to address new partnership advantages", "priority": "high", "team": "marketing"})
    if added:
        actions.append({"action": "Review integration roadmap for gaps created by competitor's new partnerships", "priority": "medium", "team": "product"})
    actions.append({"action": "Brief sales team on competitor's expanded partner ecosystem", "priority": "medium", "team": "sales"})

    return {
        "change_type": change.get("change_type", "partnership_new"),
        "severity": change.get("severity", "high"),
        "competitor_name": competitor,
        "source_url": change.get("source_url", ""),
        "detected_at": change.get("detected_at", ""),
        "before_after_summary": summary,
        "before_after_details": details,
        "plan_comparisons": [],
        "new_plans": [],
        "removed_plans": [],
        "impact_headline": impact_headline,
        "impact_details": impact_details,
        "affected_workflows": affected_workflows,
        "poachable_ideas": poachable,
        "actions": actions,
        "signals": _detect_signals(text_diff),
    }


# ===================================================================
# CONTENT / BLOG CHANGE ANALYZER
# ===================================================================

def _compare_structured_lists(old_items: list[str], new_items: list[str]) -> tuple[list[str], list[str]]:
    """Compare two lists of strings, return (added, removed) after normalization."""
    old_norm = {_normalize_feature(x) for x in old_items if x}
    new_norm = {_normalize_feature(x) for x in new_items if x}
    added = [x for x in new_items if _normalize_feature(x) in (new_norm - old_norm)]
    removed = [x for x in old_items if _normalize_feature(x) in (old_norm - new_norm)]
    return added, removed


def _compare_sections(old_sections: list[dict], new_sections: list[dict]) -> dict:
    """Compare page sections by heading. Returns {added, removed, changed}."""
    old_map = {s.get("heading", "").lower().strip(): s for s in old_sections}
    new_map = {s.get("heading", "").lower().strip(): s for s in new_sections}
    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())
    return {
        "added": [new_map[k] for k in (new_keys - old_keys) if k],
        "removed": [old_map[k] for k in (old_keys - new_keys) if k],
        "changed": [
            {"heading": new_map[k]["heading"],
             "old_summary": old_map[k].get("summary", ""),
             "new_summary": new_map[k].get("summary", "")}
            for k in (old_keys & new_keys)
            if k and old_map[k].get("summary", "") != new_map[k].get("summary", "")
        ],
    }


def _compare_stats(old_stats: list[dict], new_stats: list[dict]) -> list[dict]:
    """Find stats that changed value between snapshots."""
    old_by_ctx = {s.get("context", "").lower().strip(): s for s in old_stats if s.get("context")}
    changes = []
    for ns in new_stats:
        ctx = ns.get("context", "").lower().strip()
        if ctx and ctx in old_by_ctx:
            old_val = old_by_ctx[ctx].get("value", "")
            new_val = ns.get("value", "")
            if old_val != new_val:
                changes.append({
                    "metric": ns.get("context", ctx),
                    "old_value": old_val,
                    "new_value": new_val,
                })
    return changes


def analyze_content_change(change: dict, old_snap: dict, new_snap: dict, source: dict) -> dict:
    competitor = change.get("competitor", "Competitor")
    text_diff = change.get("text_diff", "")
    old_sd = old_snap.get("structured_data", {})
    new_sd = new_snap.get("structured_data", {})
    added_lines = [l[1:].strip() for l in text_diff.splitlines() if l.startswith("+") and len(l) > 5]
    added_text = "\n".join(added_lines)

    signals = _detect_signals(text_diff)
    signal_types = [s["type"] for s in signals]

    # --- Structured comparisons ---
    # Sections
    section_diff = _compare_sections(
        old_sd.get("sections", []), new_sd.get("sections", [])
    )
    # Headings
    old_headings = [h["text"] for h in old_sd.get("headings", [])]
    new_headings = [h["text"] for h in new_sd.get("headings", [])]
    headings_added, headings_removed = _compare_structured_lists(old_headings, new_headings)
    # Stats
    stat_changes = _compare_stats(old_sd.get("stats", []), new_sd.get("stats", []))
    # CTAs
    old_ctas = old_sd.get("ctas", [])
    new_ctas = new_sd.get("ctas", [])
    ctas_added, ctas_removed = _compare_structured_lists(old_ctas, new_ctas)
    # Features
    old_features = old_sd.get("features", [])
    new_features = new_sd.get("features", [])
    features_added, features_removed = _compare_structured_lists(old_features, new_features)

    # --- Build detailed report ---
    details = []

    # New sections
    if section_diff["added"]:
        details.append(f"New page sections added ({len(section_diff['added'])}):")
        for s in section_diff["added"][:5]:
            desc = f"  + *{s['heading']}*"
            if s.get("summary"):
                desc += f" — {s['summary'][:100]}"
            details.append(desc)

    # Removed sections
    if section_diff["removed"]:
        details.append(f"Page sections removed ({len(section_diff['removed'])}):")
        for s in section_diff["removed"][:5]:
            details.append(f"  - ~{s['heading']}~")

    # Changed sections
    if section_diff["changed"]:
        details.append("Sections with updated content:")
        for s in section_diff["changed"][:5]:
            details.append(f"  ~ {s['heading']}")

    # Stat changes
    if stat_changes:
        details.append("Key metrics changed:")
        for sc in stat_changes[:8]:
            details.append(f"  {sc['metric']}: {sc['old_value']} → {sc['new_value']}")

    # New headings (that aren't already covered by sections)
    section_heading_set = {s["heading"].lower() for s in section_diff.get("added", [])}
    extra_headings = [h for h in headings_added if h.lower() not in section_heading_set]
    if extra_headings:
        details.append("New content headings:")
        for h in extra_headings[:5]:
            details.append(f"  + {h}")

    # CTA changes (positioning signal)
    if ctas_added:
        details.append(f"New CTAs: {', '.join(ctas_added[:5])}")
    if ctas_removed:
        details.append(f"Removed CTAs: {', '.join(ctas_removed[:5])}")

    # Feature list changes
    if features_added:
        details.append(f"Features/items added ({len(features_added)}):")
        for f in features_added[:8]:
            details.append(f"  + {f[:120]}")
    if features_removed:
        details.append(f"Features/items removed ({len(features_removed)}):")
        for f in features_removed[:5]:
            details.append(f"  - {f[:120]}")

    # Signals
    if signals:
        details.append("Signals detected:")
        for s in signals:
            details.append(f"  ⚡ {s['type'].replace('_', ' ').title()}: {s['detail'][:120]}")

    # If no structured changes found, fall back to raw diff lines
    if not details:
        for line in added_lines[:10]:
            if len(line) > 30:
                details.append(f"+ {line[:200]}")

    # --- Summary ---
    summary_parts = []
    if "funding" in signal_types:
        fund = next(s for s in signals if s["type"] == "funding")
        summary_parts.append(f"funding announcement ({fund['detail']})")
    if "product_launch" in signal_types:
        summary_parts.append("new product/feature launch")
    if "partnership" in signal_types:
        summary_parts.append("partnership announcement")
    if "hiring" in signal_types:
        summary_parts.append("hiring/expansion signals")
    if section_diff["added"]:
        section_names = ", ".join(s["heading"] for s in section_diff["added"][:3])
        summary_parts.append(f"new sections: {section_names}")
    if stat_changes:
        summary_parts.append(f"{len(stat_changes)} metric(s) changed")
    if features_added:
        summary_parts.append(f"{len(features_added)} feature(s) added")

    page_type = source.get("page_type", "page")
    if summary_parts:
        summary = f"{competitor} updated their {page_type} page: {'; '.join(summary_parts)}."
    else:
        summary = f"{competitor} updated content on their {page_type} page."

    # --- Impact ---
    impact_headline = ""
    impact_details = []
    affected_workflows = []

    if "funding" in signal_types:
        impact_headline = "Funding announcement signals aggressive growth plans and increased competitive pressure."
        impact_details.append("Expect increased marketing spend, faster hiring, and accelerated product development")
        impact_details.append("Competitors with fresh funding often pursue market share with aggressive pricing and outbound sales")
        impact_details.append("May also indicate upcoming acquisitions or major product bets")
        affected_workflows.extend(["Competitive strategy review", "Board/investor update", "Sales battle cards"])

    if "product_launch" in signal_types:
        if not impact_headline:
            impact_headline = "New product launch may shift market expectations and customer evaluations."
        impact_details.append("New features/products change the competitive evaluation criteria for prospects in-pipeline")
        impact_details.append("Monitor customer reactions and early reviews for product-market fit signals")
        affected_workflows.extend(["Product roadmap review", "Marketing messaging", "Demo scripting"])

    if "hiring" in signal_types:
        impact_details.append("Hiring signals indicate investment in specific areas — what roles they're hiring reveals strategic priorities")
        affected_workflows.append("Talent strategy")

    if section_diff["added"]:
        if not impact_headline:
            impact_headline = f"{competitor} added {len(section_diff['added'])} new section(s) — expanding their page scope and messaging."
        for s in section_diff["added"][:3]:
            impact_details.append(f"New section '{s['heading']}' expands their positioning — evaluate competitive overlap")
        affected_workflows.append("Competitive positioning review")

    if stat_changes:
        for sc in stat_changes:
            impact_details.append(f"Metric '{sc['metric']}' changed from {sc['old_value']} to {sc['new_value']} — track whether this reflects real growth or re-framing")
        affected_workflows.append("Market intelligence tracking")

    if ctas_added or ctas_removed:
        if not impact_headline:
            impact_headline = "CTA changes suggest a shift in go-to-market strategy."
        if ctas_added:
            impact_details.append(f"New CTAs ({', '.join(ctas_added[:3])}) may indicate a shift in conversion strategy")
        affected_workflows.append("Marketing funnel analysis")

    if not impact_headline:
        impact_headline = "Content update worth monitoring for strategic signals."

    # --- Poachable ---
    poachable = []
    for s in signals:
        if s["type"] == "product_launch":
            poachable.append(f"Evaluate: {s['detail'][:100]}")
    for s in section_diff["added"][:3]:
        poachable.append(f"New page section '{s['heading']}' — consider if we need similar content")
    if features_added:
        for f in features_added[:3]:
            poachable.append(f"Feature worth evaluating: {f[:100]}")
    if not poachable and added_lines:
        for line in added_lines[:3]:
            if len(line) > 40:
                poachable.append(f"Content theme worth noting: {line[:100]}")

    # --- Actions ---
    actions = []
    if "funding" in signal_types:
        actions.append({"action": "Update competitive landscape document with new funding data", "priority": "high", "team": "strategy"})
        actions.append({"action": "Prepare talking points for customers asking about competitor's funding", "priority": "medium", "team": "sales"})
    if "product_launch" in signal_types:
        actions.append({"action": "Conduct deep-dive on announced product/features", "priority": "high", "team": "product"})
        actions.append({"action": "Update sales battle cards with new competitive features", "priority": "medium", "team": "sales"})
    if "partnership" in signal_types:
        actions.append({"action": "Assess impact of announced partnership on our positioning", "priority": "medium", "team": "partnerships"})
    if section_diff["added"]:
        actions.append({"action": f"Review new competitor page sections: {', '.join(s['heading'] for s in section_diff['added'][:3])}", "priority": "medium", "team": "marketing"})
    if stat_changes:
        actions.append({"action": "Verify competitor's claimed metrics and update competitive intel", "priority": "medium", "team": "marketing"})
    if features_added:
        actions.append({"action": f"Evaluate {len(features_added)} new feature(s) for competitive parity gaps", "priority": "medium", "team": "product"})
    if not actions:
        actions.append({"action": "Review content for strategic insights and update competitor profile", "priority": "low", "team": "marketing"})

    return {
        "change_type": change.get("change_type", "content_update"),
        "severity": change.get("severity", "medium"),
        "competitor_name": competitor,
        "source_url": change.get("source_url", ""),
        "detected_at": change.get("detected_at", ""),
        "before_after_summary": summary,
        "before_after_details": details,
        "plan_comparisons": [],
        "new_plans": [],
        "removed_plans": [],
        "impact_headline": impact_headline,
        "impact_details": impact_details,
        "affected_workflows": affected_workflows,
        "poachable_ideas": poachable,
        "actions": actions,
        "signals": signals,
    }


# ===================================================================
# LLM ENHANCEMENT LAYER
# ===================================================================

# Flag to disable LLM at runtime (set by --no-llm or LLM_ENABLED=false)
_llm_enabled = True


def set_llm_enabled(enabled: bool) -> None:
    """Toggle LLM enhancement on/off."""
    global _llm_enabled
    _llm_enabled = enabled


def _should_use_llm() -> bool:
    """Check if LLM is both enabled and available."""
    if not _llm_enabled:
        return False
    env_flag = os.environ.get("LLM_ENABLED", "true").lower()
    if env_flag in ("false", "0", "no"):
        return False
    return llm.is_available()


def enhance_with_llm(
    rule_based: dict,
    change: dict,
    old_snapshot: dict,
    new_snapshot: dict,
    source: dict,
) -> dict:
    """Enhance rule-based insights with Claude's strategic analysis.

    Keeps all rule-based data intact and adds/overrides with LLM output.
    Returns the original rule-based dict if LLM fails.
    """
    if not _should_use_llm():
        return rule_based

    competitor = rule_based.get("competitor_name", "Unknown")
    change_type = rule_based.get("change_type", "content_update")
    severity = rule_based.get("severity", "medium")

    # Prepare context: text diff (truncated) + structured data summary
    text_diff = change.get("text_diff", "")[:3000]
    structured_diff = json.dumps(change.get("structured_diff", {}), default=str)[:2000]

    # Include rule-based findings as context
    rule_summary = {
        "before_after_summary": rule_based.get("before_after_summary", ""),
        "impact_headline": rule_based.get("impact_headline", ""),
        "signals": rule_based.get("signals", []),
        "actions": [a.get("action", "") for a in rule_based.get("actions", [])[:5]],
    }

    prompt = f"""You are a senior competitive intelligence analyst. Analyze this competitor change and provide strategic insights.

Respond with a JSON object containing these keys:
- "impact_headline": One sentence describing the strategic impact (be specific, include numbers)
- "impact_details": Array of 3-5 strategic implications (business-level, not technical)
- "strategic_context": 2-3 sentences placing this change in broader market context
- "confidence": Float 0.0-1.0 for how confident you are in this analysis
- "poachable_ideas": Array of 1-3 ideas worth considering for our own product
- "actions": Array of objects with "action", "priority" (high/medium/low), "team" fields

Be specific and actionable. Include numbers and names. No vague platitudes."""

    context = f"""COMPETITOR: {competitor}
CHANGE TYPE: {change_type}
SEVERITY: {severity}
PAGE: {source.get('url', '')} ({source.get('page_type', 'unknown')})

TEXT DIFF (additions marked with +, removals with -):
{text_diff}

STRUCTURED DATA CHANGES:
{structured_diff}

RULE-BASED ANALYSIS (for context):
{json.dumps(rule_summary, indent=2, default=str)}"""

    result = llm.analyze(prompt, context)
    if result is None or "raw_response" in result:
        return rule_based

    # Merge LLM output over rule-based, keeping rule-based fields as fallback
    enhanced = dict(rule_based)
    enhanced["llm_enhanced"] = True

    if result.get("impact_headline"):
        enhanced["impact_headline"] = result["impact_headline"]
    if result.get("impact_details"):
        enhanced["impact_details"] = result["impact_details"]
    if result.get("strategic_context"):
        enhanced["strategic_context"] = result["strategic_context"]
    if result.get("confidence"):
        enhanced["llm_confidence"] = result["confidence"]
    if result.get("poachable_ideas"):
        enhanced["poachable_ideas"] = result["poachable_ideas"]
    if result.get("actions"):
        enhanced["actions"] = result["actions"]

    return enhanced


# ===================================================================
# KNOWLEDGE BASE UPDATES
# ===================================================================

KB_PATH = Path(__file__).parent.parent / "references" / "competitor_kb.md"


def update_knowledge_base(competitor_name: str, insights: dict, change: dict) -> None:
    """Append key learnings from an analysis to the competitor knowledge base.

    Updates references/competitor_kb.md with a timestamped entry under
    the competitor's section.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    change_type = change.get("change_type", "unknown")
    severity = change.get("severity", "unknown")

    # Build the KB entry
    summary = insights.get("before_after_summary", insights.get("impact_headline", "Change detected"))

    if _should_use_llm():
        # Ask LLM to condense insights into 2-3 bullets
        insight_text = json.dumps({
            "summary": summary,
            "impact": insights.get("impact_headline", ""),
            "signals": insights.get("signals", []),
            "actions": [a.get("action", "") for a in insights.get("actions", [])[:3]],
        }, default=str)
        condensed = llm.summarize(f"Competitive intelligence update about {competitor_name}:\n{insight_text}")
        if condensed:
            entry = f"\n### {timestamp} — {change_type.upper()} ({severity})\n{condensed}\n"
        else:
            entry = f"\n### {timestamp} — {change_type.upper()} ({severity})\n- {summary}\n"
    else:
        entry = f"\n### {timestamp} — {change_type.upper()} ({severity})\n- {summary}\n"

    # Read existing KB
    try:
        kb_content = KB_PATH.read_text()
    except FileNotFoundError:
        kb_content = "# Competitor Knowledge Base\n\n"

    # Find or create competitor section
    section_header = f"## {competitor_name}"
    if section_header in kb_content:
        # Append after the section header
        idx = kb_content.index(section_header) + len(section_header)
        # Find the next line break after the header
        next_nl = kb_content.index("\n", idx)
        kb_content = kb_content[:next_nl + 1] + entry + kb_content[next_nl + 1:]
    else:
        # Add new section before "## Key Observations" or at end
        if "## Key Observations" in kb_content:
            idx = kb_content.index("## Key Observations")
            kb_content = kb_content[:idx] + section_header + "\n" + entry + "\n" + kb_content[idx:]
        elif "## Historical Changes Log" in kb_content:
            idx = kb_content.index("## Historical Changes Log")
            kb_content = kb_content[:idx] + section_header + "\n" + entry + "\n" + kb_content[idx:]
        else:
            kb_content += "\n" + section_header + "\n" + entry

    KB_PATH.write_text(kb_content)


# ===================================================================
# MAIN ROUTER
# ===================================================================

def generate_insights(change: dict, old_snapshot: dict, new_snapshot: dict, source: dict) -> dict:
    """Route to the appropriate analyzer based on change type, then enhance with LLM."""
    ct = change.get("change_type", "content_update")
    if ct == "pricing_change":
        insights = analyze_pricing_change(change, old_snapshot, new_snapshot, source)
    elif ct == "product_update":
        insights = analyze_product_change(change, old_snapshot, new_snapshot, source)
    elif ct == "partnership_new":
        insights = analyze_partnership_change(change, old_snapshot, new_snapshot, source)
    else:
        insights = analyze_content_change(change, old_snapshot, new_snapshot, source)

    # Enhance with LLM if available
    insights = enhance_with_llm(insights, change, old_snapshot, new_snapshot, source)

    return insights


def main():
    parser = argparse.ArgumentParser(description="Generate deep insights for a detected change")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--change-json", help="Full JSON with change, old_snapshot, new_snapshot, source")
    input_group.add_argument("--change-file", help="Path to JSON file")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM enhancement (rule-based only)")
    args = parser.parse_args()

    if args.no_llm:
        set_llm_enabled(False)

    try:
        if args.change_file:
            with open(args.change_file) as f:
                data = json.load(f)
        else:
            data = json.loads(args.change_json)

        result = generate_insights(
            data["change"],
            data.get("old_snapshot", {}),
            data.get("new_snapshot", {}),
            data.get("source", {}),
        )
        print(json.dumps(result, indent=2, default=str))
    except (json.JSONDecodeError, KeyError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
