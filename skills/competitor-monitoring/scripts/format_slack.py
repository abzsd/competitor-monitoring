#!/usr/bin/env python3
"""Format alerts and reports as Slack Block Kit messages.

Usage:
    python3 format_slack.py --change '<change_json>'           # Format a single change alert
    python3 format_slack.py --analysis '<analysis_json>'       # Format an analysis
    python3 format_slack.py --report '<report_json>'           # Format a summary report
    python3 format_slack.py --send --webhook-url <url>         # Also send to Slack

Output:
    JSON Slack Block Kit payload ready to POST to a webhook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# Slack Block Kit builders
# ---------------------------------------------------------------------------

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "⚪",
}


def _header_block(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text[:150]}}


def _section_block(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}}


def _divider_block() -> dict:
    return {"type": "divider"}


def _context_block(texts: list[str]) -> dict:
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": t[:500]} for t in texts[:10]],
    }


def _fields_section(fields: list[tuple[str, str]]) -> dict:
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*{label}*\n{value}"}
            for label, value in fields[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Change alert formatting
# ---------------------------------------------------------------------------

def format_change_alert(change: dict) -> dict:
    """Format a detected change as a Slack Block Kit message."""
    severity = change.get("severity", "low")
    emoji = SEVERITY_EMOJI.get(severity, "⚪")
    competitor = change.get("competitor", change.get("competitor_slug", "Unknown"))
    change_type = change.get("change_type", "content_update").replace("_", " ").title()

    blocks = [
        _header_block(f"{emoji} {change_type}: {competitor}"),
        _fields_section([
            ("Severity", severity.upper()),
            ("Type", change_type),
            ("Source", change.get("source_url", "N/A")),
            ("Detected", str(change.get("detected_at", "N/A"))[:19]),
        ]),
        _section_block(f"*Summary:* {change.get('summary', 'No summary available')}"),
    ]

    # Add diff preview (truncated)
    diff = change.get("text_diff", "")
    if diff:
        # Show first few meaningful diff lines
        diff_lines = [
            l for l in diff.splitlines()
            if l.startswith("+") or l.startswith("-")
        ][:10]
        if diff_lines:
            diff_preview = "\n".join(diff_lines)
            blocks.append(_section_block(f"```{diff_preview}```"))

    # Structured diff highlights
    struct_diff = change.get("structured_diff", {})
    if struct_diff.get("changed"):
        changes_text = "\n".join(
            f"• `{c['path']}`: {c.get('old_value', '?')} → {c.get('new_value', '?')}"
            for c in struct_diff["changed"][:5]
        )
        blocks.append(_section_block(f"*Key Changes:*\n{changes_text}"))

    blocks.append(_divider_block())
    blocks.append(_context_block(["Competitor Monitoring Agent"]))

    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Rich change alert formatting (with deep insights)
# ---------------------------------------------------------------------------

PRIORITY_EMOJI = {"high": ":red_circle:", "medium": ":large_orange_circle:", "low": ":white_circle:"}
SIGNAL_EMOJI = {
    "funding": ":moneybag:",
    "product_launch": ":rocket:",
    "partnership": ":handshake:",
    "hiring": ":busts_in_silhouette:",
    "positioning": ":dart:",
}


def format_change_alert_rich(change: dict, insights: dict) -> dict:
    """Format a detected change + deep insights as a rich Slack Block Kit message."""
    severity = change.get("severity", "low")
    emoji = SEVERITY_EMOJI.get(severity, "\u26aa")
    competitor = change.get("competitor", change.get("competitor_slug", "Unknown"))
    change_type = change.get("change_type", "content_update").replace("_", " ").title()

    blocks = []

    # 1. Header
    blocks.append(_header_block(f"{emoji} {change_type}: {competitor}"))

    # 2. Metadata
    blocks.append(_fields_section([
        ("Severity", severity.upper()),
        ("Type", change_type),
        ("Source", change.get("source_url", "N/A")),
        ("Detected", str(change.get("detected_at", "N/A"))[:19]),
    ]))
    blocks.append(_divider_block())

    # 3. What Changed
    ba_summary = insights.get("before_after_summary", "")
    ba_details = insights.get("before_after_details", [])
    what_text = "*What Changed*"
    if ba_summary:
        what_text += f"\n{ba_summary}"
    if ba_details:
        what_text += "\n" + "\n".join(f"  {d}" for d in ba_details[:12])
    blocks.append(_section_block(what_text))

    # 4. Plan-by-Plan Comparison (pricing)
    plan_comparisons = insights.get("plan_comparisons", [])
    if plan_comparisons:
        plan_lines = ["*Plan-by-Plan Comparison*"]
        for pc in plan_comparisons:
            pct = pc.get("price_change_pct")
            pct_str = ""
            if pct is not None:
                sign = "+" if pct > 0 else ""
                pct_str = f" ({sign}{pct:.1f}%)"
                if pct > 20:
                    pct_str += " :warning:"
            plan_lines.append(f"\n>*{pc['plan_name']}*: {pc.get('old_price', '?')} \u2192 {pc.get('new_price', '?')}{pct_str}")
            for f in pc.get("features_added", [])[:5]:
                plan_lines.append(f">     :heavy_plus_sign: {f}")
            for f in pc.get("features_removed", [])[:5]:
                plan_lines.append(f">     :heavy_minus_sign: ~{f}~")
        blocks.append(_section_block("\n".join(plan_lines)))

        # Trial/billing notes
        notes = []
        for pc in plan_comparisons:
            notes.extend(pc.get("notes", []))
        if notes:
            blocks.append(_context_block([f":warning: {n}" for n in notes[:5]]))

    # New/removed plans
    new_plans = insights.get("new_plans", [])
    removed_plans = insights.get("removed_plans", [])
    if new_plans:
        blocks.append(_section_block("*New Plans Added:* " + ", ".join(f"`{p.get('name', '?')}` at {p.get('price', '?')}" for p in new_plans)))
    if removed_plans:
        blocks.append(_section_block("*Plans Removed:* " + ", ".join(f"~{p.get('name', '?')}~" for p in removed_plans)))

    blocks.append(_divider_block())

    # 5. Impact Analysis
    impact_headline = insights.get("impact_headline", "")
    impact_details = insights.get("impact_details", [])
    if impact_headline or impact_details:
        impact_text = "*Impact Analysis*"
        if impact_headline:
            impact_text += f"\n*{impact_headline}*"
        for d in impact_details[:6]:
            impact_text += f"\n  \u2022 {d}"
        affected = insights.get("affected_workflows", [])
        if affected:
            impact_text += f"\n\n:gear: *Affected Workflows:* {', '.join(affected)}"
        blocks.append(_section_block(impact_text))
        blocks.append(_divider_block())

    # 6. Poachable Ideas
    poachable = insights.get("poachable_ideas", [])
    if poachable:
        poach_text = "*What to Poach / Adopt*\n" + "\n".join(f"  :arrow_right: {idea}" for idea in poachable[:5])
        blocks.append(_section_block(poach_text))

    # 7. Recommended Actions
    actions = insights.get("actions", [])
    if actions:
        actions_text = "*Recommended Actions*"
        for a in actions[:6]:
            priority = a.get("priority", "medium")
            p_emoji = PRIORITY_EMOJI.get(priority, ":white_circle:")
            team = a.get("team", "")
            team_str = f" \u2014 _{team.title()}_" if team else ""
            actions_text += f"\n  {p_emoji} *[{priority.upper()}]* {a.get('action', '')}{team_str}"
        blocks.append(_section_block(actions_text))

    # 8. Signals (content/blog)
    signals = insights.get("signals", [])
    if signals:
        sig_text = "*Signals Detected*"
        for s in signals[:6]:
            s_emoji = SIGNAL_EMOJI.get(s.get("type", ""), ":mag:")
            sig_text += f"\n  {s_emoji} *{s.get('type', 'Signal').replace('_', ' ').title()}:* {s.get('detail', '')}"
        blocks.append(_section_block(sig_text))

    # 9. Footer
    blocks.append(_divider_block())
    blocks.append(_context_block(["Competitor Monitoring Agent \u2022 Deep Analysis"]))

    # Slack has a 50-block limit — trim if needed
    if len(blocks) > 50:
        blocks = blocks[:49] + [_context_block(["(Message trimmed due to Slack block limit)"])]

    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Analysis formatting
# ---------------------------------------------------------------------------

def format_analysis_alert(analysis: dict) -> dict:
    """Format an analysis as a Slack Block Kit message."""
    content = analysis.get("content", analysis)

    blocks = [
        _header_block("📊 Competitive Analysis"),
        _section_block(f"*Summary:* {content.get('summary', 'N/A')}"),
        _section_block(f"*Impact:* {content.get('impact_assessment', 'N/A')}"),
    ]

    insights = content.get("actionable_insights", [])
    if insights:
        insights_text = "\n".join(f"→ {i}" for i in insights)
        blocks.append(_section_block(f"*Recommended Actions:*\n{insights_text}"))

    confidence = content.get("confidence", 0)
    category = content.get("category", "other")
    blocks.append(_context_block([
        f"Category: {category}",
        f"Confidence: {confidence:.0%}",
    ]))

    blocks.append(_divider_block())
    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report_summary(report: dict) -> dict:
    """Format a periodic report as a Slack Block Kit message."""
    summary = report.get("summary", {})
    severity = summary.get("severity_breakdown", {})

    blocks = [
        _header_block(f"📋 Competitive Intelligence Report — {report.get('period', '')}"),
        _fields_section([
            ("Total Changes", str(summary.get("total_changes", 0))),
            ("Critical", f"🔴 {severity.get('critical', 0)}"),
            ("High", f"🟠 {severity.get('high', 0)}"),
            ("Partnerships Found", str(summary.get("total_partnerships_discovered", 0))),
        ]),
        _divider_block(),
    ]

    # Executive summary (LLM-generated)
    exec_summary = report.get("executive_summary", "")
    if exec_summary:
        # Truncate for Slack's 3000 char limit per block
        summary_text = exec_summary[:2900] + "..." if len(exec_summary) > 2900 else exec_summary
        blocks.append(_section_block(f"*Executive Briefing:*\n{summary_text}"))
        blocks.append(_divider_block())

    # Per-competitor summaries
    for section in report.get("competitors", [])[:5]:
        name = section.get("competitor_name", "Unknown")
        total = section.get("total_changes", 0)
        critical = section.get("critical_changes", 0)
        high = section.get("high_changes", 0)

        blocks.append(_section_block(
            f"*{name}* — {total} changes ({critical} critical, {high} high)"
        ))

        # Top changes
        top_changes = section.get("changes", [])[:3]
        if top_changes:
            lines = []
            for c in top_changes:
                emoji = SEVERITY_EMOJI.get(c.get("severity", "low"), "⚪")
                lines.append(f"{emoji} {c.get('summary', 'N/A')}")
            blocks.append(_section_block("\n".join(lines)))

        # Partnerships
        partnerships = section.get("partnerships", [])
        if partnerships:
            p_text = ", ".join(f"{p['partner_name']} ({p['partnership_type']})" for p in partnerships[:5])
            blocks.append(_context_block([f"🤝 Partnerships: {p_text}"]))

    # Top actions
    insights = report.get("top_actionable_insights", [])[:5]
    if insights:
        blocks.append(_divider_block())
        blocks.append(_section_block("*Top Recommended Actions:*"))
        for i, insight in enumerate(insights, 1):
            blocks.append(_section_block(f"{i}. {insight}"))

    blocks.append(_divider_block())
    blocks.append(_context_block(["Generated by Competitor Monitoring Agent"]))

    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Slack sending
# ---------------------------------------------------------------------------

def send_to_slack(payload: dict, webhook_url: str | None = None) -> dict:
    """POST a Block Kit payload to a Slack webhook."""
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        return {"status": "failed", "error": "No SLACK_WEBHOOK_URL configured"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text == "ok":
            return {"status": "sent"}
        return {"status": "failed", "error": f"Slack returned {resp.status_code}: {resp.text}"}
    except requests.RequestException as e:
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Format Slack Block Kit messages")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--change", help="Change JSON to format (basic)")
    input_group.add_argument("--rich-change", help="Rich change JSON {change, insights} for deep analysis")
    input_group.add_argument("--analysis", help="Analysis JSON to format")
    input_group.add_argument("--report", help="Report JSON to format")
    parser.add_argument("--send", action="store_true", help="Also send to Slack")
    parser.add_argument("--webhook-url", help="Override SLACK_WEBHOOK_URL")
    args = parser.parse_args()

    try:
        if args.change:
            data = json.loads(args.change)
            payload = format_change_alert(data)
        elif args.rich_change:
            data = json.loads(args.rich_change)
            payload = format_change_alert_rich(data["change"], data["insights"])
        elif args.analysis:
            data = json.loads(args.analysis)
            payload = format_analysis_alert(data)
        elif args.report:
            data = json.loads(args.report)
            payload = format_report_summary(data)
        else:
            sys.exit(1)

        print(json.dumps(payload, indent=2))

        if args.send:
            result = send_to_slack(payload, args.webhook_url)
            print(json.dumps(result), file=sys.stderr)
            if result["status"] == "failed":
                sys.exit(1)

    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
