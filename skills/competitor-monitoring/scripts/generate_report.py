#!/usr/bin/env python3
"""Generate periodic competitive intelligence reports.

Usage:
    python3 generate_report.py --weekly [--competitor <slug>]
    python3 generate_report.py --monthly [--competitor <slug>]
    python3 generate_report.py --days 14 [--competitor <slug>]
    python3 generate_report.py --format json|markdown|html

Output:
    Structured report (JSON, Markdown, or HTML) summarizing competitive
    changes, partnerships, and recommended actions over the specified period.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import llm
from strategic_reasoning import analyze_market_trends


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------

def gather_changes(days: int, competitor_id: str | None = None) -> list[dict]:
    """Gather all changes from the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {"detected_at": {"$gte": cutoff}}
    if competitor_id:
        query["competitor_id"] = competitor_id
    return list(
        db.changes()
        .find(query)
        .sort("detected_at", -1)
    )


def gather_analyses(days: int, competitor_id: str | None = None) -> list[dict]:
    """Gather all analyses from the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {"generated_at": {"$gte": cutoff}}
    if competitor_id:
        query["competitor_id"] = competitor_id
    return list(
        db.analyses()
        .find(query)
        .sort("generated_at", -1)
    )


def gather_partnerships(days: int, competitor_id: str | None = None) -> list[dict]:
    """Gather partnerships discovered in the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {"discovered_at": {"$gte": cutoff}}
    if competitor_id:
        query["competitor_id"] = competitor_id
    return list(
        db.partnerships()
        .find(query)
        .sort("discovered_at", -1)
    )


def gather_alerts(days: int, competitor_id: str | None = None) -> list[dict]:
    """Gather alerts sent in the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {"sent_at": {"$gte": cutoff}}
    if competitor_id:
        query["competitor_id"] = competitor_id
    return list(
        db.alerts()
        .find(query)
        .sort("sent_at", -1)
    )


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------

def build_report(days: int, competitor_id: str | None = None) -> dict:
    """Build a structured report dict."""
    changes = gather_changes(days, competitor_id)
    analyses_list = gather_analyses(days, competitor_id)
    partnerships_list = gather_partnerships(days, competitor_id)
    alerts_list = gather_alerts(days, competitor_id)

    # Group changes by competitor
    changes_by_competitor: dict[str, list[dict]] = {}
    for c in changes:
        cid = c.get("competitor_id", "unknown")
        changes_by_competitor.setdefault(cid, []).append(c)

    # Resolve competitor names
    competitor_names: dict[str, str] = {}
    for cid in changes_by_competitor:
        comp = db.get_competitor_by_id(cid)
        competitor_names[cid] = comp["name"] if comp else "Unknown"

    # Severity breakdown
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for c in changes:
        sev = c.get("severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Collect all actionable insights from analyses
    all_insights = []
    for a in analyses_list:
        content = a.get("content", {})
        insights = content.get("actionable_insights", [])
        all_insights.extend(insights)

    # Build competitor sections
    competitor_sections = []
    for cid, comp_changes in changes_by_competitor.items():
        # Sort by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        comp_changes.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))

        section = {
            "competitor_name": competitor_names.get(cid, "Unknown"),
            "total_changes": len(comp_changes),
            "critical_changes": sum(1 for c in comp_changes if c.get("severity") == "critical"),
            "high_changes": sum(1 for c in comp_changes if c.get("severity") == "high"),
            "changes": [
                {
                    "change_type": c.get("change_type", ""),
                    "severity": c.get("severity", ""),
                    "summary": c.get("summary", ""),
                    "detected_at": str(c.get("detected_at", "")),
                }
                for c in comp_changes[:10]  # Top 10 changes per competitor
            ],
        }

        # Add partnerships for this competitor
        comp_partnerships = [p for p in partnerships_list if p.get("competitor_id") == cid]
        if comp_partnerships:
            section["partnerships"] = [
                {
                    "partner_name": p.get("partner_name", ""),
                    "partnership_type": p.get("partnership_type", ""),
                    "confidence": p.get("confidence", 0),
                    "status": p.get("status", ""),
                }
                for p in comp_partnerships
            ]

        competitor_sections.append(section)

    # Sort sections: competitors with most critical/high changes first
    competitor_sections.sort(
        key=lambda s: (s["critical_changes"], s["high_changes"], s["total_changes"]),
        reverse=True,
    )

    period_label = f"Last {days} days"
    now = datetime.now(timezone.utc)

    report = {
        "report_type": "competitive_intelligence",
        "period": period_label,
        "generated_at": now.isoformat(),
        "date_range": {
            "from": (now - timedelta(days=days)).isoformat(),
            "to": now.isoformat(),
        },
        "summary": {
            "total_changes": len(changes),
            "total_analyses": len(analyses_list),
            "total_partnerships_discovered": len(partnerships_list),
            "total_alerts_sent": len(alerts_list),
            "severity_breakdown": severity_counts,
        },
        "competitors": competitor_sections,
        "top_actionable_insights": all_insights[:15],
    }

    # Add LLM-powered executive summary and strategic analysis
    if llm.is_available():
        try:
            strategic = analyze_market_trends(days=days)
            if strategic.get("strategic_analysis"):
                report["strategic_analysis"] = strategic["strategic_analysis"]
            if strategic.get("correlations"):
                report["market_correlations"] = strategic["correlations"]
        except Exception:
            pass

        exec_summary = generate_executive_summary(report)
        if exec_summary:
            report["executive_summary"] = exec_summary

    return report


def generate_executive_summary(report_data: dict) -> str | None:
    """Generate an LLM-powered executive briefing narrative."""
    if not llm.is_available():
        return None

    prompt = """You are a Chief Strategy Officer writing a weekly competitive intelligence briefing for the executive team.

Write a 300-500 word executive summary in clear, direct prose. Structure it as:
1. **Opening headline** — the single most important competitive development
2. **Key movements** — 2-3 paragraphs covering the most significant changes
3. **Market context** — what these changes mean for the broader market
4. **Recommended actions** — 3-5 specific things we should do this week

Be specific: use competitor names, numbers, percentages. No fluff or jargon.
Return plain text (not JSON)."""

    # Build context from report data
    changes_summary = []
    for comp in report_data.get("competitors", []):
        name = comp.get("competitor_name", "Unknown")
        for c in comp.get("changes", [])[:5]:
            changes_summary.append(f"[{c['severity'].upper()}] {name}: {c['summary']}")

    strategic = report_data.get("strategic_analysis", {})
    correlations = report_data.get("market_correlations", [])

    context = f"""PERIOD: {report_data.get('period', 'Last 7 days')}
TOTAL CHANGES: {report_data['summary']['total_changes']}
SEVERITY: {json.dumps(report_data['summary']['severity_breakdown'])}

KEY CHANGES:
{chr(10).join(changes_summary[:15])}

MARKET PATTERNS:
{json.dumps(correlations[:5], indent=2, default=str) if correlations else 'No cross-competitor patterns detected'}

STRATEGIC ANALYSIS:
{json.dumps(strategic, indent=2, default=str)[:1500] if strategic else 'Not available'}"""

    return llm.generate(prompt, context, max_tokens=1000)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_markdown(report: dict) -> str:
    """Format report as Markdown."""
    lines = []
    lines.append(f"# Competitive Intelligence Report")
    lines.append(f"**Period:** {report['period']} | **Generated:** {report['generated_at'][:10]}")
    lines.append("")

    s = report["summary"]
    lines.append("## Summary")
    lines.append(f"- **{s['total_changes']}** changes detected across **{len(report['competitors'])}** competitors")
    lines.append(f"- **{s['severity_breakdown']['critical']}** critical, **{s['severity_breakdown']['high']}** high severity")
    lines.append(f"- **{s['total_partnerships_discovered']}** new partnerships discovered")
    lines.append(f"- **{s['total_alerts_sent']}** alerts sent")
    lines.append("")

    # LLM-generated executive summary
    if report.get("executive_summary"):
        lines.append("## Executive Briefing")
        lines.append(report["executive_summary"])
        lines.append("")

    for section in report["competitors"]:
        lines.append(f"## {section['competitor_name']}")
        lines.append(f"**{section['total_changes']} changes** ({section['critical_changes']} critical, {section['high_changes']} high)")
        lines.append("")

        for change in section["changes"]:
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(change["severity"], "⚪")
            lines.append(f"- {severity_icon} **[{change['severity'].upper()}]** {change['summary']}")

        if section.get("partnerships"):
            lines.append("")
            lines.append("**Partnerships:**")
            for p in section["partnerships"]:
                status_icon = "✅" if p["status"] == "confirmed" else "❓"
                lines.append(f"- {status_icon} {p['partner_name']} ({p['partnership_type']}) — confidence: {p['confidence']}")

        lines.append("")

    if report["top_actionable_insights"]:
        lines.append("## Recommended Actions")
        for i, insight in enumerate(report["top_actionable_insights"], 1):
            lines.append(f"{i}. {insight}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Competitor Monitoring Agent*")
    return "\n".join(lines)


def format_html(report: dict) -> str:
    """Format report as HTML email body."""
    md = format_markdown(report)
    # Simple markdown-to-HTML conversion for email
    html = "<html><body style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;'>"
    for line in md.split("\n"):
        if line.startswith("# "):
            html += f"<h1 style='color: #1a1a2e;'>{line[2:]}</h1>"
        elif line.startswith("## "):
            html += f"<h2 style='color: #16213e; border-bottom: 1px solid #e0e0e0; padding-bottom: 5px;'>{line[3:]}</h2>"
        elif line.startswith("- "):
            html += f"<li style='margin: 4px 0;'>{line[2:]}</li>"
        elif line.startswith("**"):
            html += f"<p><strong>{line}</strong></p>"
        elif line.strip().startswith(tuple("0123456789")):
            html += f"<li style='margin: 4px 0;'>{line.lstrip('0123456789. ')}</li>"
        elif line.startswith("---"):
            html += "<hr style='border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;'>"
        elif line.startswith("*") and line.endswith("*"):
            html += f"<p style='color: #888; font-size: 12px;'>{line.strip('*')}</p>"
        elif line.strip():
            html += f"<p>{line}</p>"
    html += "</body></html>"
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate competitive intelligence report")
    period = parser.add_mutually_exclusive_group(required=True)
    period.add_argument("--weekly", action="store_true", help="Last 7 days")
    period.add_argument("--monthly", action="store_true", help="Last 30 days")
    period.add_argument("--days", type=int, help="Custom number of days")
    parser.add_argument("--competitor", help="Filter by competitor slug")
    parser.add_argument("--format", choices=["json", "markdown", "html"], default="markdown")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    days = 7 if args.weekly else (30 if args.monthly else args.days)
    competitor_id = None

    if args.competitor:
        comp = db.get_competitor_by_slug(args.competitor)
        if not comp:
            print(f"Competitor not found: {args.competitor}", file=sys.stderr)
            sys.exit(1)
        competitor_id = comp["_id"]

    try:
        report = build_report(days, competitor_id)

        if args.format == "json":
            output = json.dumps(report, indent=2, default=str)
        elif args.format == "html":
            output = format_html(report)
        else:
            output = format_markdown(report)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(output)

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
