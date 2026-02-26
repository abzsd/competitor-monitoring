#!/usr/bin/env python3
"""Discover new monitorable pages from competitor websites.

Usage:
    python3 discover_sources.py <domain> [--competitor-id <id>] [--max-depth <n>]

Discovery methods:
    1. Parse robots.txt for sitemap URLs
    2. Parse XML sitemaps recursively
    3. Filter URLs by relevant path patterns

Output:
    JSON array of discovered source candidates (not yet in DB).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import feedparser
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
from models import DiscoveredSource, DiscoveryMethod, PageType

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RELEVANT_PATH_PATTERNS = [
    (r"/pricing", PageType.PRICING),
    (r"/plans", PageType.PRICING),
    (r"/product", PageType.PRODUCT),
    (r"/features", PageType.PRODUCT),
    (r"/solutions", PageType.PRODUCT),
    (r"/partner", PageType.PARTNERSHIPS),
    (r"/integration", PageType.PARTNERSHIPS),
    (r"/blog", PageType.BLOG),
    (r"/changelog", PageType.CHANGELOG),
    (r"/release", PageType.CHANGELOG),
    (r"/what.?s.?new", PageType.CHANGELOG),
    (r"/tech", PageType.TECH_STACK),
    (r"/stack", PageType.TECH_STACK),
    (r"/career", PageType.CAREERS),
    (r"/job", PageType.CAREERS),
    (r"/about", PageType.OTHER),
]

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; CompetitorMonitor/1.0)"

# ---------------------------------------------------------------------------
# Robots.txt & Sitemap parsing
# ---------------------------------------------------------------------------

def _base_url(domain: str) -> str:
    """Return the base URL for a domain, trying HTTPS first then HTTP."""
    for scheme in ["https", "http"]:
        url = f"{scheme}://{domain}/"
        try:
            requests.head(url, timeout=5, headers={"User-Agent": USER_AGENT})
            return f"{scheme}://{domain}"
        except requests.RequestException:
            continue
    return f"https://{domain}"  # fallback


def fetch_robots_txt(domain: str) -> str:
    """Fetch robots.txt from a domain."""
    base = _base_url(domain)
    url = f"{base}/robots.txt"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 200:
            return resp.text
    except requests.RequestException:
        pass
    return ""


def extract_sitemap_urls(robots_text: str) -> list[str]:
    """Extract Sitemap: URLs from robots.txt."""
    sitemaps = []
    for line in robots_text.splitlines():
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            url = line.split(":", 1)[1].strip()
            sitemaps.append(url)
    return sitemaps


def parse_sitemap(url: str, depth: int = 0, max_depth: int = 3) -> list[str]:
    """Recursively parse XML sitemaps. Returns a list of page URLs."""
    if depth > max_depth:
        return []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200:
            return []
    except requests.RequestException:
        return []

    urls = []
    try:
        root = ElementTree.fromstring(resp.content)
        # Namespace handling — sitemaps use xmlns
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Check if this is a sitemap index (contains other sitemaps)
        for sitemap_el in root.findall(".//sm:sitemap/sm:loc", ns):
            if sitemap_el.text:
                urls.extend(parse_sitemap(sitemap_el.text.strip(), depth + 1, max_depth))

        # Regular sitemap — extract page URLs
        for url_el in root.findall(".//sm:url/sm:loc", ns):
            if url_el.text:
                urls.append(url_el.text.strip())

        # Handle sitemaps without namespace
        if not urls:
            for loc in root.iter("loc"):
                if loc.text:
                    urls.append(loc.text.strip())
    except ElementTree.ParseError:
        pass

    return urls


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

def classify_url(url: str) -> PageType | None:
    """Classify a URL by path pattern. Returns None if not relevant."""
    path = urlparse(url).path.lower()
    for pattern, page_type in RELEVANT_PATH_PATTERNS:
        if re.search(pattern, path):
            return page_type
    return None


def is_relevant_url(url: str, domain: str) -> bool:
    """Check if a URL is worth monitoring."""
    parsed = urlparse(url)

    # Must be from the target domain
    if domain not in parsed.netloc:
        return False

    # Skip common non-content paths
    skip_patterns = [
        r"/wp-content/", r"/wp-admin/", r"/wp-includes/",
        r"/assets/", r"/static/", r"/css/", r"/js/", r"/images/",
        r"/api/", r"/cdn-cgi/", r"\.xml$", r"\.json$", r"\.pdf$",
        r"/tag/", r"/category/", r"/author/", r"/page/\d+",
        r"/login", r"/signup", r"/register", r"/cart", r"/checkout",
    ]
    for pattern in skip_patterns:
        if re.search(pattern, parsed.path, re.IGNORECASE):
            return False

    return True


# ---------------------------------------------------------------------------
# Link crawling — discover pages by following links from existing pages
# ---------------------------------------------------------------------------

def crawl_page_links(url: str, domain: str, depth: int = 1, seen: set[str] | None = None) -> list[str]:
    """Fetch a page and extract internal links that might be new monitorable pages.

    Args:
        url: Page to crawl
        domain: Target domain to filter links
        depth: How many levels deep to follow links (1 = just this page's links)
        seen: URLs already visited (for recursion)

    Returns:
        List of discovered URLs on the same domain.
    """
    if seen is None:
        seen = set()
    if url in seen or depth < 0:
        return []
    seen.add(url)

    discovered = []
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200:
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Resolve relative URLs
            full_url = urljoin(url, href)

            # Normalize: strip trailing slashes, query params, fragments
            parsed = urlparse(full_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"

            if clean_url in seen:
                continue

            # Must be same domain and pass relevance filter
            if domain not in parsed.netloc:
                continue
            if not is_relevant_url(clean_url, domain):
                continue

            seen.add(clean_url)
            discovered.append(clean_url)

        # Recurse one level deeper if requested
        if depth > 1:
            for link_url in list(discovered):
                deeper = crawl_page_links(link_url, domain, depth - 1, seen)
                discovered.extend(deeper)

    except Exception:
        pass

    return discovered


# ---------------------------------------------------------------------------
# News discovery
# ---------------------------------------------------------------------------

def discover_news_mentions(competitor_name: str, limit: int = 10) -> list[DiscoveredSource]:
    """Search Google News RSS for competitor mentions."""
    results = []
    try:
        feed_url = f"https://news.google.com/rss/search?q={requests.utils.quote(competitor_name)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            results.append(DiscoveredSource(
                url=entry.get("link", ""),
                suggested_page_type=PageType.NEWS,
                discovery_method=DiscoveryMethod.NEWS,
                context=entry.get("title", ""),
            ))
    except Exception:
        pass
    return results


# ---------------------------------------------------------------------------
# Main discovery pipeline
# ---------------------------------------------------------------------------

def discover_sources(
    domain: str,
    competitor_id: str | None = None,
    max_depth: int = 3,
) -> list[DiscoveredSource]:
    """Discover new monitorable sources for a domain."""

    discovered: list[DiscoveredSource] = []
    seen_urls: set[str] = set()

    # Get existing source URLs to avoid duplicates
    if competitor_id:
        existing_sources = db.get_active_sources(competitor_id=competitor_id)
        seen_urls = {s["url"] for s in existing_sources}

    # 1. Parse robots.txt for sitemaps
    robots = fetch_robots_txt(domain)
    sitemap_urls = extract_sitemap_urls(robots)

    # Fallback: try common sitemap locations
    if not sitemap_urls:
        base = _base_url(domain)
        for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/"]:
            sitemap_urls.append(f"{base}{path}")

    # 2. Parse sitemaps
    all_urls: list[str] = []
    for sm_url in sitemap_urls:
        all_urls.extend(parse_sitemap(sm_url, max_depth=max_depth))

    # 3. Filter and classify
    for url in all_urls:
        if url in seen_urls:
            continue
        if not is_relevant_url(url, domain):
            continue

        page_type = classify_url(url)
        if page_type is None:
            page_type = PageType.OTHER  # Accept all relevant URLs, not just known patterns

        seen_urls.add(url)
        discovered.append(DiscoveredSource(
            url=url,
            suggested_page_type=page_type,
            discovery_method=DiscoveryMethod.SITEMAP,
            context=f"Found in sitemap for {domain}",
        ))

    # 4. Crawl links from existing monitored pages
    if competitor_id:
        existing_sources = db.get_active_sources(competitor_id=competitor_id)
        for source in existing_sources:
            source_url = source.get("url", "")
            if not source_url:
                continue
            try:
                crawled = crawl_page_links(source_url, domain, depth=1, seen=set(seen_urls))
                for crawled_url in crawled:
                    if crawled_url in seen_urls:
                        continue
                    page_type = classify_url(crawled_url)
                    if page_type is None:
                        page_type = PageType.OTHER
                    seen_urls.add(crawled_url)
                    discovered.append(DiscoveredSource(
                        url=crawled_url,
                        suggested_page_type=page_type,
                        discovery_method=DiscoveryMethod.CRAWL,
                        context=f"Found as link on {source_url}",
                    ))
            except Exception:
                pass

    # 5. Discover news mentions
    if competitor_id:
        competitor = db.get_competitor_by_id(competitor_id)
        if competitor:
            news = discover_news_mentions(competitor["name"])
            for item in news:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    discovered.append(item)

    return discovered


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Discover new competitor sources")
    parser.add_argument("domain", help="Competitor domain (e.g., acmecorp.com)")
    parser.add_argument("--competitor-id", help="MongoDB competitor ID")
    parser.add_argument("--max-depth", type=int, default=3, help="Max sitemap recursion depth")
    parser.add_argument("--save", action="store_true", help="Auto-save discovered sources to MongoDB")
    args = parser.parse_args()

    try:
        results = discover_sources(
            domain=args.domain,
            competitor_id=args.competitor_id,
            max_depth=args.max_depth,
        )

        # Optionally save to DB
        if args.save and args.competitor_id:
            saved = 0
            for source in results:
                if source.discovery_method == DiscoveryMethod.NEWS:
                    continue  # Don't auto-save news URLs as permanent sources
                if not db.get_source_by_url(source.url):
                    doc = {
                        "_id": str(__import__("bson").ObjectId()),
                        "competitor_id": args.competitor_id,
                        "url": source.url,
                        "page_type": source.suggested_page_type.value,
                        "scrape_method": "static",
                        "schedule_group": "daily",
                        "discovery_method": source.discovery_method.value,
                        "is_active": True,
                        "consecutive_failures": 0,
                    }
                    db.save_source(doc)
                    saved += 1
            print(f"Saved {saved} new sources to MongoDB.", file=sys.stderr)

        output = [s.model_dump() for s in results]
        print(json.dumps(output, indent=2))

        if not results:
            print("No new sources discovered.", file=sys.stderr)

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
