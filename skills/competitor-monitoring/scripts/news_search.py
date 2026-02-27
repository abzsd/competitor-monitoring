#!/usr/bin/env python3
"""Proactive web search for competitor news via Tavily API.

Searches for funding, partnerships, product launches, and acquisitions.
Scores relevance with LLM, saves to news_items collection, alerts on high-relevance items.

Usage:
    python3 news_search.py --competitor <slug>
    python3 news_search.py --all
    python3 news_search.py --all --days 14
    python3 news_search.py --all --no-alert

Output:
    JSON array of news items found, with relevance scores.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import llm
import format_slack

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
from dotenv import load_dotenv
load_dotenv(_env_path)

from tavily import TavilyClient

# ---------------------------------------------------------------------------
# Tavily client singleton
# ---------------------------------------------------------------------------

_tavily_client = None


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY not set in environment")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


# ---------------------------------------------------------------------------
# Search query templates
# ---------------------------------------------------------------------------

SEARCH_CATEGORIES = {
    "funding": "{name} funding announcement OR raised OR series",
    "partnership": "{name} partnership OR integration OR collaboration announcement",
    "product_launch": "{name} product launch OR new feature OR announcing",
    "acquisition": "{name} acquisition OR acquired OR merger",
}


# ---------------------------------------------------------------------------
# Core pipeline functions
# ---------------------------------------------------------------------------

def search_competitor_news(competitor_doc: dict, days: int = 7) -> list[dict]:
    """Run multiple Tavily searches for a single competitor.

    Returns list of de-duplicated raw result dicts with metadata.
    """
    name = competitor_doc["name"]
    tavily = _get_tavily()
    seen_urls: set[str] = set()
    all_results = []

    for category, query_template in SEARCH_CATEGORIES.items():
        query = query_template.format(name=name)

        try:
            response = tavily.search(
                query=query,
                search_depth="basic",
                max_results=5,
                days=days,
            )
        except Exception as e:
            print(f"[news_search] Tavily error for '{query}': {e}", file=sys.stderr)
            continue

        for result in response.get("results", []):
            url = result.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            domain = urlparse(url).netloc.replace("www.", "")

            all_results.append({
                "title": result.get("title", ""),
                "url": url,
                "snippet": result.get("content", "")[:500],
                "source_domain": domain,
                "search_query": query,
                "search_category": category,
                "raw_tavily_score": result.get("score", 0.0),
                "published_date": result.get("published_date", ""),
            })

    return all_results


def score_relevance(
    competitor_name: str,
    title: str,
    snippet: str,
    category: str,
) -> dict:
    """Use LLM to score relevance and generate a brief analysis.

    Returns {"relevance_score": float, "analysis": str} or defaults if LLM unavailable.
    """
    if not llm.is_available():
        return {"relevance_score": 0.5, "analysis": "LLM unavailable — manual review recommended"}

    prompt = (
        "You are a competitive intelligence analyst. Score the relevance of this news item "
        "to competitive monitoring. Return a JSON object with:\n"
        '- "relevance_score": float 0.0 to 1.0 (1.0 = extremely relevant competitive intelligence)\n'
        '- "analysis": one sentence explaining why this matters or does not matter\n\n'
        "Score highly if the news involves: concrete funding amounts, named partnership deals, "
        "specific product launches with features, confirmed acquisitions, or executive changes. "
        "Score low if the news is: generic marketing content, opinion pieces without facts, "
        "or only tangentially related to the competitor."
    )

    context = (
        f"Competitor: {competitor_name}\n"
        f"Category: {category}\n"
        f"Headline: {title}\n"
        f"Snippet: {snippet}"
    )

    result = llm.analyze(prompt, context, model=llm.FAST_MODEL, max_tokens=200, temperature=0.2)

    if result and "relevance_score" in result:
        return {
            "relevance_score": max(0.0, min(1.0, float(result["relevance_score"]))),
            "analysis": result.get("analysis", ""),
        }

    return {"relevance_score": 0.5, "analysis": "Scoring failed — manual review recommended"}


def is_duplicate_url(url: str) -> bool:
    """Check if we already have this URL in news_items."""
    return db.news_items().find_one({"url": url}) is not None


def save_news_item(competitor_doc: dict, item: dict, score_result: dict) -> str:
    """Save a single news item to the news_items collection. Returns the document ID."""
    from pymongo.errors import DuplicateKeyError

    now = datetime.now(timezone.utc)
    doc = {
        "_id": str(__import__("bson").ObjectId()),
        "competitor_id": competitor_doc["_id"],
        "competitor_slug": competitor_doc.get("slug", ""),
        "title": item["title"],
        "url": item["url"],
        "snippet": item["snippet"],
        "source_domain": item["source_domain"],
        "search_query": item["search_query"],
        "search_category": item["search_category"],
        "relevance_score": score_result["relevance_score"],
        "llm_analysis": score_result["analysis"],
        "raw_tavily_score": item.get("raw_tavily_score", 0.0),
        "published_date": item.get("published_date", ""),
        "discovered_at": now,
        "is_alerted": False,
        "created_at": now,
    }

    try:
        db.news_items().insert_one(doc)
    except DuplicateKeyError:
        return ""  # already exists

    return doc["_id"]


# ---------------------------------------------------------------------------
# Slack alert for high-relevance news
# ---------------------------------------------------------------------------

def format_news_alert(competitor_name: str, item: dict, score_result: dict) -> dict:
    """Format a high-relevance news item as a Slack Block Kit message."""
    category_emoji = {
        "funding": ":moneybag:",
        "partnership": ":handshake:",
        "product_launch": ":rocket:",
        "acquisition": ":classical_building:",
    }
    emoji = category_emoji.get(item["search_category"], ":newspaper:")
    score = score_result["relevance_score"]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji}  News Alert: {competitor_name}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*:label:  Category*\n{item['search_category'].replace('_', ' ').title()}"},
                {"type": "mrkdwn", "text": f"*:dart:  Relevance*\n{score:.0%}"},
                {"type": "mrkdwn", "text": f"*:link:  Source*\n<{item['url']}|{item['source_domain']}>"},
                {"type": "mrkdwn", "text": f"*:clock1:  Found*\n{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"},
            ],
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f":newspaper:  *{item['title']}*\n\n{item['snippet'][:500]}"}},
    ]

    if score_result.get("analysis"):
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f":mag:  *Analysis*\n\n{score_result['analysis']}"}})

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": " "}})
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": ":robot_face:  Competitor Monitoring Agent  •  News Search  •  Powered by Tavily + AI"}],
    })

    # Color based on relevance score
    if score >= 0.9:
        color = "#E01E5A"  # red — critical intelligence
    elif score >= 0.7:
        color = "#E87722"  # orange — high relevance
    else:
        color = "#ECB22E"  # yellow

    return {"attachments": [{"color": color, "blocks": blocks}]}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_news_search(
    competitor_doc: dict,
    days: int = 7,
    alert_threshold: float = 0.7,
    send_alerts: bool = True,
) -> list[dict]:
    """Full pipeline for one competitor: search -> score -> save -> alert.

    Returns list of processed news item dicts (for JSON output).
    """
    comp_name = competitor_doc["name"]

    print(f"[news_search] Searching news for {comp_name} (last {days} days)...", file=sys.stderr)

    raw_results = search_competitor_news(competitor_doc, days=days)
    print(f"[news_search] Found {len(raw_results)} results for {comp_name}", file=sys.stderr)

    processed = []
    alerted_count = 0

    for item in raw_results:
        # Skip if we already have this URL
        if is_duplicate_url(item["url"]):
            continue

        # Score relevance via LLM
        score_result = score_relevance(
            competitor_name=comp_name,
            title=item["title"],
            snippet=item["snippet"],
            category=item["search_category"],
        )

        # Save to MongoDB
        doc_id = save_news_item(competitor_doc, item, score_result)
        if not doc_id:
            continue  # duplicate

        output_item = {
            **item,
            "news_item_id": doc_id,
            "competitor_name": comp_name,
            "competitor_slug": competitor_doc.get("slug", ""),
            "relevance_score": score_result["relevance_score"],
            "analysis": score_result["analysis"],
        }
        processed.append(output_item)

        # Alert on high-relevance items
        if send_alerts and score_result["relevance_score"] >= alert_threshold:
            payload = format_news_alert(comp_name, item, score_result)
            send_result = format_slack.send_to_slack(payload)
            if send_result.get("status") == "sent":
                db.news_items().update_one({"_id": doc_id}, {"$set": {"is_alerted": True}})
                alerted_count += 1

    print(
        f"[news_search] {comp_name}: {len(processed)} new items, {alerted_count} alerts sent",
        file=sys.stderr,
    )
    return processed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Search for competitor news via Tavily")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Search news for all active competitors")
    group.add_argument("--competitor", help="Competitor slug")
    parser.add_argument("--days", type=int, default=7, help="Search recency window in days (default: 7)")
    parser.add_argument("--alert-threshold", type=float, default=0.7,
                        help="Minimum relevance score to send Slack alert (default: 0.7)")
    parser.add_argument("--no-alert", action="store_true", help="Disable Slack alerts")
    args = parser.parse_args()

    try:
        all_items = []

        if args.competitor:
            comp = db.get_competitor_by_slug(args.competitor)
            if not comp:
                print(json.dumps({"error": f"Competitor not found: {args.competitor}"}), file=sys.stderr)
                sys.exit(1)
            all_items = run_news_search(
                comp,
                days=args.days,
                alert_threshold=args.alert_threshold,
                send_alerts=not args.no_alert,
            )
        else:  # --all
            for comp in db.get_all_active_competitors():
                items = run_news_search(
                    comp,
                    days=args.days,
                    alert_threshold=args.alert_threshold,
                    send_alerts=not args.no_alert,
                )
                all_items.extend(items)

        # Sort by relevance descending
        all_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        print(json.dumps(all_items, indent=2, default=str))

        # Summary to stderr
        high_count = sum(1 for i in all_items if i.get("relevance_score", 0) >= 0.7)
        print(
            f"\nNews search complete: {len(all_items)} new items found, {high_count} high-relevance",
            file=sys.stderr,
        )

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
