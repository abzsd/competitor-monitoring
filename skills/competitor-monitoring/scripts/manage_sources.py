#!/usr/bin/env python3
"""Manage competitor sources and seed initial data from settings.yaml.

Usage:
    python3 manage_sources.py seed               # Seed competitors + sources from settings.yaml
    python3 manage_sources.py list                # List all active sources
    python3 manage_sources.py list --competitor <slug>
    python3 manage_sources.py add --url <url> --competitor <slug> --page-type pricing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import yaml

import db

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "settings.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def seed_from_config():
    """Seed competitors and sources from settings.yaml into MongoDB."""
    config = load_config()
    seeded_competitors = 0
    seeded_sources = 0

    for comp in config.get("competitors", []):
        # Upsert competitor
        existing = db.get_competitor_by_slug(comp["slug"])
        if not existing:
            comp_doc = {
                "_id": str(__import__("bson").ObjectId()),
                "name": comp["name"],
                "slug": comp["slug"],
                "domain": comp["domain"],
                "industry": comp.get("industry", ""),
                "description": comp.get("description", ""),
                "tags": comp.get("tags", []),
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            db.save_competitor(comp_doc)
            competitor_id = comp_doc["_id"]
            seeded_competitors += 1
            print(f"  Created competitor: {comp['name']} ({comp['slug']})")
        else:
            competitor_id = existing["_id"]
            print(f"  Competitor exists: {comp['name']} ({comp['slug']})")

        # Seed sources
        for src in comp.get("sources", []):
            existing_src = db.get_source_by_url(src["url"])
            if not existing_src:
                src_doc = {
                    "_id": str(__import__("bson").ObjectId()),
                    "competitor_id": competitor_id,
                    "url": src["url"],
                    "page_type": src.get("page_type", "other"),
                    "scrape_method": src.get("scrape_method", "static"),
                    "scrape_config": src.get("scrape_config", {}),
                    "schedule_group": src.get("schedule_group", "daily"),
                    "discovery_method": "manual",
                    "is_active": True,
                    "consecutive_failures": 0,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                db.save_source(src_doc)
                seeded_sources += 1
                print(f"    Added source: {src['url']} ({src.get('page_type', 'other')})")
            else:
                print(f"    Source exists: {src['url']}")

    print(f"\nSeeded {seeded_competitors} competitors, {seeded_sources} sources.")


def list_sources(competitor_slug: str | None = None):
    """List active sources, optionally filtered by competitor."""
    competitor_id = None
    if competitor_slug:
        comp = db.get_competitor_by_slug(competitor_slug)
        if not comp:
            print(f"Competitor not found: {competitor_slug}", file=sys.stderr)
            sys.exit(1)
        competitor_id = comp["_id"]

    sources_list = db.get_active_sources(competitor_id=competitor_id)

    # Enrich with competitor names
    output = []
    for src in sources_list:
        comp = db.get_competitor_by_id(src["competitor_id"]) if src.get("competitor_id") else None
        output.append({
            "source_id": src["_id"],
            "competitor": comp["name"] if comp else "Unknown",
            "url": src["url"],
            "page_type": src.get("page_type", ""),
            "scrape_method": src.get("scrape_method", ""),
            "schedule_group": src.get("schedule_group", ""),
            "last_scraped": str(src.get("last_scraped_at", "never")),
            "failures": src.get("consecutive_failures", 0),
        })

    print(json.dumps(output, indent=2, default=str))


def add_source(url: str, competitor_slug: str, page_type: str, scrape_method: str, schedule_group: str):
    """Add a single source."""
    comp = db.get_competitor_by_slug(competitor_slug)
    if not comp:
        print(f"Competitor not found: {competitor_slug}", file=sys.stderr)
        sys.exit(1)

    if db.get_source_by_url(url):
        print(f"Source already exists: {url}", file=sys.stderr)
        sys.exit(1)

    doc = {
        "_id": str(__import__("bson").ObjectId()),
        "competitor_id": comp["_id"],
        "url": url,
        "page_type": page_type,
        "scrape_method": scrape_method,
        "schedule_group": schedule_group,
        "discovery_method": "manual",
        "is_active": True,
        "consecutive_failures": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    source_id = db.save_source(doc)
    print(json.dumps({"status": "created", "source_id": source_id, "url": url}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Manage competitor sources")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Seed from settings.yaml")

    list_parser = sub.add_parser("list", help="List active sources")
    list_parser.add_argument("--competitor", help="Filter by competitor slug")

    add_parser = sub.add_parser("add", help="Add a source")
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--competitor", required=True, help="Competitor slug")
    add_parser.add_argument("--page-type", default="other")
    add_parser.add_argument("--scrape-method", default="static")
    add_parser.add_argument("--schedule-group", default="daily")

    args = parser.parse_args()

    try:
        db.ensure_indexes()

        if args.command == "seed":
            seed_from_config()
        elif args.command == "list":
            list_sources(args.competitor)
        elif args.command == "add":
            add_source(args.url, args.competitor, args.page_type, args.scrape_method, args.schedule_group)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
