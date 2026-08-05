"""Configurable, evidence-aware rules for the transparent GEO score.

The values in ``DEFAULT_SCORING_RULES`` are the only point allocations.  Each
evaluator reports a quality ratio rather than an opaque score; the scoring
engine converts that ratio to the rule's configured maximum points.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .models import (
    AnswerStatus,
    AuditCategory,
    Confidence,
    CrawlResult,
    DiscoverabilityFinding,
    RuleScoreStatus,
    Severity,
    SitemapAnalysisStatus,
)


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """The completed deterministic analyses available to a rule."""

    result: CrawlResult


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    """An evaluator's evidence-backed quality result before points are assigned."""

    quality: float
    status: RuleScoreStatus
    reason: str
    findings: tuple[DiscoverabilityFinding, ...] = ()
    deduction_keys: tuple[str, ...] = ()
    evidence_available: bool = True


EvaluationFunction = Callable[[ScoringContext], RuleEvaluation]


# These policy caps are configuration, not hidden point deductions. A critical
# evidence-backed issue can use a full rule deduction; cosmetic evidence cannot.
SEVERITY_DEDUCTION_CAPS: dict[Severity, float] = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.75,
    Severity.MEDIUM: 0.5,
    Severity.LOW: 0.25,
    Severity.INFO: 0.0,
}
LOW_CONFIDENCE_MAX_DEDUCTION = 0.5


@dataclass(frozen=True, slots=True)
class ScoringRule:
    """One documented scoring rule and its configurable point allocation."""

    id: str
    category: AuditCategory
    title: str
    maximum_points: float
    evaluation_function: EvaluationFunction
    deduction_reason: str
    explanation: str


def _not_scored(reason: str) -> RuleEvaluation:
    """Unknown analysis data never creates a deduction."""

    return RuleEvaluation(
        quality=1.0,
        status=RuleScoreStatus.NOT_APPLICABLE,
        reason=reason,
        evidence_available=False,
    )


def _evaluation(
    quality: float,
    reason: str,
    *,
    findings: Iterable[DiscoverabilityFinding] = (),
    deduction_keys: Iterable[str] = (),
) -> RuleEvaluation:
    bounded = min(1.0, max(0.0, quality))
    status = (
        RuleScoreStatus.PASS
        if bounded == 1.0
        else RuleScoreStatus.FAIL
        if bounded == 0.0
        else RuleScoreStatus.PARTIAL
    )
    return RuleEvaluation(
        quality=bounded,
        status=status,
        reason=reason,
        findings=tuple(findings),
        deduction_keys=tuple(deduction_keys),
    )


def _findings(
    context: ScoringContext,
    category: AuditCategory,
    *needles: str,
) -> tuple[DiscoverabilityFinding, ...]:
    """Select only actual analyzer findings relevant to a specific rule."""

    all_findings: list[DiscoverabilityFinding] = []
    if category == AuditCategory.DISCOVERABILITY and context.result.discoverability:
        all_findings = context.result.discoverability.findings
    elif category == AuditCategory.CITATION_READINESS and context.result.citation_readiness:
        all_findings = context.result.citation_readiness.findings
    elif category == AuditCategory.ENTITY_TRUST and context.result.entity_trust:
        all_findings = context.result.entity_trust.findings
    elif category == AuditCategory.ANSWERABILITY and context.result.answerability:
        all_findings = context.result.answerability.findings

    normalized_needles = tuple(needle.lower() for needle in needles)
    return tuple(
        finding
        for finding in all_findings
        if any(needle in finding.title.lower() for needle in normalized_needles)
    )


def _finding_keys(prefix: str, findings: Iterable[DiscoverabilityFinding]) -> tuple[str, ...]:
    return tuple(f"{prefix}:{finding.id}" for finding in findings)


def _discoverability_robots(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.discoverability
    if not analysis:
        return _not_scored("Robots.txt analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.DISCOVERABILITY, "robots.txt")
    if analysis.robots_txt.found:
        return _evaluation(1, "robots.txt was retrieved successfully.")
    return _evaluation(
        0,
        "robots.txt was not retrieved from the site root.",
        findings=findings,
        deduction_keys=_finding_keys("robots", findings) or ("robots:missing",),
    )


def _discoverability_sitemap(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.discoverability
    if not analysis:
        return _not_scored("Sitemap analysis was unavailable, so this rule was not deducted.")
    sitemap = analysis.sitemap
    findings = _findings(context, AuditCategory.DISCOVERABILITY, "sitemap")
    if sitemap.status == SitemapAnalysisStatus.COMPLETE:
        return _evaluation(1, f"Sitemap coverage is complete ({sitemap.parsed_url_count} parsed URLs).")
    if sitemap.status == SitemapAnalysisStatus.PARTIAL:
        return _evaluation(
            0.5,
            "A sitemap was found but one or more sitemap files were intentionally skipped; URL coverage may be incomplete.",
            findings=findings,
            deduction_keys=_finding_keys("sitemap", findings) or ("sitemap:partial",),
        )
    return _evaluation(
        0,
        "No usable sitemap coverage was available.",
        findings=findings,
        deduction_keys=_finding_keys("sitemap", findings) or ("sitemap:unavailable",),
    )


def _discoverability_canonical(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.discoverability
    if not analysis:
        return _not_scored("Canonical analysis was unavailable, so this rule was not deducted.")
    canonical = analysis.canonical
    checked = len(canonical.pages)
    if not checked:
        return _not_scored("No crawled pages were available for canonical inspection.")
    issue_count = len(canonical.missing_page_urls) + len(canonical.external_canonical_page_urls)
    if not issue_count:
        return _evaluation(1, f"Canonical tags were acceptable on all {checked} crawled pages.")
    findings = _findings(context, AuditCategory.DISCOVERABILITY, "canonical")
    return _evaluation(
        1 - min(1, issue_count / checked),
        f"{issue_count} of {checked} crawled pages have a missing or external canonical URL.",
        findings=findings,
        deduction_keys=_finding_keys("canonical", findings) or ("canonical:coverage",),
    )


def _discoverability_meta_robots(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.discoverability
    if not analysis:
        return _not_scored("Meta robots analysis was unavailable, so this rule was not deducted.")
    meta_robots = analysis.meta_robots
    if not meta_robots.checked_page_count:
        return _not_scored("No crawled pages were available for meta robots inspection.")
    blocked = len(meta_robots.noindex_pages)
    if not blocked:
        return _evaluation(1, "No crawled pages carried a noindex directive.")
    findings = _findings(context, AuditCategory.DISCOVERABILITY, "noindex", "meta robots")
    return _evaluation(
        1 - min(1, blocked / meta_robots.checked_page_count),
        f"{blocked} crawled page(s) have a noindex-equivalent directive.",
        findings=findings,
        deduction_keys=_finding_keys("meta-robots", findings) or ("meta-robots:noindex",),
    )


def _discoverability_llms(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.discoverability
    if not analysis:
        return _not_scored("llms.txt analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.DISCOVERABILITY, "llms.txt")
    if analysis.llms_txt.found:
        return _evaluation(1, "llms.txt was retrieved successfully.")
    return _evaluation(
        0,
        "llms.txt was not found at the site root.",
        findings=findings,
        deduction_keys=_finding_keys("llms", findings) or ("llms:missing",),
    )


def _discoverability_bots(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.discoverability
    if not analysis or not analysis.robots_txt.bot_access:
        return _not_scored("No bot-access directives were available to score.")
    bot_access = analysis.robots_txt.bot_access
    allowed = sum(item.access.value == "Allowed" for item in bot_access)
    unknown = sum(item.access.value == "Unknown" for item in bot_access)
    quality = (allowed + (0.5 * unknown)) / len(bot_access)
    if quality == 1:
        return _evaluation(1, "All checked AI crawler user agents are allowed at the root path.")
    findings = _findings(context, AuditCategory.DISCOVERABILITY, "bot", "crawler")
    return _evaluation(
        quality,
        "One or more checked AI crawler user agents are blocked or have no explicit access signal.",
        findings=findings,
        deduction_keys=_finding_keys("bot-access", findings) or ("bot-access:root",),
    )


def _discoverability_homepage(context: ScoringContext) -> RuleEvaluation:
    pages = context.result.pages
    if not pages:
        return _not_scored("No crawled homepage content was available to score.")
    homepage = next((page for page in pages if page.url == context.result.analyzed_url), pages[0])
    visible_words = len(homepage.text_content.split())
    if homepage.status_code < 400 and (homepage.title or homepage.headings) and visible_words >= 20:
        return _evaluation(1, "The crawled homepage has a successful response, identifying metadata, and meaningful visible text.")
    return _evaluation(
        0,
        "The crawled homepage lacks enough successful, identifiable visible content for reliable discovery.",
        deduction_keys=("homepage:discovery",),
    )


def _citation_opening(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis or not analysis.pages:
        return _not_scored("No citation-readiness page openings were available to score.")
    strong = sum(page.direct_answer.is_strong for page in analysis.pages)
    total = len(analysis.pages)
    if strong == total:
        return _evaluation(1, f"All {total} crawled page openings clearly state their topic.")
    findings = _findings(context, AuditCategory.CITATION_READINESS, "opening does not")
    return _evaluation(
        strong / total,
        f"{total - strong} of {total} crawled page openings do not clearly state what the page is about.",
        findings=findings,
        deduction_keys=_finding_keys("citation-opening", findings) or ("citation-opening:clarity",),
    )


def _citation_headings(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis:
        return _not_scored("Heading analysis was unavailable, so this rule was not deducted.")
    findings = _findings(
        context,
        AuditCategory.CITATION_READINESS,
        "missing an h1",
        "multiple h1",
        "hierarchy skips",
        "generic headings",
    )
    if not findings:
        return _evaluation(1, "No evidence-backed heading structure issues were detected.")
    return _evaluation(
        1 - min(1, 0.25 * len(findings)),
        f"{len(findings)} evidence-backed heading structure issue(s) were detected.",
        findings=findings,
        deduction_keys=_finding_keys("citation-headings", findings),
    )


def _citation_chunkability(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis:
        return _not_scored("Content structure analysis was unavailable, so this rule was not deducted.")
    findings = _findings(
        context,
        AuditCategory.CITATION_READINESS,
        "paragraph is difficult",
        "section is too long",
    )
    if not findings:
        return _evaluation(1, "No evidence-backed content chunkability issues were detected.")
    return _evaluation(
        1 - min(1, len(findings) / 3),
        f"{len(findings)} evidence-backed long-form content structure issue(s) were detected.",
        findings=findings,
        deduction_keys=_finding_keys("citation-chunkability", findings),
    )


def _citation_lists_and_tables(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis:
        return _not_scored("List and table analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.CITATION_READINESS, "no lists or tables")
    if not findings:
        return _evaluation(1, "No long page without lists or tables was detected.")
    return _evaluation(
        0,
        "A page over the analyzer's length threshold has no detected lists or tables.",
        findings=findings,
        deduction_keys=_finding_keys("citation-lists", findings),
    )


def _citation_faq(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis:
        return _not_scored("FAQ analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.CITATION_READINESS, "question headings do not")
    if not findings:
        return _evaluation(1, "No question headings without visible answers were detected.")
    return _evaluation(
        0,
        "Question-style headings were detected without nearby visible answers.",
        findings=findings,
        deduction_keys=_finding_keys("citation-faq", findings),
    )


def _citation_claims(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis:
        return _not_scored("Claim-support analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.CITATION_READINESS, "unsupported claims")
    if not findings:
        return _evaluation(1, "No confidence-based unsupported-claim signals were detected.")
    return _evaluation(
        0.5,
        "Potential claims were found without a nearby supporting source; the signal is confidence-based, not a claim of falsity.",
        findings=findings,
        deduction_keys=_finding_keys("citation-claims", findings),
    )


def _citation_freshness(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.citation_readiness
    if not analysis:
        return _not_scored("Freshness-signal analysis was unavailable, so this rule was not deducted.")
    dated_pages = sum(bool(page.freshness_signals) for page in analysis.pages)
    if dated_pages:
        return _evaluation(1, f"Freshness signals were found on {dated_pages} crawled page(s); no recency judgment was made.")
    return _not_scored("No freshness signals were found; absence alone is not a deduction.")


def _entity_schema(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Entity structured-data analysis was unavailable, so this rule was not deducted.")
    findings = _findings(
        context,
        AuditCategory.ENTITY_TRUST,
        "organization-like",
        "organization structured data",
        "malformed json-ld",
    )
    if analysis.organization_data and not findings:
        return _evaluation(1, "Organization-like structured data was detected without a linked structural issue.")
    if not findings:
        return _not_scored("No evidence-backed organization structured-data issue was available to score.")
    return _evaluation(
        0 if not analysis.organization_data else 0.6,
        "Organization structured-data coverage has evidence-backed gaps.",
        findings=findings,
        deduction_keys=_finding_keys("entity-schema", findings),
    )


def _entity_identity(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Entity identity analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.ENTITY_TRUST, "entity consistency risk", "contains conflicting")
    if not findings:
        return _evaluation(1, "No evidence-backed conflicting organization identity signals were detected.")
    return _evaluation(
        0,
        "Conflicting organization identity signals were detected.",
        findings=findings,
        deduction_keys=_finding_keys("entity-identity", findings),
    )


def _entity_contact(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Organization-page analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.ENTITY_TRUST, "about page", "contact page", "contact details")
    if not findings:
        return _evaluation(1, "No evidence-backed organization or contact-page issue was detected.")
    return _evaluation(
        1 - min(1, 0.5 * len(findings)),
        f"{len(findings)} evidence-backed organization or contact-page issue(s) were detected.",
        findings=findings,
        deduction_keys=_finding_keys("entity-contact", findings),
    )


def _entity_policies(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Trust-policy analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.ENTITY_TRUST, "trust policy")
    if not findings:
        return _evaluation(1, "No evidence-backed missing core trust-policy issue was detected.")
    return _evaluation(
        0,
        "Applicable core trust-policy pages were not detected within the bounded crawl.",
        findings=findings,
        deduction_keys=_finding_keys("entity-policies", findings),
    )


def _entity_editorial(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Editorial-attribution analysis was unavailable, so this rule was not deducted.")
    findings = _findings(context, AuditCategory.ENTITY_TRUST, "editorial")
    if not findings:
        return _evaluation(1, "No evidence-backed editorial attribution issue was detected.")
    return _evaluation(
        1 - min(1, len(findings) / 3),
        f"{len(findings)} evidence-backed editorial attribution issue(s) were detected.",
        findings=findings,
        deduction_keys=_finding_keys("entity-editorial", findings),
    )


def _entity_credibility(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Credibility-signal analysis was unavailable, so this rule was not deducted.")
    # The Phase 4 analyzer detects visible credibility signals without judging their truth.
    if any(
        signal.outbound_citation_urls
        or signal.named_source_labels
        or signal.certifications_or_awards
        or signal.testimonial_signals
        or signal.case_study_signals
        for signal in analysis.credibility_signals
    ):
        return _evaluation(1, "Visible, non-verified credibility context was detected; no truth claim is made.")
    return _not_scored("No credibility signal was detected; absence alone is not a deduction.")


def _entity_profiles(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.entity_trust
    if not analysis:
        return _not_scored("Official-profile analysis was unavailable, so this rule was not deducted.")
    findings = _findings(
        context,
        AuditCategory.ENTITY_TRUST,
        "sameas",
        "potential official profiles",
        "multiple potential",
    )
    if not findings:
        return _evaluation(1, "No evidence-backed official-profile linkage issue was detected.")
    return _evaluation(
        0.5,
        "Potential or malformed official-profile linkage needs verification before it is published in sameAs.",
        findings=findings,
        deduction_keys=_finding_keys("entity-profiles", findings),
    )


def _answer_result(context: ScoringContext, question_id: str):
    analysis = context.result.answerability
    if not analysis:
        return None
    return next((item for item in analysis.results if item.question.id == question_id), None)


def _answer_quality(result) -> float:
    if result.status in {AnswerStatus.CLEARLY_ANSWERED, AnswerStatus.NOT_APPLICABLE}:
        return 1
    if result.status == AnswerStatus.PARTIALLY_ANSWERED:
        return 0.5
    # A conflicting purpose is handled by the separate conflict rule so the same
    # disagreement never takes points from two rules.
    if result.status == AnswerStatus.CONFLICTING_ANSWER:
        return 1
    return 0


def _answer_findings(context: ScoringContext, question_ids: Iterable[str]) -> tuple[DiscoverabilityFinding, ...]:
    labels = {
        "purpose": "core purpose",
        "audience": "target audience",
        "offerings": "products or services",
        "location": "geographic coverage",
        "contact": "contact or engagement",
        "pricing": "pricing is not",
        "trust": "trust justification",
        "differentiation": "differentiation",
        "next_action": "next action",
    }
    needles = [labels[question_id] for question_id in question_ids]
    return _findings(context, AuditCategory.ANSWERABILITY, *needles)


def _answer_rule(context: ScoringContext, question_ids: tuple[str, ...], label: str) -> RuleEvaluation:
    results = [_answer_result(context, question_id) for question_id in question_ids]
    if any(item is None for item in results):
        return _not_scored(f"No complete {label.lower()} answerability result was available to score.")
    quality = sum(_answer_quality(item) for item in results) / len(results)
    findings = _answer_findings(context, question_ids)
    if quality == 1:
        return _evaluation(1, f"{label} is clearly answered or not applicable based on crawled evidence.")
    status_description = ", ".join(item.status.value for item in results)
    return _evaluation(
        quality,
        f"{label} result: {status_description}.",
        findings=findings,
        deduction_keys=_finding_keys("answerability-" + "-".join(question_ids), findings)
        or tuple(f"answerability:{question_id}" for question_id in question_ids),
    )


def _answer_conflicts(context: ScoringContext) -> RuleEvaluation:
    analysis = context.result.answerability
    if not analysis:
        return _not_scored("Answerability conflict analysis was unavailable, so this rule was not deducted.")
    conflicts = [item for item in analysis.results if item.status == AnswerStatus.CONFLICTING_ANSWER]
    if not conflicts:
        return _evaluation(1, "No genuinely conflicting answer excerpts were detected.")
    findings = _findings(context, AuditCategory.ANSWERABILITY, "contradictory")
    return _evaluation(
        0,
        f"{len(conflicts)} genuinely conflicting answerability description(s) were detected.",
        findings=findings,
        deduction_keys=_finding_keys("answerability-conflict", findings) or ("answerability:conflict",),
    )


# Category totals are deliberately explicit and sum to 25 points each.
DEFAULT_SCORING_RULES: tuple[ScoringRule, ...] = (
    ScoringRule("robots_txt", AuditCategory.DISCOVERABILITY, "Robots.txt", 3, _discoverability_robots, "robots.txt could not be retrieved", "Checks whether the crawl access policy is published."),
    ScoringRule("sitemap", AuditCategory.DISCOVERABILITY, "Sitemap", 4, _discoverability_sitemap, "usable sitemap coverage is missing or incomplete", "Checks whether URL discovery coverage is complete."),
    ScoringRule("canonical", AuditCategory.DISCOVERABILITY, "Canonical URLs", 4, _discoverability_canonical, "pages have missing or external canonical URLs", "Checks whether crawled pages identify their preferred URLs."),
    ScoringRule("meta_robots", AuditCategory.DISCOVERABILITY, "Meta robots", 4, _discoverability_meta_robots, "crawled pages have noindex directives", "Checks whether pages are eligible for indexing."),
    ScoringRule("llms_txt", AuditCategory.DISCOVERABILITY, "llms.txt", 3, _discoverability_llms, "llms.txt is missing", "Checks for the optional AI-facing site guide."),
    ScoringRule("bot_access", AuditCategory.DISCOVERABILITY, "Bot accessibility", 4, _discoverability_bots, "AI crawler access is blocked or unknown", "Checks the effective root-path access for selected AI crawlers."),
    ScoringRule("homepage_discovery", AuditCategory.DISCOVERABILITY, "Homepage discovery", 3, _discoverability_homepage, "homepage content is not reliably discoverable", "Checks that the crawled homepage has meaningful identifying content."),
    ScoringRule("opening_clarity", AuditCategory.CITATION_READINESS, "Direct answer openings", 4, _citation_opening, "page openings do not explain their topic", "Checks whether page openings can be understood in isolation."),
    ScoringRule("heading_quality", AuditCategory.CITATION_READINESS, "Heading quality", 4, _citation_headings, "heading structure is unclear", "Checks H1 coverage, hierarchy, and generic headings."),
    ScoringRule("chunkability", AuditCategory.CITATION_READINESS, "Content chunkability", 4, _citation_chunkability, "long content is difficult to extract", "Checks paragraphs and sections for citation-friendly structure."),
    ScoringRule("faq_answers", AuditCategory.CITATION_READINESS, "FAQ answerability", 4, _citation_faq, "question headings have no visible answers", "Checks that visible questions have nearby answer content."),
    ScoringRule("lists_tables", AuditCategory.CITATION_READINESS, "Lists and tables", 3, _citation_lists_and_tables, "long pages have no lists or tables", "Checks whether long pages have scannable structural elements."),
    ScoringRule("claim_support", AuditCategory.CITATION_READINESS, "Claim support", 3, _citation_claims, "potential claims lack nearby sources", "Uses a confidence-based signal for support near potentially notable claims."),
    ScoringRule("freshness_signals", AuditCategory.CITATION_READINESS, "Freshness signals", 3, _citation_freshness, "freshness signals are unavailable", "Records dates without making an automatic recency judgment."),
    ScoringRule("organization_schema", AuditCategory.ENTITY_TRUST, "Organization structured data", 5, _entity_schema, "organization structured data has gaps", "Checks whether explicit organization data is available and complete."),
    ScoringRule("identity_consistency", AuditCategory.ENTITY_TRUST, "Identity consistency", 4, _entity_identity, "organization identity signals conflict", "Checks whether public organization names and URLs conflict."),
    ScoringRule("contact_pages", AuditCategory.ENTITY_TRUST, "Organization and contact pages", 4, _entity_contact, "organization or contact pages have evidence-backed gaps", "Checks accessible attribution and contact paths."),
    ScoringRule("trust_policies", AuditCategory.ENTITY_TRUST, "Trust policies", 4, _entity_policies, "applicable policy pages were not detected", "Checks policy accessibility where the analyzer identified a commercial context."),
    ScoringRule("editorial_attribution", AuditCategory.ENTITY_TRUST, "Editorial attribution", 3, _entity_editorial, "editorial content lacks attribution", "Checks authorship and date signals on substantial editorial pages."),
    ScoringRule("credibility_context", AuditCategory.ENTITY_TRUST, "Credibility context", 3, _entity_credibility, "credibility context is unavailable", "Recognizes visible credibility context without judging truth."),
    ScoringRule("official_profiles", AuditCategory.ENTITY_TRUST, "Official profile linkage", 2, _entity_profiles, "official-profile linkage needs verification", "Checks conservative sameAs linkage candidates."),
    ScoringRule("purpose", AuditCategory.ANSWERABILITY, "Core purpose", 4, lambda context: _answer_rule(context, ("purpose",), "Core purpose"), "core purpose is not clearly answered", "Checks whether the organization explains what it does."),
    ScoringRule("audience_offerings", AuditCategory.ANSWERABILITY, "Audience and offerings", 4, lambda context: _answer_rule(context, ("audience", "offerings"), "Audience and offerings"), "audience or offerings are not clearly answered", "Checks who the site is for and what it offers."),
    ScoringRule("contact_engagement", AuditCategory.ANSWERABILITY, "Contact and engagement", 3, lambda context: _answer_rule(context, ("contact",), "Contact and engagement"), "contact or engagement is not clearly answered", "Checks whether a visitor can take a direct engagement path."),
    ScoringRule("pricing_relevance", AuditCategory.ANSWERABILITY, "Pricing relevance", 3, lambda context: _answer_rule(context, ("pricing",), "Pricing relevance"), "pricing is not findable when relevant", "Uses the analyzer's commercial-context and not-applicable handling."),
    ScoringRule("location_relevance", AuditCategory.ANSWERABILITY, "Geographic coverage", 2, lambda context: _answer_rule(context, ("location",), "Geographic coverage"), "geographic coverage is unclear when relevant", "Uses the analyzer's global-product and relevance handling."),
    ScoringRule("trust_differentiation", AuditCategory.ANSWERABILITY, "Trust and differentiation", 4, lambda context: _answer_rule(context, ("trust", "differentiation"), "Trust and differentiation"), "trust or differentiation is not clearly answered", "Checks why visitors should trust the site and how it differs."),
    ScoringRule("next_action", AuditCategory.ANSWERABILITY, "Next action", 2, lambda context: _answer_rule(context, ("next_action",), "Next action"), "the visitor's next action is unclear", "Checks whether a visitor can identify a concrete next step."),
    ScoringRule("conflicting_answers", AuditCategory.ANSWERABILITY, "Conflicting answers", 3, _answer_conflicts, "core descriptions conflict", "Only deducts when two crawled sources genuinely disagree."),
)
