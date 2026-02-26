"""Pydantic models for the Competitor Monitoring system.

These models define the data shapes for MongoDB documents, script I/O,
and structured analysis output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_object_id() -> str:
    return str(ObjectId())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PageType(str, Enum):
    PRICING = "pricing"
    PRODUCT = "product"
    TECH_STACK = "tech_stack"
    PARTNERSHIPS = "partnerships"
    BLOG = "blog"
    NEWS = "news"
    CHANGELOG = "changelog"
    CAREERS = "careers"
    LANDING = "landing"
    OTHER = "other"


class ScrapeMethod(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"


class ScheduleGroup(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class DiscoveryMethod(str, Enum):
    MANUAL = "manual"
    SITEMAP = "sitemap"
    CRAWL = "crawl"
    NEWS = "news"


class ChangeType(str, Enum):
    PRICING_CHANGE = "pricing_change"
    PRODUCT_UPDATE = "product_update"
    TECH_STACK_CHANGE = "tech_stack_change"
    PARTNERSHIP_NEW = "partnership_new"
    CONTENT_UPDATE = "content_update"
    PAGE_ADDED = "page_added"
    PAGE_REMOVED = "page_removed"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PartnershipType(str, Enum):
    INTEGRATION = "integration"
    RESELLER = "reseller"
    STRATEGIC = "strategic"
    ACQUISITION = "acquisition"
    INVESTMENT = "investment"


class PartnershipStatus(str, Enum):
    RUMORED = "rumored"
    CONFIRMED = "confirmed"
    DEPRECATED = "deprecated"


class AlertChannel(str, Enum):
    SLACK = "slack"


class AlertStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


# ---------------------------------------------------------------------------
# Document Models
# ---------------------------------------------------------------------------

class Competitor(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    name: str
    slug: str
    domain: str
    industry: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


class Source(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    competitor_id: str
    url: str
    page_type: PageType = PageType.OTHER
    scrape_method: ScrapeMethod = ScrapeMethod.STATIC
    scrape_config: dict[str, Any] = Field(default_factory=dict)
    schedule_group: ScheduleGroup = ScheduleGroup.DAILY
    discovery_method: DiscoveryMethod = DiscoveryMethod.MANUAL
    is_active: bool = True
    last_scraped_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    consecutive_failures: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


class Snapshot(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    source_id: str
    competitor_id: str
    url: str
    scraped_at: datetime = Field(default_factory=utcnow)
    content_hash: str = ""
    raw_html: str = ""
    extracted_text: str = ""
    structured_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    has_change: bool = False
    created_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


class StructuredDiff(BaseModel):
    changed: list[dict[str, Any]] = Field(default_factory=list)
    added: list[dict[str, Any]] = Field(default_factory=list)
    removed: list[dict[str, Any]] = Field(default_factory=list)


class Change(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    source_id: str
    competitor_id: str
    snapshot_before_id: str
    snapshot_after_id: str
    detected_at: datetime = Field(default_factory=utcnow)
    change_type: ChangeType = ChangeType.CONTENT_UPDATE
    severity: Severity = Severity.LOW
    summary: str = ""
    text_diff: str = ""
    structured_diff: StructuredDiff = Field(default_factory=StructuredDiff)
    is_analyzed: bool = False
    analysis_id: Optional[str] = None
    is_alerted: bool = False
    created_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


class AnalysisContent(BaseModel):
    """Structured output from the agent's analysis."""
    summary: str = ""
    impact_assessment: str = ""
    actionable_insights: list[str] = Field(default_factory=list)
    category: str = ""
    confidence: float = 0.0


class Analysis(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    competitor_id: str
    change_ids: list[str] = Field(default_factory=list)
    analysis_type: str = "change_analysis"
    generated_at: datetime = Field(default_factory=utcnow)
    content: AnalysisContent = Field(default_factory=AnalysisContent)
    raw_response: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


class Partnership(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    competitor_id: str
    partner_name: str
    partnership_type: PartnershipType = PartnershipType.INTEGRATION
    source_url: str = ""
    discovered_at: datetime = Field(default_factory=utcnow)
    first_seen_snapshot_id: Optional[str] = None
    description: str = ""
    confidence: float = 0.0
    status: PartnershipStatus = PartnershipStatus.RUMORED
    analysis_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


class Alert(BaseModel):
    id: str = Field(default_factory=new_object_id, alias="_id")
    analysis_id: Optional[str] = None
    change_ids: list[str] = Field(default_factory=list)
    competitor_id: str
    channel: AlertChannel = AlertChannel.SLACK
    severity: Severity = Severity.MEDIUM
    subject: str = ""
    body: str = ""
    sent_at: Optional[datetime] = None
    status: AlertStatus = AlertStatus.SENT
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Script I/O Models
# ---------------------------------------------------------------------------

class ScrapeResult(BaseModel):
    """Output from scrape.py."""
    snapshot_id: str
    content_hash: str
    has_change: bool
    extracted_text_preview: str = ""
    url: str = ""
    error: Optional[str] = None


class ChangeResult(BaseModel):
    """Single change output from detect_changes.py."""
    change_id: str
    source_url: str
    competitor_slug: str
    change_type: ChangeType
    severity: Severity
    summary: str
    text_diff_preview: str = ""


class DiscoveredSource(BaseModel):
    """Output from discover_sources.py."""
    url: str
    suggested_page_type: PageType
    discovery_method: DiscoveryMethod
    context: str = ""  # anchor text or surrounding context
