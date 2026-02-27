#!/usr/bin/env python3
"""Deep investigation on significant changes — research broader context via web search.

When a high/critical severity change is detected, this script:
1. Reads the change record
2. Extracts key entities and topics
3. Searches for related news, press releases, analyst coverage
4. Pulls full content from top URLs
5. Synthesizes an investigation report via LLM
6. Saves to analyses collection

Usage:
    python3 investigate.py --change-id <id>
    python3 investigate.py --change-json '<json>'
    python3 investigate.py --change-id <id> --no-extract

Output:
    JSON investigation report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import llm

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
# Step 1: Load change
# ---------------------------------------------------------------------------

def load_change(change_id: str | None = None, change_json: str | None = None) -> dict:
    """Load a change record from MongoDB by ID or parse from JSON string."""
    if change_json:
        return json.loads(change_json)

    if change_id:
        change = db.changes().find_one({"_id": change_id})
        if change:
            return change
        raise ValueError(f"Change not found: {change_id}")

    raise ValueError("Either --change-id or --change-json must be provided")


# ---------------------------------------------------------------------------
# Step 2: Extract entities and topics
# ---------------------------------------------------------------------------

# Common words that are NOT company names
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "this", "that", "new", "our", "their", "now", "more",
    "also", "here", "where", "when", "what", "which", "who", "free",
    "start", "get", "try", "before", "after", "during", "read", "learn",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}


def extract_investigation_topics(change: dict) -> dict:
    """Extract key entities and topics from a change for web research.

    Returns {"company_names": [...], "dollar_amounts": [...],
             "keywords": [...], "search_queries": [...], "competitor_name": str}.
    """
    # Combine all text fields for extraction
    text_sources = [
        change.get("summary", ""),
        change.get("text_diff", ""),
    ]
    structured = change.get("structured_diff", {})
    if isinstance(structured, dict):
        for items in structured.values():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        text_sources.extend(str(v) for v in item.values())

    full_text = " ".join(text_sources)

    # Extract dollar amounts
    dollar_pattern = re.compile(
        r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|M|billion|B|thousand|K))?", re.IGNORECASE
    )
    dollar_amounts = dollar_pattern.findall(full_text)

    # Extract capitalized entity names
    name_pattern = re.compile(
        r"\b([A-Z][a-zA-Z]*(?:\s+(?:[A-Z][a-zA-Z]*|(?:of|and|the|for|by)\s+[A-Z][a-zA-Z]*))*)\b"
    )
    raw_names = name_pattern.findall(full_text)
    company_names = list(set(
        n for n in raw_names
        if len(n) > 2 and n.lower() not in _STOP_WORDS and len(n.split()) <= 5
    ))

    # Get competitor context
    comp_name = ""
    if change.get("competitor_id"):
        comp = db.get_competitor_by_id(change["competitor_id"])
        if comp:
            comp_name = comp["name"]

    # Build search queries
    summary = change.get("summary", "")[:100]
    search_queries = []

    if comp_name:
        search_queries.append(f'"{comp_name}" {summary}')
        if dollar_amounts:
            search_queries.append(f'"{comp_name}" {dollar_amounts[0]}')
        search_queries.append(f'"{comp_name}" announcement news')

    # Add queries for extracted entity names (potential partners / acquirees)
    for name in company_names[:3]:
        if name != comp_name and len(name) > 3:
            search_queries.append(f'"{name}" {comp_name}' if comp_name else f'"{name}" announcement')

    return {
        "company_names": company_names[:10],
        "dollar_amounts": dollar_amounts[:5],
        "keywords": [w for w in summary.split() if len(w) > 4][:10],
        "search_queries": search_queries[:5],
        "competitor_name": comp_name,
    }


# ---------------------------------------------------------------------------
# Step 3: Search for related coverage
# ---------------------------------------------------------------------------

def search_related_coverage(queries: list[str], days: int = 14) -> list[dict]:
    """Search Tavily for related news across multiple queries. De-duplicate by URL."""
    tavily = _get_tavily()
    seen_urls: set[str] = set()
    all_results = []

    for query in queries:
        try:
            response = tavily.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                days=days,
            )
        except Exception as e:
            print(f"[investigate] Tavily search error: {e}", file=sys.stderr)
            continue

        for result in response.get("results", []):
            url = result.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_results.append({
                "title": result.get("title", ""),
                "url": url,
                "content": result.get("content", ""),
                "score": result.get("score", 0.0),
                "published_date": result.get("published_date", ""),
            })

    # Sort by Tavily relevance score descending
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_results


# ---------------------------------------------------------------------------
# Step 4: Extract full content from top URLs
# ---------------------------------------------------------------------------

def extract_full_content(urls: list[str]) -> list[dict]:
    """Use Tavily extract() to pull full article content from top URLs.

    Returns list of {"url": str, "raw_content": str} dicts.
    """
    if not urls:
        return []

    tavily = _get_tavily()
    extracted = []

    try:
        response = tavily.extract(urls=urls[:3])
        for result in response.get("results", []):
            extracted.append({
                "url": result.get("url", ""),
                "raw_content": result.get("raw_content", "")[:5000],
            })
    except Exception as e:
        print(f"[investigate] Tavily extract error: {e}", file=sys.stderr)

    return extracted


# ---------------------------------------------------------------------------
# Step 5: LLM investigation report synthesis
# ---------------------------------------------------------------------------

def synthesize_investigation(
    change: dict,
    topics: dict,
    search_results: list[dict],
    extracted_content: list[dict],
) -> dict:
    """Use LLM to synthesize a comprehensive investigation report."""
    if not llm.is_available():
        return {
            "what_happened": change.get("summary", "Change detected"),
            "why_it_matters": "LLM unavailable — manual analysis recommended",
            "market_context": "",
            "recommended_response": ["Review the change manually"],
            "confidence": 0.3,
            "key_facts": topics.get("dollar_amounts", []),
            "sources_cited": [r["url"] for r in search_results[:3]],
            "risk_level": "medium",
        }

    prompt = (
        "You are a senior competitive intelligence analyst conducting a deep investigation. "
        "Analyze the detected change and supporting research. Return a JSON object with:\n\n"
        '- "what_happened": 2-3 sentence factual summary of what occurred\n'
        '- "why_it_matters": 2-3 sentences on business impact and strategic significance\n'
        '- "market_context": 1-2 sentences placing this in broader market context\n'
        '- "recommended_response": array of 2-4 specific recommended actions for our team\n'
        '- "confidence": float 0.0-1.0, how confident you are in this analysis\n'
        '- "key_facts": array of 3-5 specific facts (names, numbers, dates) extracted\n'
        '- "sources_cited": array of URLs that were most informative\n'
        '- "risk_level": "low" | "medium" | "high" | "critical"\n\n'
        "Be specific. Cite numbers, names, dates. No vague generalities."
    )

    # Build context from all gathered intelligence
    context_parts = [
        f"DETECTED CHANGE:\n{json.dumps(change, default=str)[:1500]}",
        f"\nKEY ENTITIES: {', '.join(topics.get('company_names', [])[:5])}",
        f"DOLLAR AMOUNTS: {', '.join(topics.get('dollar_amounts', [])[:3])}",
    ]

    if search_results:
        context_parts.append("\nRELATED NEWS COVERAGE:")
        for r in search_results[:5]:
            context_parts.append(f"- [{r['title']}]({r['url']})\n  {r['content'][:200]}")

    if extracted_content:
        context_parts.append("\nFULL ARTICLE CONTENT:")
        for ec in extracted_content[:2]:
            context_parts.append(f"Source: {ec['url']}\n{ec['raw_content'][:2000]}")

    context = "\n".join(context_parts)

    result = llm.analyze(prompt, context, max_tokens=1500, temperature=0.3)

    if result and "what_happened" in result:
        return result

    return {
        "what_happened": change.get("summary", ""),
        "why_it_matters": result.get("raw_response", "") if result else "",
        "market_context": "",
        "recommended_response": [],
        "confidence": 0.4,
        "key_facts": [],
        "sources_cited": [r["url"] for r in search_results[:3]],
        "risk_level": "medium",
    }


# ---------------------------------------------------------------------------
# Step 6: Save investigation
# ---------------------------------------------------------------------------

def save_investigation(
    change: dict,
    topics: dict,
    search_results: list[dict],
    report: dict,
) -> str:
    """Save the investigation as an analysis document. Returns analysis_id."""
    now = datetime.now(timezone.utc)

    analysis_content = {
        "summary": report.get("what_happened", ""),
        "impact_assessment": report.get("why_it_matters", ""),
        "market_context": report.get("market_context", ""),
        "actionable_insights": report.get("recommended_response", []),
        "confidence": report.get("confidence", 0.5),
        "category": change.get("change_type", "content_update"),
        "key_facts": report.get("key_facts", []),
        "risk_level": report.get("risk_level", "medium"),
        "sources_cited": report.get("sources_cited", []),
        "search_results_count": len(search_results),
        "entities_extracted": topics.get("company_names", []),
    }

    doc = {
        "_id": str(__import__("bson").ObjectId()),
        "competitor_id": change.get("competitor_id", ""),
        "change_ids": [change["_id"]] if "_id" in change else [],
        "analysis_type": "investigation",
        "generated_at": now,
        "content": analysis_content,
        "raw_response": json.dumps(report, default=str),
        "created_at": now,
    }

    analysis_id = db.save_analysis(doc)

    # Mark the change as analyzed
    if "_id" in change:
        db.mark_change_analyzed(change["_id"], analysis_id)

    return analysis_id


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_investigation(change: dict, skip_extract: bool = False) -> dict:
    """Full investigation pipeline. Returns the complete report dict."""
    # Step 2: Extract topics
    topics = extract_investigation_topics(change)
    print(f"[investigate] Extracted {len(topics['company_names'])} entities, "
          f"{len(topics['search_queries'])} queries", file=sys.stderr)

    # Step 3: Search for related coverage
    search_results = search_related_coverage(topics["search_queries"])
    print(f"[investigate] Found {len(search_results)} related articles", file=sys.stderr)

    # Step 4: Extract full content from top URLs
    extracted_content = []
    if not skip_extract and search_results:
        top_urls = [r["url"] for r in search_results[:3]]
        extracted_content = extract_full_content(top_urls)
        print(f"[investigate] Extracted content from {len(extracted_content)} articles", file=sys.stderr)

    # Step 5: Synthesize report
    report = synthesize_investigation(change, topics, search_results, extracted_content)
    print(f"[investigate] Report generated (confidence: {report.get('confidence', 'N/A')})", file=sys.stderr)

    # Step 6: Save
    analysis_id = save_investigation(change, topics, search_results, report)
    print(f"[investigate] Saved as analysis {analysis_id}", file=sys.stderr)

    # Build complete output
    return {
        "analysis_id": analysis_id,
        "change_id": change.get("_id", ""),
        "competitor_id": change.get("competitor_id", ""),
        "topics_extracted": topics,
        "articles_found": len(search_results),
        "articles_extracted": len(extracted_content),
        "report": report,
        "search_results": [{"title": r["title"], "url": r["url"], "score": r["score"]}
                           for r in search_results[:10]],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Deep investigation on a detected change")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--change-id", help="Change ID to investigate (loads from MongoDB)")
    group.add_argument("--change-json", help="Change JSON string to investigate")
    parser.add_argument("--no-extract", action="store_true",
                        help="Skip Tavily extract (faster, less context)")
    args = parser.parse_args()

    try:
        change = load_change(change_id=args.change_id, change_json=args.change_json)
        result = run_investigation(change, skip_extract=args.no_extract)
        print(json.dumps(result, indent=2, default=str))

    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
