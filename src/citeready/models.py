"""Typed data contracts shared by the crawler and later audit phases."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditCategory(str, Enum):
    """The four transparent GEO audit categories."""

    DISCOVERABILITY = "AI Discoverability"
    CITATION_READINESS = "Citation Readiness"
    ENTITY_TRUST = "Entity and Trust"
    ANSWERABILITY = "AI Answerability"


class Severity(str, Enum):
    """Business-readable urgency levels for findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AnswerStatus(str, Enum):
    """Evidence-based outcome for an important customer question."""

    CLEARLY_ANSWERED = "Clearly answered"
    PARTIALLY_ANSWERED = "Partially answered"
    NOT_ANSWERED = "Not answered"
    CONFLICTING_ANSWER = "Conflicting answer"


class Model(BaseModel):
    """Base model with predictable whitespace handling."""

    model_config = ConfigDict(str_strip_whitespace=True)


class CrawlWarning(Model):
    """A recoverable issue observed while collecting a website."""

    code: str
    message: str
    url: str | None = None


class Heading(Model):
    """A page heading in document order."""

    level: int = Field(ge=1, le=6)
    text: str


class CrawledPage(Model):
    """Server-rendered content and metadata extracted from one HTML page."""

    requested_url: str
    url: str
    status_code: int = Field(ge=100, le=599)
    redirect_chain: list[str] = Field(default_factory=list)
    content_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    headings: list[Heading] = Field(default_factory=list)
    text_content: str = ""
    canonical_url: str | None = None
    robots_meta: dict[str, str] = Field(default_factory=dict)
    json_ld: list[Any] = Field(default_factory=list)
    internal_links: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime


class CrawlResult(Model):
    """The complete output of a bounded crawl."""

    requested_url: str
    analyzed_url: str
    pages: list[CrawledPage] = Field(default_factory=list)
    warnings: list[CrawlWarning] = Field(default_factory=list)
    max_pages: int = Field(ge=1, le=12)
    started_at: datetime
    completed_at: datetime


class Evidence(Model):
    """Exact source material supporting a later audit conclusion."""

    page_url: str
    exact_text: str
    source_type: str
    context: str | None = None


class RuleResult(Model):
    """Transparent outcome for a single scoring rule."""

    rule_name: str
    maximum_points: float = Field(ge=0)
    earned_points: float = Field(ge=0)
    evidence: list[Evidence] = Field(default_factory=list)
    reason: str
    recommendation: str


class AuditFinding(Model):
    """A business-actionable issue backed by evidence."""

    title: str
    category: AuditCategory
    severity: Severity
    page_url: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    why_it_matters: str
    recommended_action: str
    copy_paste_fix: str | None = None
    estimated_impact: int = Field(ge=1, le=5)
    estimated_effort: int = Field(ge=1, le=5)
    priority_score: int = Field(ge=0, le=100)


class CategoryScore(Model):
    """A category total with its supporting rule-level results."""

    category: AuditCategory
    maximum_points: float = Field(ge=0)
    earned_points: float = Field(ge=0)
    rules: list[RuleResult] = Field(default_factory=list)


class PrioritizedRecommendation(Model):
    """A grouped remediation action for the later report."""

    action: str
    finding_titles: list[str] = Field(default_factory=list)
    estimated_impact: int = Field(ge=1, le=5)
    estimated_effort: int = Field(ge=1, le=5)
    priority_score: int = Field(ge=0, le=100)
    expected_outcome: str


class AnswerabilityResult(Model):
    """Evidence-backed answerability classification for one buyer question."""

    question: str
    status: AnswerStatus
    page_url: str | None = None
    supporting_text: str | None = None
    explanation: str


class FinalAuditReport(Model):
    """Top-level report contract; population arrives in later phases."""

    business_name: str | None = None
    analyzed_url: str
    crawl_result: CrawlResult
    category_scores: list[CategoryScore] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    recommendations: list[PrioritizedRecommendation] = Field(default_factory=list)
    answerability_results: list[AnswerabilityResult] = Field(default_factory=list)
    methodology: str = ""
