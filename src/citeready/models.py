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


class Evidence(Model):
    """Exact source material supporting a later audit conclusion."""

    page_url: str
    exact_text: str
    source_type: str
    context: str | None = None


class DiscoverabilityFinding(Model):
    """An evidence-backed discoverability issue with no score attached."""

    title: str
    severity: Severity
    evidence: list[Evidence] = Field(default_factory=list)
    affected_url: str
    why_it_matters: str
    recommended_fix: str
    copy_paste_fix: str | None = None


class ResourceFetch(Model):
    """A bounded text resource retrieved for discoverability analysis."""

    requested_url: str
    final_url: str | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    text: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    error: str | None = None


class BotAccess(str, Enum):
    """Effective access for one crawler user agent under robots.txt."""

    ALLOWED = "Allowed"
    BLOCKED = "Blocked"
    UNKNOWN = "Unknown"


class BotAccessResult(Model):
    """The applicable robots directives and effective root-path access for a bot."""

    bot_name: str
    access: BotAccess
    is_explicit_rule: bool = False
    directives: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class RobotsTxtAnalysis(Model):
    """Structured results from a robots.txt inspection."""

    url: str
    found: bool
    status_code: int | None = None
    bot_access: list[BotAccessResult] = Field(default_factory=list)
    sitemap_urls: list[str] = Field(default_factory=list)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class SitemapDocument(Model):
    """One sitemap document inspected by the sitemap analyzer."""

    url: str
    status_code: int | None = None
    is_index: bool = False
    url_count: int = Field(default=0, ge=0)
    parsed: bool = False
    error: str | None = None


class SitemapAnalysisStatus(str, Enum):
    """Whether sitemap URL coverage is complete, partial, unavailable, or invalid."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class SkippedSitemapFile(Model):
    """A sitemap that was discovered but intentionally not parsed."""

    url: str
    reason: str
    status_code: int | None = Field(default=None, ge=100, le=599)


class SitemapAnalysis(Model):
    """Structured sitemap coverage result with explicit completeness metadata."""

    status: SitemapAnalysisStatus
    found: bool
    discovered_sitemap_files: list[str] = Field(default_factory=list)
    successfully_parsed_sitemap_files: list[str] = Field(default_factory=list)
    skipped_sitemap_files: list[SkippedSitemapFile] = Field(default_factory=list)
    parsed_url_count: int = Field(default=0, ge=0)
    url_count_is_complete: bool
    documents: list[SitemapDocument] = Field(default_factory=list)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class CanonicalState(str, Enum):
    """Canonical relationship for an audited page."""

    SELF = "self"
    INTERNAL_OTHER = "internal_other"
    EXTERNAL = "external"
    MISSING = "missing"


class CanonicalPageResult(Model):
    """Canonical result for one crawled page."""

    page_url: str
    canonical_url: str | None = None
    state: CanonicalState


class CanonicalAnalysis(Model):
    """Canonical-tag results across all crawled HTML pages."""

    pages: list[CanonicalPageResult] = Field(default_factory=list)
    missing_page_urls: list[str] = Field(default_factory=list)
    external_canonical_page_urls: list[str] = Field(default_factory=list)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class NoindexPage(Model):
    """A page carrying one or more noindex-equivalent meta directives."""

    page_url: str
    directives: dict[str, str]


class MetaRobotsAnalysis(Model):
    """Meta robots directives found in the crawled page set."""

    checked_page_count: int = Field(ge=0)
    noindex_pages: list[NoindexPage] = Field(default_factory=list)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class LlmsTxtAnalysis(Model):
    """Availability result for the optional llms.txt convention."""

    url: str
    found: bool
    status_code: int | None = None
    line_count: int = Field(default=0, ge=0)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class DiscoverabilityAnalysis(Model):
    """The unscored aggregate of all Phase 2 discoverability analyzers."""

    robots_txt: RobotsTxtAnalysis
    sitemap: SitemapAnalysis
    canonical: CanonicalAnalysis
    meta_robots: MetaRobotsAnalysis
    llms_txt: LlmsTxtAnalysis
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class CrawlResult(Model):
    """The complete output of a bounded crawl."""

    requested_url: str
    analyzed_url: str
    pages: list[CrawledPage] = Field(default_factory=list)
    warnings: list[CrawlWarning] = Field(default_factory=list)
    discoverability: DiscoverabilityAnalysis | None = None
    max_pages: int = Field(ge=1, le=12)
    started_at: datetime
    completed_at: datetime


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
