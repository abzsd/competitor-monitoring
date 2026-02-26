#!/usr/bin/env python3
"""Aggregate and score news sentiment for competitors.

Usage:
    python3 analyze_sentiment.py --competitor <slug>    # Analyze one competitor
    python3 analyze_sentiment.py --all                  # Analyze all competitors
    python3 analyze_sentiment.py --text "<text>" --competitor-id <id>
    python3 analyze_sentiment.py --competitor <slug> --no-llm  # Keyword-only

Uses keyword-based scoring as foundation, enhanced with Claude LLM analysis
when available for nuanced understanding of article sentiment.

Output:
    JSON with sentiment summary per competitor.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import feedparser
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import llm

# ---------------------------------------------------------------------------
# Sentiment lexicon (lightweight keyword approach)
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "growth", "growing", "raised", "funding", "launch", "launched", "innovative",
    "innovation", "award", "winning", "milestone", "expansion", "expanded",
    "partnership", "success", "successful", "revenue", "profit", "profitable",
    "record", "breakthrough", "leading", "leader", "best", "top", "trusted",
    "momentum", "adoption", "popular", "praised", "upgrade", "improved",
    "doubled", "tripled", "surpass", "exceeded", "exceeded", "outperformed",
    "unicorn", "ipo", "valuation",
}

NEGATIVE_WORDS = {
    "layoff", "layoffs", "fired", "downsizing", "struggling", "decline",
    "declined", "loss", "losses", "lawsuit", "sued", "breach", "hack",
    "hacked", "vulnerability", "outage", "downtime", "failure", "failed",
    "criticism", "criticized", "controversy", "controversial", "scandal",
    "bankruptcy", "shutting down", "shutdown", "pivot", "pivoting", "debt",
    "cut", "cuts", "reduction", "restructuring", "delayed", "delays",
    "bug", "bugs", "broken", "complaint", "complaints", "exodus",
}

OPPORTUNITY_SIGNALS = {
    "layoff", "layoffs", "downsizing", "struggling", "outage", "downtime",
    "breach", "hack", "controversy", "shutdown", "complaint", "exodus",
    "price increase", "raised prices", "expensive", "overpriced",
}


def score_text(text: str) -> dict:
    """Score a text snippet for sentiment.

    Returns {positive_count, negative_count, score, opportunity_signals}.
    """
    words = set(re.findall(r"\b[a-z]+\b", text.lower()))

    positive_hits = words & POSITIVE_WORDS
    negative_hits = words & NEGATIVE_WORDS
    opportunity_hits = words & OPPORTUNITY_SIGNALS

    pos = len(positive_hits)
    neg = len(negative_hits)
    total = pos + neg

    if total == 0:
        score = 0.0
    else:
        score = (pos - neg) / total  # Range: -1.0 to 1.0

    return {
        "positive_count": pos,
        "negative_count": neg,
        "score": round(score, 2),
        "positive_words": sorted(positive_hits),
        "negative_words": sorted(negative_hits),
        "opportunity_signals": sorted(opportunity_hits),
    }


# ---------------------------------------------------------------------------
# News fetching
# ---------------------------------------------------------------------------

def fetch_news_rss(competitor_name: str, limit: int = 20) -> list[dict]:
    """Fetch recent news from Google News RSS for a competitor."""
    articles = []
    try:
        query = requests.utils.quote(competitor_name)
        feed_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:limit]:
            articles.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", ""),
                "summary": entry.get("summary", ""),
            })
    except Exception:
        pass

    return articles


# ---------------------------------------------------------------------------
# LLM-enhanced sentiment
# ---------------------------------------------------------------------------

_use_llm = True


def analyze_article_llm(title: str, summary: str, competitor_name: str) -> dict | None:
    """Use Claude to analyze an article's sentiment with nuance.

    Returns dict with score, label, signals, opportunities, threats, or None on failure.
    """
    if not _use_llm or not llm.is_available():
        return None

    prompt = """Analyze this news article about a competitor. Return a JSON object with:
- "score": float from -1.0 (very negative) to 1.0 (very positive)
- "label": "positive", "negative", or "neutral"
- "key_signals": array of 1-3 key signals (e.g., "Series C funding", "layoffs", "product launch")
- "opportunities": array of 0-2 opportunities this creates for us
- "threats": array of 0-2 threats this poses to us

Be objective. Consider both explicit statements and implications."""

    context = f"Competitor: {competitor_name}\nHeadline: {title}\nSummary: {summary}"
    return llm.analyze(prompt, context, model=llm.FAST_MODEL, max_tokens=500)


# ---------------------------------------------------------------------------
# Sentiment analysis pipeline
# ---------------------------------------------------------------------------

def analyze_competitor_sentiment(competitor_doc: dict) -> dict:
    """Analyze news sentiment for a single competitor."""
    name = competitor_doc["name"]
    articles = fetch_news_rss(name)

    article_sentiments = []
    overall_positive = 0
    overall_negative = 0
    all_opportunity_signals = []
    llm_opportunities = []
    llm_threats = []

    for article in articles:
        text = f"{article['title']} {article.get('summary', '')}"

        # Try LLM analysis first, fall back to keyword-based
        llm_result = analyze_article_llm(article["title"], article.get("summary", ""), name)

        if llm_result and "score" in llm_result:
            score = float(llm_result["score"])
            pos = 1 if score > 0 else 0
            neg = 1 if score < 0 else 0
            overall_positive += pos
            overall_negative += neg

            signals = llm_result.get("key_signals", [])
            llm_opportunities.extend(llm_result.get("opportunities", []))
            llm_threats.extend(llm_result.get("threats", []))

            article_sentiments.append({
                "title": article["title"],
                "url": article["url"],
                "source": article.get("source", ""),
                "published": article.get("published", ""),
                "sentiment_score": round(score, 2),
                "key_signals": signals,
                "analysis_method": "llm",
            })
        else:
            # Keyword-based fallback
            sentiment = score_text(text)
            overall_positive += sentiment["positive_count"]
            overall_negative += sentiment["negative_count"]
            all_opportunity_signals.extend(sentiment["opportunity_signals"])

            article_sentiments.append({
                "title": article["title"],
                "url": article["url"],
                "source": article.get("source", ""),
                "published": article.get("published", ""),
                "sentiment_score": sentiment["score"],
                "positive_words": sentiment["positive_words"],
                "negative_words": sentiment["negative_words"],
                "analysis_method": "keyword",
            })

    # Sort: most negative first (opportunities), then most positive (threats)
    article_sentiments.sort(key=lambda x: x["sentiment_score"])

    total = overall_positive + overall_negative
    overall_score = round((overall_positive - overall_negative) / max(total, 1), 2)

    if overall_score > 0.3:
        sentiment_label = "positive"
    elif overall_score < -0.3:
        sentiment_label = "negative"
    else:
        sentiment_label = "neutral"

    result = {
        "competitor_name": name,
        "competitor_slug": competitor_doc.get("slug", ""),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "articles_analyzed": len(articles),
        "overall_sentiment": {
            "score": overall_score,
            "label": sentiment_label,
            "positive_signals": overall_positive,
            "negative_signals": overall_negative,
        },
        "opportunity_signals": sorted(set(all_opportunity_signals)),
        "top_negative_articles": [
            a for a in article_sentiments if a["sentiment_score"] < 0
        ][:5],
        "top_positive_articles": [
            a for a in article_sentiments if a["sentiment_score"] > 0
        ][:5],
        "all_articles": article_sentiments,
    }

    if llm_opportunities:
        result["llm_opportunities"] = list(set(llm_opportunities))
    if llm_threats:
        result["llm_threats"] = list(set(llm_threats))

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze competitor news sentiment")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Analyze all competitors")
    group.add_argument("--competitor", help="Competitor slug")
    group.add_argument("--text", help="Score arbitrary text")
    parser.add_argument("--competitor-id", help="Competitor ID (with --text)")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM, use keyword scoring only")
    args = parser.parse_args()

    global _use_llm
    if args.no_llm:
        _use_llm = False

    try:
        if args.text:
            result = score_text(args.text)
            print(json.dumps(result, indent=2))
            return

        results = []

        if args.competitor:
            comp = db.get_competitor_by_slug(args.competitor)
            if not comp:
                print(json.dumps({"error": f"Competitor not found: {args.competitor}"}), file=sys.stderr)
                sys.exit(1)
            results.append(analyze_competitor_sentiment(comp))
        else:  # --all
            for comp in db.get_all_active_competitors():
                results.append(analyze_competitor_sentiment(comp))

        print(json.dumps(results, indent=2, default=str))

        # Summary to stderr
        for r in results:
            s = r["overall_sentiment"]
            emoji = {"positive": "📈", "negative": "📉", "neutral": "➡️"}[s["label"]]
            print(
                f"{emoji} {r['competitor_name']}: {s['label']} (score={s['score']}, "
                f"{r['articles_analyzed']} articles, "
                f"{len(r['opportunity_signals'])} opportunity signals)",
                file=sys.stderr,
            )

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
