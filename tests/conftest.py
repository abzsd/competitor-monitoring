"""Shared test fixtures for the Competitor Monitoring test suite."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_competitor():
    return {
        "_id": "comp_001",
        "name": "Acme Corp",
        "slug": "acme-corp",
        "domain": "acmecorp.com",
        "industry": "developer-tools",
        "description": "Primary competitor",
        "tags": ["api", "saas"],
        "is_active": True,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_source():
    return {
        "_id": "src_001",
        "competitor_id": "comp_001",
        "url": "https://acmecorp.com/pricing",
        "page_type": "pricing",
        "scrape_method": "static",
        "scrape_config": {},
        "schedule_group": "hourly",
        "discovery_method": "manual",
        "is_active": True,
        "last_scraped_at": None,
        "last_changed_at": None,
        "consecutive_failures": 0,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_html_v1():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Acme Corp Pricing</title>
    <meta name="description" content="Acme Corp pricing plans">
    </head>
    <body>
    <nav>Navigation here</nav>
    <main>
        <h1>Pricing Plans</h1>
        <div class="pricing-card">
            <h3 class="plan-name">Starter</h3>
            <div class="price">$29/mo</div>
            <ul>
                <li class="feature">5 users</li>
                <li class="feature">10GB storage</li>
            </ul>
        </div>
        <div class="pricing-card">
            <h3 class="plan-name">Pro</h3>
            <div class="price">$79/mo</div>
            <ul>
                <li class="feature">50 users</li>
                <li class="feature">100GB storage</li>
                <li class="feature">API access</li>
            </ul>
        </div>
    </main>
    <footer>Footer content</footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_v2():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Acme Corp Pricing</title>
    <meta name="description" content="Acme Corp pricing plans - Updated">
    </head>
    <body>
    <nav>Navigation here</nav>
    <main>
        <h1>Pricing Plans</h1>
        <div class="pricing-card">
            <h3 class="plan-name">Starter</h3>
            <div class="price">$29/mo</div>
            <ul>
                <li class="feature">5 users</li>
                <li class="feature">10GB storage</li>
            </ul>
        </div>
        <div class="pricing-card">
            <h3 class="plan-name">Pro</h3>
            <div class="price">$99/mo</div>
            <ul>
                <li class="feature">50 users</li>
                <li class="feature">100GB storage</li>
                <li class="feature">API access</li>
                <li class="feature">AI Features</li>
            </ul>
        </div>
        <div class="pricing-card">
            <h3 class="plan-name">Enterprise</h3>
            <div class="price">Contact us</div>
            <ul>
                <li class="feature">Unlimited users</li>
                <li class="feature">1TB storage</li>
            </ul>
        </div>
    </main>
    <footer>Footer content</footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_partnership_html():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Acme Corp Partners</title></head>
    <body>
    <main>
        <h1>Our Partners</h1>
        <p>We are excited to announce our new partnership with BigCo Inc
        to bring integrated solutions to enterprise customers.</p>
        <p>Acme Corp has also collaborated with CloudTech Solutions on
        a strategic alliance for cloud infrastructure.</p>
        <div class="partners">
            <img alt="BigCo Inc" src="/logos/bigco.png">
            <img alt="CloudTech Solutions" src="/logos/cloudtech.png">
            <img alt="DataFlow Systems" src="/logos/dataflow.png">
        </div>
    </main>
    </body>
    </html>
    """


@pytest.fixture
def sample_snapshot_v1(sample_html_v1):
    return {
        "_id": "snap_001",
        "source_id": "src_001",
        "competitor_id": "comp_001",
        "url": "https://acmecorp.com/pricing",
        "scraped_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
        "content_hash": "abc123",
        "raw_html": sample_html_v1,
        "extracted_text": "Pricing Plans\nStarter\n$29/mo\n5 users\n10GB storage\nPro\n$79/mo\n50 users\n100GB storage\nAPI access",
        "structured_data": {
            "plans": [
                {"name": "Starter", "price": "$29/mo", "features": ["5 users", "10GB storage"]},
                {"name": "Pro", "price": "$79/mo", "features": ["50 users", "100GB storage", "API access"]},
            ],
            "page_title": "Acme Corp Pricing",
        },
        "metadata": {"http_status": 200},
        "has_change": False,
        "created_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_snapshot_v2(sample_html_v2):
    return {
        "_id": "snap_002",
        "source_id": "src_001",
        "competitor_id": "comp_001",
        "url": "https://acmecorp.com/pricing",
        "scraped_at": datetime(2025, 6, 2, tzinfo=timezone.utc),
        "content_hash": "def456",
        "raw_html": sample_html_v2,
        "extracted_text": "Pricing Plans\nStarter\n$29/mo\n5 users\n10GB storage\nPro\n$99/mo\n50 users\n100GB storage\nAPI access\nAI Features\nEnterprise\nContact us\nUnlimited users\n1TB storage",
        "structured_data": {
            "plans": [
                {"name": "Starter", "price": "$29/mo", "features": ["5 users", "10GB storage"]},
                {"name": "Pro", "price": "$99/mo", "features": ["50 users", "100GB storage", "API access", "AI Features"]},
                {"name": "Enterprise", "price": "Contact us", "features": ["Unlimited users", "1TB storage"]},
            ],
            "page_title": "Acme Corp Pricing",
        },
        "metadata": {"http_status": 200},
        "has_change": True,
        "created_at": datetime(2025, 6, 2, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_change():
    return {
        "_id": "chg_001",
        "source_id": "src_001",
        "competitor_id": "comp_001",
        "snapshot_before_id": "snap_001",
        "snapshot_after_id": "snap_002",
        "detected_at": datetime(2025, 6, 2, tzinfo=timezone.utc),
        "change_type": "pricing_change",
        "severity": "high",
        "summary": "Pricing Change detected on pricing page: +5/-1 lines changed",
        "text_diff": "--- before\n+++ after\n-$79/mo\n+$99/mo\n+AI Features\n+Enterprise\n+Contact us",
        "structured_diff": {
            "changed": [{"path": "plans[1].price", "old_value": "$79/mo", "new_value": "$99/mo"}],
            "added": [{"path": "plans[2]", "value": "Enterprise plan"}],
            "removed": [],
        },
        "is_analyzed": False,
        "analysis_id": None,
        "is_alerted": False,
        "created_at": datetime(2025, 6, 2, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_analysis():
    return {
        "_id": "ana_001",
        "competitor_id": "comp_001",
        "change_ids": ["chg_001"],
        "analysis_type": "change_analysis",
        "generated_at": datetime(2025, 6, 2, tzinfo=timezone.utc),
        "content": {
            "summary": "Acme raised Pro plan from $79/mo to $99/mo and added Enterprise tier",
            "impact_assessment": "Price increase widens our competitive advantage in mid-market",
            "actionable_insights": [
                "Update comparison page to highlight price gap",
                "Target Acme Pro customers with migration offer",
            ],
            "category": "pricing",
            "confidence": 0.92,
        },
        "raw_response": "",
        "created_at": datetime(2025, 6, 2, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------------
# Mock DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Patch the db module to use in-memory dicts instead of MongoDB."""
    collections = {
        "competitors": {},
        "sources": {},
        "snapshots": {},
        "changes": {},
        "analyses": {},
        "partnerships": {},
        "alerts": {},
    }

    def mock_save(collection_name):
        def _save(doc):
            doc_id = doc.get("_id", str(len(collections[collection_name])))
            collections[collection_name][doc_id] = doc
            return doc_id
        return _save

    with patch("db.get_client") as mock_client, \
         patch("db.get_db") as mock_db_fn:
        mock_client.return_value = MagicMock()
        mock_db_fn.return_value = MagicMock()

        yield collections
