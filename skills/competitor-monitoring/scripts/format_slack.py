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
    "critical": ":rotating_light:",
    "high": ":large_orange_diamond:",
    "medium": ":small_orange_diamond:",
    "low": ":white_small_square:",
}

SEVERITY_COLOR = {
    "critical": "#E01E5A",
    "high": "#E87722",
    "medium": "#ECB22E",
    "low": "#CCCCCC",
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
# Path & value humanizers — turn raw JSON paths into plain English
# ---------------------------------------------------------------------------

_PATH_LABELS = {
    "headings": "Heading",
    "sections": "Section",
    "features": "Feature",
    "stats": "Statistic",
    "links": "Link",
    "meta": "Page Info",
    "images": "Image",
    "buttons": "Button",
    "navigation": "Navigation",
    "pricing": "Pricing",
    "plans": "Plan",
    "testimonials": "Testimonial",
}


def _humanize_path(path: str) -> str:
    """Convert root['sections'][3]['summary'] → 'Section summary'."""
    import re
    # Extract component names from the path
    parts = re.findall(r"\['?(\w+)'?\]", path)
    if not parts:
        return "Content"

    # Skip 'root' prefix
    parts = [p for p in parts if p != "root"]
    if not parts:
        return "Content"

    # Map first meaningful part to a readable label
    label = _PATH_LABELS.get(parts[0], parts[0].replace("_", " ").title())

    # If there's a sub-field like 'text', 'summary', 'heading', append it
    sub_fields = [p for p in parts[1:] if not p.isdigit()]
    if sub_fields:
        last = sub_fields[-1].replace("_", " ")
        if last not in label.lower():
            label = f"{label} {last}"

    return label


def _clean_summary(summary: str) -> str:
    """Remove raw path references from summaries (e.g. 'sections > summary: ...')."""
    import re
    # Remove field prefixes like "sections > summary: " or "headings > text: "
    cleaned = re.sub(r"\b\w+ > \w+:\s*", "", summary)
    # Collapse multiple semicolons into a cleaner separator
    cleaned = re.sub(r"\s*;\s*", ". ", cleaned)
    # Remove duplicate periods
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    return cleaned.strip()


def _humanize_value(val) -> str:
    """Clean up raw values — extract text from dict-like strings."""
    s = str(val).strip()
    # Handle stringified dicts like "{'level': 'h3', 'text': '12'}"
    if s.startswith("{") and "'text'" in s:
        import re
        m = re.search(r"'text'\s*:\s*'([^']*)'", s)
        if m:
            return m.group(1)
    if s.startswith("{") and "'value'" in s:
        import re
        m = re.search(r"'value'\s*:\s*'([^']*)'", s)
        if m:
            extracted = m.group(1)
            ctx = re.search(r"'context'\s*:\s*'([^']*)'", s)
            if ctx:
                return f"{extracted} ({ctx.group(1)})"
            return extracted
    # Truncate long values
    if len(s) > 120:
        return s[:117] + "..."
    return s


# ---------------------------------------------------------------------------
# Change alert formatting
# ---------------------------------------------------------------------------

def format_change_alert(change: dict) -> dict:
    """Format a detected change as a Slack Block Kit message with colored sidebar."""
    severity = change.get("severity", "low")
    emoji = SEVERITY_EMOJI.get(severity, ":white_small_square:")
    color = SEVERITY_COLOR.get(severity, "#CCCCCC")
    competitor = change.get("competitor", change.get("competitor_slug", "Unknown"))
    change_type = change.get("change_type", "content_update").replace("_", " ").title()
    url = change.get("source_url", "N/A")

    blocks = [
        _header_block(f"{emoji}  {change_type} — {competitor}"),
        _section_block(" "),
        _fields_section([
            (":bar_chart:  Severity", f"*{severity.upper()}*"),
            (":label:  Type", change_type),
            (":link:  Source", f"<{url}|View Page>" if url != "N/A" else "N/A"),
            (":clock1:  Detected", str(change.get("detected_at", "N/A"))[:19]),
        ]),
        _divider_block(),
        _section_block(f":memo:  *Summary*\n\n{_clean_summary(change.get('summary', 'No summary available'))}"),
    ]

    # Structured diff highlights — human-readable
    struct_diff = change.get("structured_diff", {})
    if struct_diff.get("changed"):
        blocks.append(_divider_block())
        changes_text = ":pushpin:  *Key Changes*\n"
        for c in struct_diff["changed"][:6]:
            label = _humanize_path(c.get("path", ""))
            old_v = _humanize_value(c.get("old_value", ""))
            new_v = _humanize_value(c.get("new_value", ""))
            changes_text += f"\n>  :small_blue_diamond:  *{label}*\n>  _{old_v}_  →  *{new_v}*\n"
        blocks.append(_section_block(changes_text))

    blocks.append(_section_block(" "))
    blocks.append(_divider_block())
    blocks.append(_context_block([":robot_face:  Competitor Monitoring Agent  •  Automated Detection"]))

    return {"attachments": [{"color": color, "blocks": blocks}]}


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
    "pricing": ":money_with_wings:",
}


def format_change_alert_rich(change: dict, insights: dict) -> dict:
    """Format a detected change + deep insights as a rich Slack Block Kit message."""
    severity = change.get("severity", "low")
    emoji = SEVERITY_EMOJI.get(severity, ":white_small_square:")
    color = SEVERITY_COLOR.get(severity, "#CCCCCC")
    competitor = change.get("competitor", change.get("competitor_slug", "Unknown"))
    change_type = change.get("change_type", "content_update").replace("_", " ").title()
    url = change.get("source_url", "N/A")

    blocks = []

    # ━━━ HEADER ━━━
    blocks.append(_header_block(f"{emoji}  {change_type} — {competitor}"))
    blocks.append(_section_block(" "))
    blocks.append(_fields_section([
        (":bar_chart:  Severity", f"*{severity.upper()}*"),
        (":label:  Type", change_type),
        (":link:  Source", f"<{url}|View Page>" if url != "N/A" else "N/A"),
        (":clock1:  Detected", str(change.get("detected_at", "N/A"))[:19]),
    ]))

    # ━━━ WHAT CHANGED ━━━
    blocks.append(_divider_block())
    ba_summary = insights.get("before_after_summary", "")
    ba_details = insights.get("before_after_details", [])
    what_text = ":memo:  *What Changed*\n"
    if ba_summary:
        what_text += f"\n{ba_summary}\n"
    if ba_details:
        what_text += "\n" + "\n".join(f"    •  {d}" for d in ba_details[:12])
    blocks.append(_section_block(what_text))

    # ━━━ PLAN-BY-PLAN COMPARISON (pricing) ━━━
    plan_comparisons = insights.get("plan_comparisons", [])
    if plan_comparisons:
        blocks.append(_divider_block())
        plan_lines = [":money_with_wings:  *Plan-by-Plan Comparison*\n"]
        for pc in plan_comparisons:
            pct = pc.get("price_change_pct")
            pct_str = ""
            if pct is not None:
                sign = "+" if pct > 0 else ""
                pct_str = f"  `{sign}{pct:.1f}%`"
                if pct > 20:
                    pct_str += "  :warning:"
            plan_lines.append(f">  *{pc['plan_name']}*\n>  {pc.get('old_price', '?')}  \u2192  {pc.get('new_price', '?')}{pct_str}")
            for f in pc.get("features_added", [])[:5]:
                plan_lines.append(f">      :heavy_plus_sign:  {f}")
            for f in pc.get("features_removed", [])[:5]:
                plan_lines.append(f">      :heavy_minus_sign:  ~{f}~")
            plan_lines.append(">")
        blocks.append(_section_block("\n".join(plan_lines)))

        # Trial/billing notes
        notes = []
        for pc in plan_comparisons:
            notes.extend(pc.get("notes", []))
        if notes:
            blocks.append(_context_block([f":warning:  {n}" for n in notes[:5]]))

    # New/removed plans
    new_plans = insights.get("new_plans", [])
    removed_plans = insights.get("removed_plans", [])
    if new_plans:
        blocks.append(_section_block(":new:  *New Plans Added*\n\n" + "\n".join(f"    •  `{p.get('name', '?')}`  at  {p.get('price', '?')}" for p in new_plans)))
    if removed_plans:
        blocks.append(_section_block(":x:  *Plans Removed*\n\n" + "\n".join(f"    •  ~{p.get('name', '?')}~" for p in removed_plans)))

    # ━━━ SIGNALS DETECTED ━━━
    signals = insights.get("signals", [])
    if signals:
        blocks.append(_divider_block())
        sig_lines = [":satellite_antenna:  *Signals Detected*\n"]
        for s in signals[:6]:
            s_emoji = SIGNAL_EMOJI.get(s.get("type", ""), ":mag:")
            sig_lines.append(f"    {s_emoji}  *{s.get('type', 'Signal').replace('_', ' ').title()}*  —  {s.get('detail', '')}")
        blocks.append(_section_block("\n".join(sig_lines)))

    # ━━━ IMPACT ANALYSIS ━━━
    impact_headline = insights.get("impact_headline", "")
    impact_details = insights.get("impact_details", [])
    if impact_headline or impact_details:
        blocks.append(_divider_block())
        impact_text = ":chart_with_upwards_trend:  *Impact Analysis*\n"
        if impact_headline:
            impact_text += f"\n>  _{impact_headline}_\n"
        for d in impact_details[:6]:
            impact_text += f"\n    \u2022  {d}"
        affected = insights.get("affected_workflows", [])
        if affected:
            impact_text += f"\n\n    :gear:  *Affected Workflows:*  {', '.join(affected)}"
        blocks.append(_section_block(impact_text))

    # ━━━ POACHABLE IDEAS ━━━
    poachable = insights.get("poachable_ideas", [])
    if poachable:
        blocks.append(_divider_block())
        poach_text = ":bulb:  *Ideas to Adopt*\n\n" + "\n".join(f"    :arrow_right:  {idea}" for idea in poachable[:5])
        blocks.append(_section_block(poach_text))

    # ━━━ RECOMMENDED ACTIONS ━━━
    actions = insights.get("actions", [])
    if actions:
        blocks.append(_divider_block())
        actions_text = ":pushpin:  *Recommended Actions*\n"
        for a in actions[:6]:
            priority = a.get("priority", "medium")
            p_emoji = PRIORITY_EMOJI.get(priority, ":white_circle:")
            team = a.get("team", "")
            team_str = f"  \u2014  _{team.title()}_" if team else ""
            actions_text += f"\n    {p_emoji}  *[{priority.upper()}]*  {a.get('action', '')}{team_str}"
        blocks.append(_section_block(actions_text))

    # ━━━ NEWS & MARKET INTELLIGENCE ━━━
    news_items = insights.get("news_context", [])
    if news_items:
        blocks.append(_divider_block())
        news_text = ":newspaper:  *Market Intelligence (from web search)*\n"
        for n in news_items[:4]:
            source = n.get("source", "")
            title = n.get("title", "")[:100]
            url = n.get("url", "")
            snippet = n.get("snippet", "")[:120]
            if url and title:
                news_text += f"\n>  :link:  <{url}|{title}>"
                if source:
                    news_text += f"  _({source})_"
                if snippet:
                    news_text += f"\n>  {snippet}"
                news_text += "\n"
        blocks.append(_section_block(news_text))

    # ━━━ FOOTER ━━━
    blocks.append(_section_block(" "))
    blocks.append(_divider_block())
    blocks.append(_context_block([":robot_face:  Competitor Monitoring Agent  •  Deep Analysis  •  Powered by AI + Web Search"]))

    # Slack has a 50-block limit — trim if needed
    if len(blocks) > 50:
        blocks = blocks[:49] + [_context_block(["(Message trimmed due to Slack block limit)"])]

    return {"attachments": [{"color": color, "blocks": blocks}]}


# ---------------------------------------------------------------------------
# Analysis formatting
# ---------------------------------------------------------------------------

def format_analysis_alert(analysis: dict) -> dict:
    """Format an analysis as a Slack Block Kit message with visual hierarchy."""
    content = analysis.get("content", analysis)
    category = content.get("category", "other").replace("_", " ").title()
    confidence = content.get("confidence", 0)

    blocks = [
        _header_block(f":bar_chart:  Competitive Analysis  —  {category}"),
        _section_block(" "),
        _section_block(f":memo:  *Summary*\n\n{content.get('summary', 'N/A')}"),
        _divider_block(),
        _section_block(f":chart_with_upwards_trend:  *Impact Assessment*\n\n{content.get('impact_assessment', 'N/A')}"),
    ]

    insights = content.get("actionable_insights", [])
    if insights:
        blocks.append(_divider_block())
        insights_text = "\n".join(f"    :arrow_right:  {i}" for i in insights)
        blocks.append(_section_block(f":pushpin:  *Recommended Actions*\n\n{insights_text}"))

    blocks.append(_section_block(" "))
    blocks.append(_divider_block())
    blocks.append(_context_block([
        f":label:  Category: {category}",
        f":dart:  Confidence: {confidence:.0%}",
        ":robot_face:  Competitor Monitoring Agent",
    ]))

    return {"attachments": [{"color": "#36C5F0", "blocks": blocks}]}


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report_summary(report: dict) -> dict:
    """Format a periodic report as a clean Slack dashboard."""
    summary = report.get("summary", {})
    sev = summary.get("severity_breakdown", {})
    period = report.get("period", "Weekly")

    blocks = [
        _header_block(f":clipboard:  Competitive Intelligence Report  —  {period}"),
        _section_block(" "),
    ]

    # ━━━ STATS DASHBOARD ━━━
    total = summary.get("total_changes", 0)
    partnerships = summary.get("total_partnerships_discovered", 0)
    blocks.append(_fields_section([
        (":rotating_light:  Critical", f"*{sev.get('critical', 0)}*"),
        (":large_orange_diamond:  High", f"*{sev.get('high', 0)}*"),
        (":small_orange_diamond:  Medium", f"*{sev.get('medium', 0)}*"),
        (":bar_chart:  Total Changes", f"*{total}*"),
    ]))

    if partnerships:
        blocks.append(_context_block([f":handshake:  {partnerships} new partnerships discovered"]))

    # ━━━ EXECUTIVE BRIEFING ━━━
    exec_summary = report.get("executive_summary", "")
    if exec_summary:
        blocks.append(_divider_block())
        summary_text = exec_summary[:2900] + "..." if len(exec_summary) > 2900 else exec_summary
        blocks.append(_section_block(f":speech_balloon:  *Executive Briefing*\n\n{summary_text}"))

    # ━━━ PER-COMPETITOR BREAKDOWN ━━━
    for section in report.get("competitors", [])[:5]:
        name = section.get("competitor_name", "Unknown")
        total_c = section.get("total_changes", 0)
        critical = section.get("critical_changes", 0)
        high = section.get("high_changes", 0)

        blocks.append(_divider_block())

        # Competitor header with badge
        badge = ""
        if critical:
            badge = f"  :rotating_light: {critical} critical"
        elif high:
            badge = f"  :large_orange_diamond: {high} high"
        blocks.append(_section_block(f":globe_with_meridians:  *{name}*  —  {total_c} changes{badge}"))

        # Top changes
        top_changes = section.get("changes", [])[:3]
        if top_changes:
            lines = []
            for c in top_changes:
                emoji = SEVERITY_EMOJI.get(c.get("severity", "low"), ":white_small_square:")
                lines.append(f"    {emoji}  {c.get('summary', 'N/A')}")
            blocks.append(_section_block("\n\n".join(lines)))

        # Partnerships
        partnerships_list = section.get("partnerships", [])
        if partnerships_list:
            p_text = ",  ".join(f"*{p['partner_name']}* ({p['partnership_type']})" for p in partnerships_list[:5])
            blocks.append(_context_block([f":handshake:  Partnerships:  {p_text}"]))

    # ━━━ TOP ACTIONS ━━━
    insights = report.get("top_actionable_insights", [])[:5]
    if insights:
        blocks.append(_divider_block())
        action_lines = "\n\n".join(f"    *{i+1}.*  {ins}" for i, ins in enumerate(insights))
        blocks.append(_section_block(f":pushpin:  *Top Recommended Actions*\n\n{action_lines}"))

    # ━━━ FOOTER ━━━
    blocks.append(_section_block(" "))
    blocks.append(_divider_block())
    blocks.append(_context_block([":robot_face:  Generated by Competitor Monitoring Agent  •  Powered by AI"]))

    # Trim to Slack limit
    if len(blocks) > 45:
        blocks = blocks[:44] + [_context_block(["(report trimmed)"])]

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
