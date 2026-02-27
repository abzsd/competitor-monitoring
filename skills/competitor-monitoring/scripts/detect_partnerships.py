#!/usr/bin/env python3
"""Detect competitor partnerships from scraped content, news, and web search.

Usage:
    python3 detect_partnerships.py --competitor <slug>   # Check one competitor
    python3 detect_partnerships.py --all                 # Check all competitors
    python3 detect_partnerships.py --scan-text "<text>" --competitor-id <id>
    python3 detect_partnerships.py --all --search-news --save  # Include Tavily news search

Combines:
    1. Keyword-based detection in scraped snapshot text
    2. Structured data extraction from partnership/integration pages
    3. Named entity co-occurrence near partnership signal words
    4. Tavily web search for partnership news (with --search-news flag)

Output:
    JSON array of detected partnership candidates.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
from models import PartnershipStatus, PartnershipType

# ---------------------------------------------------------------------------
# Signal keywords and patterns
# ---------------------------------------------------------------------------

PARTNERSHIP_SIGNALS = [
    r"partner(?:ship|ed|ing|s)\b",
    r"integrat(?:ion|ed|es|ing)\b",
    r"collaborat(?:ion|ed|es|ing)\b",
    r"powered\s+by\b",
    r"works\s+with\b",
    r"built\s+on\b",
    r"connect(?:s|ed|ing)?\s+(?:with|to)\b",
    r"acqui(?:red|sition|ring)\b",
    r"merg(?:ed|er|ing)\b",
    r"strategic\s+alliance\b",
    r"joint\s+venture\b",
    r"resell(?:er|ing)\b",
    r"certified\s+partner\b",
    r"technology\s+partner\b",
    r"ecosystem\b",
]

PARTNERSHIP_PATTERN = re.compile(
    "|".join(PARTNERSHIP_SIGNALS), re.IGNORECASE
)

# Patterns that indicate partnership type
TYPE_PATTERNS = {
    PartnershipType.ACQUISITION: re.compile(
        r"acqui(?:red|sition|ring)|merg(?:ed|er|ing)|bought|takeover", re.IGNORECASE
    ),
    PartnershipType.INVESTMENT: re.compile(
        r"invest(?:ed|ment|ing|or)|fund(?:ed|ing|raise)|series\s+[a-z]|raised\s+\$", re.IGNORECASE
    ),
    PartnershipType.STRATEGIC: re.compile(
        r"strategic\s+(?:alliance|partner)|joint\s+venture|exclusive\s+partner", re.IGNORECASE
    ),
    PartnershipType.RESELLER: re.compile(
        r"resell(?:er|ing)|distribut(?:or|ion)|channel\s+partner|marketplace", re.IGNORECASE
    ),
    PartnershipType.INTEGRATION: re.compile(
        r"integrat(?:ion|ed|es)|connect(?:s|ed)|plugin|add-?on|extension|api\s+partner", re.IGNORECASE
    ),
}


# ---------------------------------------------------------------------------
# Entity extraction (simple heuristic approach)
# ---------------------------------------------------------------------------

# Common words that are NOT company names
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "this", "that", "these", "those", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "shall", "can", "our", "their", "its", "new", "all",
    "more", "also", "than", "other", "about", "into", "over", "such",
    "now", "between", "through", "after", "before", "during", "including",
    "here", "there", "where", "when", "how", "what", "which", "who",
    "today", "read", "learn", "click", "visit", "see", "get", "try",
    "start", "free", "sign", "log", "contact", "support", "help",
}


def extract_potential_entity_names(text: str, window: int = 100) -> list[dict]:
    """Extract potential company/product names near partnership signals.

    Looks for capitalized multi-word sequences near partnership keywords.
    Returns list of {name, context, signal_word} dicts.
    """
    candidates = []

    for match in PARTNERSHIP_PATTERN.finditer(text):
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        context = text[start:end]
        signal_word = match.group()

        # Find capitalized sequences (likely company/product names)
        # Matches: "Acme Corp", "BigCo Inc", "AWS", "Google Cloud"
        name_pattern = re.compile(
            r"\b([A-Z][a-zA-Z]*(?:\s+(?:[A-Z][a-zA-Z]*|(?:of|and|the|for|by)\s+[A-Z][a-zA-Z]*))*)\b"
        )
        for name_match in name_pattern.finditer(context):
            name = name_match.group().strip()
            # Filter out common non-entity words
            name_words = name.lower().split()
            if len(name_words) == 1 and name_words[0] in STOP_WORDS:
                continue
            if len(name) < 2 or len(name) > 60:
                continue

            candidates.append({
                "name": name,
                "context": context.strip(),
                "signal_word": signal_word,
            })

    return candidates


def classify_partnership_type(context: str) -> PartnershipType:
    """Classify partnership type from surrounding text context."""
    for ptype, pattern in TYPE_PATTERNS.items():
        if pattern.search(context):
            return ptype
    return PartnershipType.INTEGRATION  # default


def compute_confidence(signals_count: int, has_structured_data: bool, name_frequency: int) -> float:
    """Compute a rough confidence score for the partnership detection."""
    score = 0.3  # base

    # More signal keywords found → higher confidence
    score += min(signals_count * 0.1, 0.3)

    # Found in structured data (partner section) → much higher confidence
    if has_structured_data:
        score += 0.25

    # Name appears multiple times → likely real
    if name_frequency >= 3:
        score += 0.15
    elif name_frequency >= 2:
        score += 0.1

    return min(score, 0.99)


# ---------------------------------------------------------------------------
# Detection pipeline
# ---------------------------------------------------------------------------

def detect_from_snapshots(competitor_id: str) -> list[dict]:
    """Scan recent snapshots for partnership signals."""
    detected = []

    # Get all active sources for this competitor
    source_docs = db.get_active_sources(competitor_id=competitor_id)

    for source_doc in source_docs:
        # Get the latest snapshot
        snapshot = db.get_latest_snapshot(source_doc["_id"])
        if not snapshot:
            continue

        text = snapshot.get("extracted_text", "")
        structured = snapshot.get("structured_data", {})

        # 1. Check structured data for explicit partner lists
        partners_from_struct = structured.get("partners", [])
        for partner_name in partners_from_struct:
            if not partner_name or len(partner_name) < 2:
                continue
            # Check if already known
            if db.partnership_exists(competitor_id, partner_name):
                continue
            detected.append({
                "partner_name": partner_name,
                "partnership_type": PartnershipType.INTEGRATION.value,
                "source_url": source_doc["url"],
                "snapshot_id": snapshot["_id"],
                "confidence": 0.8,  # High confidence from structured data
                "context": f"Found in structured partner list on {source_doc['url']}",
                "status": PartnershipStatus.CONFIRMED.value,
            })

        # 2. Extract entities near partnership signals in text
        if not PARTNERSHIP_PATTERN.search(text):
            continue

        candidates = extract_potential_entity_names(text)

        # Group by name and count occurrences
        name_groups: dict[str, list[dict]] = {}
        for cand in candidates:
            key = cand["name"].lower()
            name_groups.setdefault(key, []).append(cand)

        for name_lower, occurrences in name_groups.items():
            display_name = occurrences[0]["name"]

            # Skip if already known
            if db.partnership_exists(competitor_id, display_name):
                continue

            ptype = classify_partnership_type(occurrences[0]["context"])
            confidence = compute_confidence(
                signals_count=len(occurrences),
                has_structured_data=bool(partners_from_struct),
                name_frequency=len(occurrences),
            )

            # Only report if above threshold
            if confidence < 0.4:
                continue

            detected.append({
                "partner_name": display_name,
                "partnership_type": ptype.value,
                "source_url": source_doc["url"],
                "snapshot_id": snapshot["_id"],
                "confidence": round(confidence, 2),
                "context": occurrences[0]["context"][:300],
                "status": PartnershipStatus.RUMORED.value if confidence < 0.7 else PartnershipStatus.CONFIRMED.value,
            })

    return detected


def detect_from_text(text: str, competitor_id: str) -> list[dict]:
    """Detect partnerships from arbitrary text (e.g., news article fed by the agent)."""
    detected = []

    if not PARTNERSHIP_PATTERN.search(text):
        return detected

    candidates = extract_potential_entity_names(text, window=150)

    name_groups: dict[str, list[dict]] = {}
    for cand in candidates:
        key = cand["name"].lower()
        name_groups.setdefault(key, []).append(cand)

    for name_lower, occurrences in name_groups.items():
        display_name = occurrences[0]["name"]

        if db.partnership_exists(competitor_id, display_name):
            continue

        ptype = classify_partnership_type(occurrences[0]["context"])
        confidence = compute_confidence(
            signals_count=len(occurrences),
            has_structured_data=False,
            name_frequency=len(occurrences),
        )

        if confidence < 0.35:
            continue

        detected.append({
            "partner_name": display_name,
            "partnership_type": ptype.value,
            "source_url": "",
            "snapshot_id": "",
            "confidence": round(confidence, 2),
            "context": occurrences[0]["context"][:300],
            "status": PartnershipStatus.RUMORED.value,
        })

    return detected


# ---------------------------------------------------------------------------
# Tavily web search for partnership news
# ---------------------------------------------------------------------------

_tavily_client = None


def _get_tavily():
    global _tavily_client
    if _tavily_client is None:
        _env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        from dotenv import load_dotenv
        load_dotenv(_env_path)
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY not set — cannot use --search-news")
        from tavily import TavilyClient
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


def detect_from_news_search(competitor_doc: dict, days: int = 14) -> list[dict]:
    """Search Tavily for partnership/integration news and extract partner names.

    Returns list of partnership candidate dicts with detection_source="news_search"
    and a lower base confidence of 0.5.
    """
    name = competitor_doc["name"]
    competitor_id = competitor_doc["_id"]
    tavily = _get_tavily()
    detected = []
    seen_urls: set[str] = set()

    query = f'"{name}" partnership OR integration OR collaboration'

    try:
        response = tavily.search(
            query=query,
            search_depth="basic",
            max_results=10,
            days=days,
        )
    except Exception as e:
        print(f"[detect_partnerships] Tavily error for {name}: {e}", file=sys.stderr)
        return detected

    for result in response.get("results", []):
        url = result.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        content = f"{result.get('title', '')} {result.get('content', '')}"

        if not PARTNERSHIP_PATTERN.search(content):
            continue

        candidates = extract_potential_entity_names(content, window=150)

        name_groups: dict[str, list[dict]] = {}
        for cand in candidates:
            key = cand["name"].lower()
            if key == name.lower() or key in name.lower():
                continue
            name_groups.setdefault(key, []).append(cand)

        domain = urlparse(url).netloc.replace("www.", "")

        for name_lower, occurrences in name_groups.items():
            display_name = occurrences[0]["name"]

            if db.partnership_exists(competitor_id, display_name):
                continue

            ptype = classify_partnership_type(occurrences[0]["context"])

            base_confidence = 0.5
            bonus = min(len(occurrences) * 0.05, 0.15)
            confidence = min(base_confidence + bonus, 0.75)

            if confidence < 0.4:
                continue

            detected.append({
                "partner_name": display_name,
                "partnership_type": ptype.value,
                "source_url": url,
                "source_domain": domain,
                "snapshot_id": "",
                "confidence": round(confidence, 2),
                "context": occurrences[0]["context"][:300],
                "status": PartnershipStatus.RUMORED.value,
                "detection_source": "news_search",
                "search_result_title": result.get("title", ""),
            })

    return detected


def save_detected_partnerships(competitor_id: str, partnerships_list: list[dict]) -> int:
    """Save detected partnerships to MongoDB. Returns count saved."""
    saved = 0
    now = datetime.now(timezone.utc)

    for p in partnerships_list:
        if db.partnership_exists(competitor_id, p["partner_name"]):
            continue

        doc = {
            "_id": str(__import__("bson").ObjectId()),
            "competitor_id": competitor_id,
            "partner_name": p["partner_name"],
            "partnership_type": p["partnership_type"],
            "source_url": p.get("source_url", ""),
            "discovered_at": now,
            "first_seen_snapshot_id": p.get("snapshot_id"),
            "description": p.get("context", ""),
            "confidence": p.get("confidence", 0.5),
            "status": p.get("status", "rumored"),
            "analysis_id": None,
            "created_at": now,
            "updated_at": now,
        }
        db.save_partnership(doc)
        saved += 1

    return saved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Detect competitor partnerships")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Check all competitors")
    group.add_argument("--competitor", help="Competitor slug")
    group.add_argument("--scan-text", help="Scan arbitrary text for partnerships")
    parser.add_argument("--competitor-id", help="Competitor ID (required with --scan-text)")
    parser.add_argument("--save", action="store_true", help="Auto-save to MongoDB")
    parser.add_argument("--search-news", action="store_true",
                        help="Also search Tavily for partnership news (requires TAVILY_API_KEY)")
    args = parser.parse_args()

    try:
        all_detected = []

        if args.scan_text:
            if not args.competitor_id:
                print(json.dumps({"error": "--competitor-id required with --scan-text"}), file=sys.stderr)
                sys.exit(1)
            all_detected = detect_from_text(args.scan_text, args.competitor_id)

        elif args.competitor:
            comp = db.get_competitor_by_slug(args.competitor)
            if not comp:
                print(json.dumps({"error": f"Competitor not found: {args.competitor}"}), file=sys.stderr)
                sys.exit(1)
            all_detected = detect_from_snapshots(comp["_id"])

            if args.search_news:
                news_detected = detect_from_news_search(comp)
                for d in news_detected:
                    d["competitor_name"] = comp["name"]
                    d["competitor_slug"] = comp["slug"]
                all_detected.extend(news_detected)
                print(f"News search found {len(news_detected)} additional candidates for {comp['name']}.",
                      file=sys.stderr)

            if args.save:
                saved = save_detected_partnerships(comp["_id"], all_detected)
                print(f"Saved {saved} new partnerships.", file=sys.stderr)

        else:  # --all
            for comp in db.get_all_active_competitors():
                detected = detect_from_snapshots(comp["_id"])

                if args.search_news:
                    news_detected = detect_from_news_search(comp)
                    for d in news_detected:
                        d["detection_source"] = "news_search"
                    detected.extend(news_detected)

                for d in detected:
                    d["competitor_name"] = comp["name"]
                    d["competitor_slug"] = comp["slug"]
                all_detected.extend(detected)
                if args.save:
                    saved = save_detected_partnerships(comp["_id"], detected)
                    if saved:
                        print(f"Saved {saved} partnerships for {comp['name']}.", file=sys.stderr)

        print(json.dumps(all_detected, indent=2, default=str))

        if not all_detected:
            print("No new partnerships detected.", file=sys.stderr)

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
