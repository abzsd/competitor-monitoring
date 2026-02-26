"""Request / response Pydantic models for the dashboard API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------

class CompetitorCreate(BaseModel):
    name: str
    slug: str = ""
    domain: str
    industry: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class CompetitorOut(BaseModel):
    id: str = Field(alias="_id")
    name: str
    slug: str
    domain: str
    industry: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_count: int = 0
    recent_change_count: int = 0

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class SourceCreate(BaseModel):
    competitor_id: str
    url: str
    page_type: str = "other"
    scrape_method: str = "static"
    schedule_group: str = "daily"


class SourceUpdate(BaseModel):
    page_type: Optional[str] = None
    scrape_method: Optional[str] = None
    schedule_group: Optional[str] = None
    is_active: Optional[bool] = None


class SourceOut(BaseModel):
    id: str = Field(alias="_id")
    competitor_id: str = ""
    competitor_name: str = ""
    url: str = ""
    page_type: str = ""
    scrape_method: str = ""
    schedule_group: str = ""
    discovery_method: str = ""
    is_active: bool = True
    last_scraped_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    consecutive_failures: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

class ChangeOut(BaseModel):
    id: str = Field(alias="_id")
    source_id: str = ""
    competitor_id: str = ""
    competitor_name: str = ""
    source_url: str = ""
    detected_at: Optional[datetime] = None
    change_type: str = ""
    severity: str = ""
    summary: str = ""
    is_analyzed: bool = False
    is_alerted: bool = False
    created_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class ChangeDetailOut(ChangeOut):
    text_diff: str = ""
    structured_diff: dict[str, Any] = Field(default_factory=dict)
    snapshot_before_id: str = ""
    snapshot_after_id: str = ""
    analysis_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

class AnalysisOut(BaseModel):
    id: str = Field(alias="_id")
    competitor_id: str = ""
    competitor_name: str = ""
    change_ids: list[str] = Field(default_factory=list)
    analysis_type: str = ""
    generated_at: Optional[datetime] = None
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertOut(BaseModel):
    id: str = Field(alias="_id")
    analysis_id: Optional[str] = None
    change_ids: list[str] = Field(default_factory=list)
    competitor_id: str = ""
    competitor_name: str = ""
    channel: str = ""
    severity: str = ""
    subject: str = ""
    body: str = ""
    sent_at: Optional[datetime] = None
    status: str = ""
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Partnerships
# ---------------------------------------------------------------------------

class PartnershipOut(BaseModel):
    id: str = Field(alias="_id")
    competitor_id: str = ""
    competitor_name: str = ""
    partner_name: str = ""
    partnership_type: str = ""
    source_url: str = ""
    discovered_at: Optional[datetime] = None
    description: str = ""
    confidence: float = 0.0
    status: str = ""
    created_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class CompetitorActivity(BaseModel):
    name: str
    slug: str
    activity_score: float = 0.0
    source_count: int = 0
    change_count_7d: int = 0


class DashboardStats(BaseModel):
    total_competitors: int = 0
    total_sources: int = 0
    active_sources: int = 0
    failing_sources: int = 0
    total_changes_7d: int = 0
    total_changes_30d: int = 0
    changes_by_severity: dict[str, int] = Field(default_factory=dict)
    changes_by_type: dict[str, int] = Field(default_factory=dict)
    alerts_last_24h: int = 0
    recent_changes: list[ChangeOut] = Field(default_factory=list)
    recent_alerts: list[AlertOut] = Field(default_factory=list)
    competitor_activity: list[CompetitorActivity] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
