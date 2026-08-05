"""Typed data contracts shared by the crawler and later audit phases."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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


class Confidence(str, Enum):
    """Confidence in a deterministic finding, not a quality score."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


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


class ContentBlock(Model):
    """A meaningful HTML content element retained in document order."""

    kind: str
    text: str
    heading_level: int | None = Field(default=None, ge=1, le=6)
    links: list[str] = Field(default_factory=list)


class FreshnessSignal(Model):
    """A date or copyright signal extracted without judging its recency."""

    value: str
    source_type: str
    evidence: str


class ExternalLinkSignal(Model):
    """Visible link context used for conservative social-profile classification."""

    url: str
    anchor_text: str = ""
    rel_values: list[str] = Field(default_factory=list)
    aria_label: str | None = None
    location: str | None = None
    in_social_area: bool = False


class CrawledPage(Model):
    """Server-rendered content and metadata extracted from one HTML page."""

    requested_url: str
    url: str
    status_code: int = Field(ge=100, le=599)
    redirect_chain: list[str] = Field(default_factory=list)
    content_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    open_graph: dict[str, str] = Field(default_factory=dict)
    headings: list[Heading] = Field(default_factory=list)
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    text_content: str = ""
    footer_text: str = ""
    visible_addresses: list[str] = Field(default_factory=list)
    image_alt_text: list[str] = Field(default_factory=list)
    has_contact_form: bool = False
    author_links: list[str] = Field(default_factory=list)
    canonical_url: str | None = None
    robots_meta: dict[str, str] = Field(default_factory=dict)
    json_ld: list[Any] = Field(default_factory=list)
    internal_links: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)
    external_link_signals: list[ExternalLinkSignal] = Field(default_factory=list)
    freshness_signals: list[FreshnessSignal] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime


class Evidence(Model):
    """Exact source material supporting a later audit conclusion."""

    model_config = ConfigDict(str_strip_whitespace=False)

    page_url: str
    exact_text: str
    source_type: str
    context: str | None = None


class FindingStatus(str, Enum):
    """Lifecycle state for an evidence-backed finding."""

    DETECTED = "detected"


class DiscoverabilityFinding(Model):
    """The shared, unscored contract for every analyzer finding."""

    id: str = Field(default_factory=lambda: f"disc-{uuid4().hex}")
    category: AuditCategory = AuditCategory.DISCOVERABILITY
    title: str
    severity: Severity
    confidence: Confidence = Confidence.MEDIUM
    status: FindingStatus = FindingStatus.DETECTED
    affected_url: str
    evidence: list[Evidence] = Field(default_factory=list)
    why_it_matters: str
    recommendation: str = Field(
        validation_alias=AliasChoices("recommendation", "recommended_fix"),
    )
    copy_paste_fix: str | None = None
    # Deliberately unestimated until the scoring and prioritization phase.
    impact: int | None = Field(default=None, ge=1, le=5)
    effort: int | None = Field(default=None, ge=1, le=5)

    @property
    def recommended_fix(self) -> str:
        """Compatibility accessor for callers using the original Phase 2 name."""

        return self.recommendation


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


class DirectAnswerAssessment(Model):
    """Deterministic assessment of whether a page opening explains its topic."""

    is_strong: bool
    opening_excerpt: str
    reason: str


class FaqAssessment(Model):
    """Visible and structured FAQ signals found on one page."""

    has_faq_schema: bool
    faq_schema_evidence: list[str] = Field(default_factory=list)
    visible_faq_headings: list[str] = Field(default_factory=list)
    question_headings: list[str] = Field(default_factory=list)
    unanswered_question_headings: list[str] = Field(default_factory=list)


class CitationReadinessPageAnalysis(Model):
    """Unscored citation-readiness signals for one crawled page."""

    page_url: str
    heading_hierarchy: list[Heading] = Field(default_factory=list)
    direct_answer: DirectAnswerAssessment
    faq: FaqAssessment
    freshness_signals: list[FreshnessSignal] = Field(default_factory=list)


class CitationReadinessAnalysis(Model):
    """Aggregate output from the deterministic Citation Readiness analyzer."""

    pages: list[CitationReadinessPageAnalysis] = Field(default_factory=list)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class OrganizationStructuredData(Model):
    """One typed JSON-LD entity extracted exactly as published by a page."""

    page_url: str
    entity_type: str
    schema_types: list[str] = Field(default_factory=list)
    source_property: str | None = None
    name: str | None = None
    legal_name: str | None = None
    url: str | None = None
    logo: str | None = None
    description: str | None = None
    email: str | None = None
    telephone: str | None = None
    address: str | None = None
    location: str | None = None
    same_as: list[str] = Field(default_factory=list)
    founder: str | None = None
    founding_date: str | None = None


class EntityIdentitySignal(Model):
    """One bounded, page-level value that may identify the business."""

    page_url: str
    entity_type: str
    source_type: str
    value: str


class CompanyPageSignal(Model):
    """Availability and visible-content signal for a company or support page."""

    page_type: str
    url: str
    internally_linked: bool
    available: bool | None = None
    visible_word_count: int = Field(default=0, ge=0)
    has_meaningful_text: bool = False


class BusinessContactDetail(Model):
    """Public business contact detail retained for deterministic comparison."""

    detail_type: str
    value: str
    page_url: str
    source_type: str


class AuthorEditorialSignal(Model):
    """Attribution signals detected on one likely editorial page."""

    page_url: str
    is_editorial: bool
    visible_word_count: int = Field(default=0, ge=0)
    author_names: list[str] = Field(default_factory=list)
    author_links: list[str] = Field(default_factory=list)
    has_author_bio: bool = False
    roles_or_credentials: list[str] = Field(default_factory=list)
    publication_dates: list[str] = Field(default_factory=list)
    has_article_schema: bool = False
    has_person_schema: bool = False


class ExternalCredibilitySignal(Model):
    """Visible support context detected without verifying its truthfulness."""

    page_url: str
    outbound_citation_urls: list[str] = Field(default_factory=list)
    named_source_labels: list[str] = Field(default_factory=list)
    certifications_or_awards: list[str] = Field(default_factory=list)
    customer_logo_signals: list[str] = Field(default_factory=list)
    testimonial_signals: list[str] = Field(default_factory=list)
    case_study_signals: list[str] = Field(default_factory=list)


class TrustPolicySignal(Model):
    """One detected trust or policy page, linked or directly crawled."""

    policy_type: str
    url: str
    internally_linked: bool
    available: bool | None = None


class SocialProfileSignal(Model):
    """A known social or knowledge-graph profile published by the site."""

    network: str
    url: str
    page_url: str
    source_type: str
    relevance_signals: list[str] = Field(default_factory=list)


class EntityTrustAnalysis(Model):
    """Aggregate output from the deterministic Entity and Trust analyzer."""

    organization_data: list[OrganizationStructuredData] = Field(default_factory=list)
    person_entities: list[OrganizationStructuredData] = Field(default_factory=list)
    website_entities: list[OrganizationStructuredData] = Field(default_factory=list)
    article_entities: list[OrganizationStructuredData] = Field(default_factory=list)
    identity_signals: list[EntityIdentitySignal] = Field(default_factory=list)
    company_pages: list[CompanyPageSignal] = Field(default_factory=list)
    contact_details: list[BusinessContactDetail] = Field(default_factory=list)
    editorial_signals: list[AuthorEditorialSignal] = Field(default_factory=list)
    credibility_signals: list[ExternalCredibilitySignal] = Field(default_factory=list)
    trust_policy_pages: list[TrustPolicySignal] = Field(default_factory=list)
    social_profiles: list[SocialProfileSignal] = Field(default_factory=list)
    findings: list[DiscoverabilityFinding] = Field(default_factory=list)


class CrawlResult(Model):
    """The complete output of a bounded crawl."""

    requested_url: str
    analyzed_url: str
    pages: list[CrawledPage] = Field(default_factory=list)
    warnings: list[CrawlWarning] = Field(default_factory=list)
    discoverability: DiscoverabilityAnalysis | None = None
    citation_readiness: CitationReadinessAnalysis | None = None
    entity_trust: EntityTrustAnalysis | None = None
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
