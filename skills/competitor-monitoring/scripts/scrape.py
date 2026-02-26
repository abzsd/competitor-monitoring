#!/usr/bin/env python3
"""Scrape a URL, extract content, and store a snapshot in MongoDB.

Usage:
    python3 scrape.py <url> [--source-id <id>] [--competitor-id <id>] [--stdin]

Options:
    --source-id     MongoDB source document ID (if already registered)
    --competitor-id MongoDB competitor document ID
    --stdin         Read raw HTML from stdin (when piped from OpenClaw browser)

Output:
    JSON with {snapshot_id, content_hash, has_change, extracted_text_preview, url}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import requests
import xxhash
from bs4 import BeautifulSoup, Comment

import db
from models import ScrapeResult

# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

# Tags whose entire content is non-informative
STRIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"}

# Common boilerplate CSS classes / ids to remove
BOILERPLATE_PATTERNS = re.compile(
    r"(cookie|consent|popup|modal|overlay|sidebar|advertisement|ad-|"
    r"social-share|share-buttons|newsletter|subscribe)",
    re.IGNORECASE,
)


def extract_text(html: str) -> str:
    """Convert raw HTML to clean extracted text."""
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content tags
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove boilerplate elements by class/id
    for el in soup.find_all(attrs={"class": BOILERPLATE_PATTERNS}):
        el.decompose()
    for el in soup.find_all(attrs={"id": BOILERPLATE_PATTERNS}):
        el.decompose()

    # Get text, collapse whitespace
    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines into one
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_structured_data(html: str, page_type: str = "other") -> dict:
    """Extract structured data based on page type.

    Returns a dict with type-specific fields. This is a best-effort
    extraction — the agent can refine or re-extract via browser if needed.
    """
    soup = BeautifulSoup(html, "lxml")
    data: dict = {}

    if page_type == "pricing":
        # Look for pricing cards/plans
        plans = []
        # Common pricing card selectors (ordered from most to least specific)
        cards = soup.select(".pricing-card, .price-card, .plan-card, .pricing-tier, [data-plan]")
        if not cards:
            # Fallback: broader selectors, but skip containers
            cards = [
                el for el in soup.select("[class*='pricing'], [class*='plan-']")
                if el.select_one(".price, .amount, [class*='price']")
            ]
        for card in cards:
            plan: dict = {}
            # Plan name
            name_el = card.select_one(
                "h2, h3, .plan-name, .tier-name, [class*='plan-name']"
            )
            if name_el:
                plan["name"] = name_el.get_text(strip=True)
            # Price
            price_el = card.select_one(
                ".price, .amount, [class*='price'], [class*='amount']"
            )
            if price_el:
                plan["price"] = price_el.get_text(strip=True)
            # Features
            features = []
            for li in card.select("li, .feature, [class*='feature']"):
                feat_text = li.get_text(strip=True)
                if feat_text:
                    features.append(feat_text)
            if features:
                plan["features"] = features
            if plan:
                plans.append(plan)
        if plans:
            data["plans"] = plans

    elif page_type == "tech_stack":
        # Look for technology mentions
        tech_keywords = soup.find_all(
            string=re.compile(
                r"(built with|powered by|technology|stack|infrastructure)",
                re.IGNORECASE,
            )
        )
        if tech_keywords:
            data["tech_mentions"] = [kw.strip() for kw in tech_keywords[:20]]

    elif page_type == "partnerships":
        # Look for partner logos or mentions
        partner_sections = soup.select(
            ".partners, .integrations, [class*='partner'], [class*='integration']"
        )
        partners = []
        for section in partner_sections:
            for item in section.select("img[alt], a, .partner-name, li"):
                name = item.get("alt") or item.get_text(strip=True)
                if name and len(name) < 100:
                    partners.append(name)
        if partners:
            data["partners"] = list(set(partners))[:50]

    # Extract meta tags (useful for any page type)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        data["meta_description"] = meta_desc["content"]

    title_tag = soup.find("title")
    if title_tag:
        data["page_title"] = title_tag.get_text(strip=True)

    # -----------------------------------------------------------------------
    # Universal extraction — runs for ALL page types
    # -----------------------------------------------------------------------

    # Headings: page structure skeleton
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and len(text) < 200:
            headings.append({"level": tag.name, "text": text})
    if headings:
        data["headings"] = headings[:50]

    # Stats: numbers with nearby context (e.g. "15,000+ Teams worldwide")
    stats = []
    for el in soup.find_all(["h3", "h2", "strong", "b"]):
        text = el.get_text(strip=True)
        # Only leaf-level elements with a number and short text
        if not text or not re.search(r"\d", text) or len(text) > 40:
            continue
        # Skip if this element has child headings (it's a container)
        if el.find(["h2", "h3", "h4"]):
            continue
        context = ""
        next_el = el.find_next_sibling(["p", "span", "div"])
        if next_el:
            ctx = next_el.get_text(strip=True)
            if ctx and len(ctx) < 80:
                context = ctx
        if not context:
            parent = el.parent
            if parent and parent.name not in ("body", "html"):
                sibling_p = parent.find("p")
                if sibling_p:
                    context = sibling_p.get_text(strip=True)[:80]
        stats.append({"value": text, "context": context})
    # Deduplicate stats by value
    seen_stats = set()
    unique_stats = []
    for s in stats:
        if s["value"] not in seen_stats:
            seen_stats.add(s["value"])
            unique_stats.append(s)
    if unique_stats:
        data["stats"] = unique_stats[:30]

    # Features / list items in content sections
    feature_items = []
    for ul in soup.find_all(["ul", "ol"]):
        # Walk up the tree to check for nav/footer ancestors
        skip = False
        for ancestor in ul.parents:
            if ancestor.name in ("nav", "footer", "header"):
                skip = True
                break
            ancestor_classes = " ".join(ancestor.get("class", []))
            if any(s in ancestor_classes.lower() for s in ["nav", "footer", "menu", "header"]):
                skip = True
                break
        if skip:
            continue
        for li in ul.find_all("li", recursive=False):
            text = li.get_text(strip=True)
            if text and 5 < len(text) < 300:
                feature_items.append(text)
    if feature_items:
        data["features"] = feature_items[:100]

    # CTAs: button and call-to-action text
    ctas = []
    for el in soup.select("a.btn-primary, a.btn-secondary, a.btn-white, button, "
                          "[class*='cta'], [class*='btn'], a[class*='button']"):
        text = el.get_text(strip=True)
        if text and 2 < len(text) < 60:
            ctas.append(text)
    if ctas:
        data["ctas"] = list(dict.fromkeys(ctas))[:20]  # deduplicate, preserve order

    # Images alt text (reveals logos, product screenshots, partner logos)
    images_alt = []
    for img in soup.find_all("img", alt=True):
        alt = img["alt"].strip()
        if alt and len(alt) > 2 and len(alt) < 200:
            images_alt.append(alt)
    if images_alt:
        data["images_alt"] = list(dict.fromkeys(images_alt))[:30]

    # Sections: top-level content blocks with heading + summary
    sections = []
    for section_el in soup.find_all(["section", "article"]):
        heading = section_el.find(["h1", "h2", "h3"])
        if not heading:
            continue
        heading_text = heading.get_text(strip=True)
        if not heading_text or len(heading_text) > 200:
            continue
        # Get first paragraph as summary
        para = section_el.find("p")
        summary = para.get_text(strip=True)[:200] if para else ""
        sections.append({"heading": heading_text, "summary": summary})
    if sections:
        data["sections"] = sections[:20]

    return data


# ---------------------------------------------------------------------------
# HTTP fetching
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def fetch_url(url: str, timeout: int = 30) -> tuple[str, dict]:
    """Fetch a URL and return (html, metadata)."""
    import random

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()

    metadata = {
        "http_status": resp.status_code,
        "response_time_ms": int(resp.elapsed.total_seconds() * 1000),
        "content_length": len(resp.content),
        "final_url": resp.url,
        "scrape_method": "static",
    }

    return resp.text, metadata


# ---------------------------------------------------------------------------
# Dynamic browser fetching (Selenium)
# ---------------------------------------------------------------------------

def fetch_url_dynamic(url: str, timeout: int = 30) -> tuple[str, dict]:
    """Fetch a URL using headless Chrome via Selenium. Returns (html, metadata).

    Falls back to static fetch_url() if Selenium is unavailable or fails.
    """
    import time as _time
    start = _time.time()

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={USER_AGENTS[0]}")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(timeout)

        try:
            driver.get(url)
            # Wait for body to be present
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Small wait for JS rendering
            _time.sleep(2)
            html = driver.page_source
            final_url = driver.current_url
        finally:
            driver.quit()

        elapsed_ms = int((_time.time() - start) * 1000)
        metadata = {
            "http_status": 200,
            "response_time_ms": elapsed_ms,
            "content_length": len(html),
            "final_url": final_url,
            "scrape_method": "dynamic",
        }
        return html, metadata

    except ImportError:
        print("[scrape] Selenium not installed, falling back to static fetch", file=sys.stderr)
        return fetch_url(url, timeout)
    except Exception as e:
        print(f"[scrape] Dynamic fetch failed ({e}), falling back to static", file=sys.stderr)
        return fetch_url(url, timeout)


# ---------------------------------------------------------------------------
# Self-correcting scrape with recovery strategies
# ---------------------------------------------------------------------------

def scrape_with_recovery(url: str, source_doc: dict | None = None, timeout: int = 30) -> tuple[str, dict]:
    """Try multiple scraping strategies with error recovery.

    Strategy cascade:
    1. Static fetch with default UA
    2. Static fetch with alternate UA
    3. Dynamic fetch via Selenium
    Handles: 403/429/5xx errors, empty responses, timeouts.

    Returns (html, metadata) or raises on complete failure.
    """
    import random
    import time as _time

    errors = []

    # Strategy 1: Normal static fetch
    try:
        html, meta = fetch_url(url, timeout)
        if html and len(html) > 200:
            return html, meta
        errors.append("Response too short")
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        errors.append(f"HTTP {status}")
        if status == 429:
            # Rate limited — back off
            _time.sleep(5)
    except requests.RequestException as e:
        errors.append(str(e))

    # Strategy 2: Alternate User-Agent
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS[1:]) if len(USER_AGENTS) > 1 else USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.5",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        if resp.text and len(resp.text) > 200:
            meta = {
                "http_status": resp.status_code,
                "response_time_ms": int(resp.elapsed.total_seconds() * 1000),
                "content_length": len(resp.content),
                "final_url": resp.url,
                "scrape_method": "static_retry",
            }
            return resp.text, meta
        errors.append("Alternate UA response too short")
    except Exception as e:
        errors.append(f"Alternate UA: {e}")

    # Strategy 3: Dynamic fetch (Selenium)
    try:
        html, meta = fetch_url_dynamic(url, timeout)
        if html and len(html) > 200:
            # If dynamic worked, suggest switching this source to dynamic
            if source_doc and source_doc.get("scrape_method") != "dynamic":
                try:
                    db.sources().update_one(
                        {"_id": source_doc["_id"]},
                        {"$set": {"scrape_method": "dynamic"}},
                    )
                    print(f"[scrape] Auto-switched source to dynamic: {url}", file=sys.stderr)
                except Exception:
                    pass
            return html, meta
        errors.append("Dynamic fetch returned empty")
    except Exception as e:
        errors.append(f"Dynamic: {e}")

    # All strategies failed
    raise requests.RequestException(
        f"All scrape strategies failed for {url}: {'; '.join(errors)}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_and_store(
    url: str,
    source_id: str | None = None,
    competitor_id: str | None = None,
    html_from_stdin: bool = False,
    page_type: str = "other",
) -> ScrapeResult:
    """Scrape a URL, extract content, and store snapshot in MongoDB."""

    # Get HTML — choose fetch strategy based on source config
    metadata: dict = {}
    if html_from_stdin:
        raw_html = sys.stdin.read()
        metadata = {"scrape_method": "dynamic", "source": "stdin"}
    else:
        # Check if source is configured for dynamic scraping
        source_doc = None
        if source_id:
            source_doc = db.get_source_by_id(source_id)

        scrape_method = "static"
        if source_doc:
            scrape_method = source_doc.get("scrape_method", "static")

        if scrape_method == "dynamic":
            raw_html, metadata = fetch_url_dynamic(url)
        else:
            raw_html, metadata = fetch_url(url)

    # Extract content
    extracted_text = extract_text(raw_html)
    structured_data = extract_structured_data(raw_html, page_type)

    # Compute content hash (on extracted text, not raw HTML — ignores style changes)
    content_hash = xxhash.xxh64(extracted_text.encode()).hexdigest()

    # Check if content changed from previous snapshot
    has_change = False
    if source_id:
        prev = db.get_latest_snapshot(source_id)
        if prev:
            has_change = prev.get("content_hash") != content_hash
        else:
            has_change = True  # First snapshot for this source

    # Resolve competitor_id from source if not provided
    if not competitor_id and source_id:
        source_doc = db.get_source_by_id(source_id)
        if source_doc:
            competitor_id = source_doc.get("competitor_id", "")

    # Build snapshot document
    now = datetime.now(timezone.utc)
    snapshot_doc = {
        "_id": str(__import__("bson").ObjectId()),
        "source_id": source_id or "",
        "competitor_id": competitor_id or "",
        "url": url,
        "scraped_at": now,
        "content_hash": content_hash,
        "raw_html": raw_html,
        "extracted_text": extracted_text,
        "structured_data": structured_data,
        "metadata": metadata,
        "has_change": has_change,
        "created_at": now,
    }

    # Store in MongoDB
    snapshot_id = db.save_snapshot(snapshot_doc)

    # Update source tracking
    if source_id:
        db.update_source_scrape_time(source_id)
        db.reset_source_failures(source_id)
        if has_change:
            db.sources().update_one(
                {"_id": source_id},
                {"$set": {"last_changed_at": now}},
            )

    # Build preview (first 500 chars of extracted text)
    preview = extracted_text[:500] + ("..." if len(extracted_text) > 500 else "")

    return ScrapeResult(
        snapshot_id=snapshot_id,
        content_hash=content_hash,
        has_change=has_change,
        extracted_text_preview=preview,
        url=url,
    )


def main():
    parser = argparse.ArgumentParser(description="Scrape a URL and store snapshot")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--source-id", help="MongoDB source document ID")
    parser.add_argument("--competitor-id", help="MongoDB competitor document ID")
    parser.add_argument("--page-type", default="other", help="Page type for structured extraction")
    parser.add_argument("--stdin", action="store_true", help="Read HTML from stdin")
    args = parser.parse_args()

    try:
        result = scrape_and_store(
            url=args.url,
            source_id=args.source_id,
            competitor_id=args.competitor_id,
            html_from_stdin=args.stdin,
            page_type=args.page_type,
        )
        print(json.dumps(result.model_dump(), indent=2))
    except (requests.RequestException, Exception) as e:
        # On errors, increment failure count and auto-disable if threshold reached
        if args.source_id:
            db.increment_source_failures(args.source_id)
            # Check if source should be auto-disabled
            source_doc = db.get_source_by_id(args.source_id)
            if source_doc:
                failures = source_doc.get("consecutive_failures", 0) + 1
                if failures >= 10:
                    db.disable_source(args.source_id)
                    print(json.dumps({
                        "warning": f"Source auto-disabled after {failures} consecutive failures",
                        "source_id": args.source_id,
                        "url": args.url,
                    }), file=sys.stderr)
                elif failures >= 3:
                    print(json.dumps({
                        "warning": f"Source has {failures} consecutive failures (auto-disables at 10)",
                        "source_id": args.source_id,
                        "url": args.url,
                    }), file=sys.stderr)
        error_result = ScrapeResult(
            snapshot_id="",
            content_hash="",
            has_change=False,
            url=args.url,
            error=str(e),
        )
        print(json.dumps(error_result.model_dump(), indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()