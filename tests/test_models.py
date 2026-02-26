"""Tests for models.py — Pydantic model validation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts"))

from models import (
    Analysis,
    AnalysisContent,
    Change,
    ChangeResult,
    ChangeType,
    Competitor,
    DiscoveredSource,
    PageType,
    Partnership,
    ScrapeResult,
    Severity,
    Snapshot,
    Source,
)


class TestCompetitor:
    def test_creates_with_defaults(self):
        c = Competitor(name="Acme", slug="acme", domain="acme.com")
        assert c.name == "Acme"
        assert c.is_active is True
        assert c.tags == []
        assert c.id is not None

    def test_custom_fields(self):
        c = Competitor(
            name="Acme", slug="acme", domain="acme.com",
            industry="saas", tags=["api", "tools"]
        )
        assert c.industry == "saas"
        assert len(c.tags) == 2


class TestSource:
    def test_creates_with_defaults(self):
        s = Source(competitor_id="comp_001", url="https://acme.com/pricing")
        assert s.page_type == PageType.OTHER
        assert s.scrape_method.value == "static"
        assert s.schedule_group.value == "daily"
        assert s.consecutive_failures == 0

    def test_custom_fields(self):
        s = Source(
            competitor_id="comp_001",
            url="https://acme.com/pricing",
            page_type=PageType.PRICING,
            schedule_group="hourly",
        )
        assert s.page_type == PageType.PRICING


class TestSnapshot:
    def test_creates_with_defaults(self):
        s = Snapshot(source_id="src_001", competitor_id="comp_001", url="https://acme.com")
        assert s.has_change is False
        assert s.content_hash == ""
        assert s.extracted_text == ""

    def test_serialization(self):
        s = Snapshot(
            source_id="src_001",
            competitor_id="comp_001",
            url="https://acme.com",
            content_hash="abc123",
            extracted_text="Hello world",
        )
        d = s.model_dump(by_alias=True)
        assert "_id" in d
        assert d["content_hash"] == "abc123"


class TestChange:
    def test_creates_with_defaults(self):
        c = Change(
            source_id="src_001",
            competitor_id="comp_001",
            snapshot_before_id="snap_001",
            snapshot_after_id="snap_002",
        )
        assert c.change_type == ChangeType.CONTENT_UPDATE
        assert c.severity == Severity.LOW
        assert c.is_analyzed is False
        assert c.is_alerted is False

    def test_enums_serialize(self):
        c = Change(
            source_id="src_001",
            competitor_id="comp_001",
            snapshot_before_id="snap_001",
            snapshot_after_id="snap_002",
            change_type=ChangeType.PRICING_CHANGE,
            severity=Severity.CRITICAL,
        )
        d = c.model_dump()
        assert d["change_type"] == "pricing_change"
        assert d["severity"] == "critical"


class TestAnalysis:
    def test_creates_with_defaults(self):
        a = Analysis(competitor_id="comp_001")
        assert a.analysis_type == "change_analysis"
        assert a.content.summary == ""

    def test_with_content(self):
        content = AnalysisContent(
            summary="Price raised",
            impact_assessment="Good for us",
            actionable_insights=["Update comparison page"],
            category="pricing",
            confidence=0.92,
        )
        a = Analysis(competitor_id="comp_001", content=content)
        assert a.content.confidence == 0.92
        assert len(a.content.actionable_insights) == 1


class TestPartnership:
    def test_creates_with_defaults(self):
        p = Partnership(competitor_id="comp_001", partner_name="BigCo")
        assert p.status.value == "rumored"
        assert p.confidence == 0.0


class TestScriptIOModels:
    def test_scrape_result(self):
        r = ScrapeResult(snapshot_id="snap_001", content_hash="abc", has_change=True, url="https://test.com")
        assert r.has_change is True
        assert r.error is None

    def test_scrape_result_with_error(self):
        r = ScrapeResult(snapshot_id="", content_hash="", has_change=False, url="https://test.com", error="timeout")
        assert r.error == "timeout"

    def test_change_result(self):
        r = ChangeResult(
            change_id="chg_001",
            source_url="https://test.com",
            competitor_slug="acme",
            change_type=ChangeType.PRICING_CHANGE,
            severity=Severity.HIGH,
            summary="Price changed",
        )
        assert r.severity == Severity.HIGH

    def test_discovered_source(self):
        d = DiscoveredSource(
            url="https://acme.com/new-page",
            suggested_page_type=PageType.PRODUCT,
            discovery_method="sitemap",
        )
        assert d.suggested_page_type == PageType.PRODUCT
