"""Deterministic, evidence-backed checks for whether a site answers core questions."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from ..models import (
    AnswerEvidence,
    AnswerStatus,
    AnswerabilityAnalysis,
    AnswerabilityQuestion,
    AnswerabilityResult,
    AnswerabilitySummary,
    AuditCategory,
    Confidence,
    ContentBlock,
    CrawledPage,
    DiscoverabilityFinding,
    EntityTrustAnalysis,
    Evidence,
    PrimaryEntityContext,
    Severity,
)


QUESTION_SET = (
    AnswerabilityQuestion(id="purpose", label="What does this organization do?"),
    AnswerabilityQuestion(id="audience", label="Who is it for?"),
    AnswerabilityQuestion(id="offerings", label="What products or services are offered?"),
    AnswerabilityQuestion(id="location", label="Where does the organization operate?"),
    AnswerabilityQuestion(id="contact", label="How can someone contact or engage with it?"),
    AnswerabilityQuestion(id="pricing", label="How much does it cost?"),
    AnswerabilityQuestion(id="trust", label="Why should someone trust it?"),
    AnswerabilityQuestion(id="differentiation", label="How is it different from alternatives?"),
    AnswerabilityQuestion(id="next_action", label="What should a visitor do next?"),
)
QUESTIONS = {question.id: question for question in QUESTION_SET}

WORD_PATTERN = re.compile(r"\b[\w'-]+\b")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
PURPOSE_VERB_PATTERN = re.compile(
    r"\b(?:is|are|provides?|offers?|builds?|creates?|delivers?|runs?|operates?|develops?|"
    r"supports?|advances?|promotes?)\b",
    re.I,
)
PURPOSE_TYPE_PATTERN = re.compile(r"\b(?:is|are)\s+(?:an?|the)\s+[\w -]{2,70}\b", re.I)
OFFERING_PATTERN = re.compile(
    r"\b(?:products?|services?|solutions?|software|platform|application|app|tool(?:s)?|"
    r"consulting|consultancy|training|support|subscriptions?|plans?|courses?|programs?)\b",
    re.I,
)
AUDIENCE_PATTERN = re.compile(
    r"\b(?:for|built for|designed for|made for|serving|serves|helps?)\s+(?:the\s+)?"
    r"([A-Za-z][A-Za-z0-9&' -]{2,80})",
    re.I,
)
AUDIENCE_TERMS = {
    "businesses",
    "companies",
    "teams",
    "developers",
    "customers",
    "organizations",
    "people",
    "students",
    "teachers",
    "professionals",
    "marketers",
    "designers",
    "patients",
    "families",
    "nonprofits",
    "publishers",
    "creators",
    "startups",
    "enterprises",
    "agencies",
}
GENERIC_AUDIENCES = {"you", "everyone", "all", "anyone", "people"}
PRICE_PATTERN = re.compile(
    r"(?:[$€£₹]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|inr)\b|\bstarting\s+at\b|"
    r"\bper\s+(?:month|year|user)\b|\b(?:monthly|annual)\s+plan)",
    re.I,
)
PRICE_CONTACT_PATTERN = re.compile(
    r"\b(?:contact|talk to|speak with|request)\b.{0,40}\b(?:pricing|price|quote|sales)\b|"
    r"\b(?:pricing|price|quote)\b.{0,40}\b(?:contact|sales|request)\b",
    re.I,
)
CURRENCY_PATTERN = re.compile(r"(?:[$€£₹]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|inr)\b)", re.I)
PRICE_CONTEXT_PATTERN = re.compile(
    r"\b(?:per\s+(?:month|year|transaction|user)|starting\s+at|plans?|pricing|fees?|"
    r"subscriptions?|billed|free|enterprise quote|custom pricing|pay[- ]as[- ]you[- ]go)\b",
    re.I,
)
PRICE_NEGATIVE_PATTERN = re.compile(
    r"\b(?:processed|volume|revenue|funding|grant|awarded|raised|valuation|market size|"
    r"transaction volume|annual report|statistic|trillion|billion users?|customer result)\b",
    re.I,
)
COMMERCIAL_PATTERN = re.compile(
    r"\b(?:pricing|price|plans?|subscribe|subscription|buy|purchase|free trial|request a quote|"
    r"contact sales|checkout|billing|paid plan|fees?|payment processing|financial infrastructure|commerce)\b",
    re.I,
)
NONCOMMERCIAL_PATTERN = re.compile(
    r"\b(?:non[- ]?profit|not[- ]?for[- ]?profit|charity|donation[- ]funded|volunteer[- ]?run|"
    r"open[- ]?source(?: project)?|public[- ]?benefit|foundation|grant program|community maintained)\b",
    re.I,
)
LOCATION_PATTERN = re.compile(
    r"\b(?:based in|headquartered in|located in|operating in|service area|"
    r"offices? in|visit us in)\s+[A-Za-z0-9 ,.'-]{2,100}",
    re.I,
)
GLOBAL_AVAILABILITY_PATTERN = re.compile(
    r"\b(?:available|operate|operating|serve|serving|support(?:ed)?|access(?:ible)?)\b.{0,40}"
    r"\b(?:worldwide|globally|around the world|internationally)\b|"
    r"\b(?:worldwide|global)\s+(?:availability|access|coverage)\b",
    re.I,
)
DIGITAL_PATTERN = re.compile(
    r"\b(?:software|platform|application|app|digital|cloud|online service|web[- ]based|api)\b",
    re.I,
)
PHYSICAL_RELEVANCE_PATTERN = re.compile(
    r"\b(?:local|in[- ]person|visit our|office|store|clinic|restaurant|service area|location)\b",
    re.I,
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{6,}\d)(?!\w)")
CONTACT_PATTERN = re.compile(r"\b(?:contact us|email us|call us|get in touch|book a meeting|talk to us)\b", re.I)
TRUST_STRONG_PATTERN = re.compile(
    r"\b(?:soc\s?2|iso\s?27001|hipaa|gdpr|certified|accredited|licensed|regulated|"
    r"independently audited|trusted by|years of experience)\b",
    re.I,
)
TRUST_PARTIAL_PATTERN = re.compile(
    r"\b(?:testimonial|customer stor(?:y|ies)|case stud(?:y|ies)|award(?:-winning)?|"
    r"privacy policy|terms of (?:service|use)|security)\b",
    re.I,
)
DIFFERENTIATOR_PATTERN = re.compile(
    r"\b(?:unlike|instead of|different from|compared with|compared to|only platform|"
    r"only service|unique(?:ly)?|without [a-z]+|all[- ]in[- ]one)\b",
    re.I,
)
GENERIC_DIFFERENTIATOR_PATTERN = re.compile(r"\b(?:better|leading|innovative|fastest)\b", re.I)
CTA_PATTERN = re.compile(
    r"\b(?:get started|start (?:a )?free trial|book a demo|request a demo|request a quote|"
    r"contact us|contact our team|sign up|join now|buy now|schedule (?:a )?consultation|downloads?|try|documentation)\b",
    re.I,
)
GENERIC_CTA_PATTERN = re.compile(r"\b(?:learn more|read more|explore)\b", re.I)
PURPOSE_CLASS_PATTERN = re.compile(
    r"\b(?:we|[A-Z][A-Za-z0-9&' -]{1,60})\s+(?:are|is)\s+(?:an?\s+)?"
    r"(?P<kind>non[- ]?profit|not[- ]?for[- ]?profit|for[- ]?profit|commercial|"
    r"government(?:al)?|public[- ]sector|university|school)\b",
    re.I,
)
FIRST_PERSON_PATTERN = re.compile(r"\b(?:we|our|us)\b", re.I)
EXTERNAL_SUBJECT_PATTERN = re.compile(
    r"^\s*(?:the\s+)?[A-Z][A-Za-z0-9&'_-]*(?:\s+[A-Z][A-Za-z0-9&'_-]*){0,2}\s+"
    r"(?:is|are|provides?|offers?|delivers?|builds?|helps?|uses?|raised|received)\b",
)
THIRD_PARTY_CONTEXT_PATTERN = re.compile(
    r"\b(?:case study|customer stor(?:y|ies)|partner|testimonial|grant|ecosystem example|"
    r"according to|cited report|external organization|sponsored by)\b",
    re.I,
)
STATISTIC_CONTEXT_PATTERN = re.compile(
    r"\b(?:processed|processes|transaction volume|revenue|uptime|fortune\s+\d+|"
    r"\d+(?:\.\d+)?%|million|billion|trillion|market size|annual report)\b",
    re.I,
)
NOISE_PAGE_PATTERN = re.compile(
    r"\b(?:case stud(?:y|ies)|customer stor(?:y|ies)|partner|testimonial|blog|news|article|"
    r"report|grant|grants|quote|quotes|press|legal|privacy|terms|cookie|accessibility)\b",
    re.I,
)
LEGAL_PAGE_PATTERN = re.compile(r"\b(?:privacy|terms|cookie|legal|accessibility)\b", re.I)
MIN_CANDIDATE_SCORE = 10


@dataclass(frozen=True, slots=True)
class Candidate:
    """A bounded excerpt found in a crawled page."""

    page_url: str
    excerpt: str
    source_type: str
    context: str | None = None
    answer_reason: str | None = None
    entity_relevance_reason: str | None = None
    relevance_score: int = 0
    page_priority: int = 0


class AnswerabilityAnalyzer:
    """Assess whether a small crawl directly answers nine core visitor questions."""

    def analyze(
        self,
        pages: list[CrawledPage],
        entity_trust: EntityTrustAnalysis | None = None,
        site_url: str | None = None,
    ) -> AnswerabilityAnalysis:
        """Return unscored answerability results and actionable shared findings."""

        primary_entity = _primary_entity_context(pages, site_url)
        fallback_url = primary_entity.homepage_url or (pages[0].url if pages else (site_url or ""))
        noncommercial = _first_candidate(
            primary_entity, pages, _is_noncommercial, question_id="pricing", roles=("home", "about")
        )
        commercial = _is_commercial(primary_entity, pages)
        global_digital = _first_candidate(
            primary_entity, pages, _is_global_digital, question_id="location", roles=("home", "about", "product")
        )

        results = [
            self._purpose_result(primary_entity, pages, fallback_url),
            self._audience_result(primary_entity, pages, fallback_url),
            self._offerings_result(primary_entity, pages, fallback_url),
            self._location_result(primary_entity, pages, fallback_url, commercial, global_digital),
            self._contact_result(primary_entity, pages, fallback_url),
            self._pricing_result(primary_entity, pages, fallback_url, commercial, noncommercial),
            self._trust_result(primary_entity, pages, fallback_url, entity_trust),
            self._differentiation_result(primary_entity, pages, fallback_url),
            self._next_action_result(primary_entity, pages, fallback_url),
        ]
        findings = [_finding_for_result(result, fallback_url) for result in results]
        findings = [finding for finding in findings if finding is not None]
        return AnswerabilityAnalysis(
            primary_entity=primary_entity,
            results=results,
            summary=_summary(results),
            findings=findings,
        )

    def _purpose_result(
        self,
        primary_entity: PrimaryEntityContext,
        pages: list[CrawledPage],
        fallback_url: str,
    ) -> AnswerabilityResult:
        conflict = _purpose_conflict(primary_entity, pages)
        if conflict:
            first, second = conflict
            return _result(
                "purpose",
                AnswerStatus.CONFLICTING_ANSWER,
                Confidence.LOW,
                first,
                explanation=(
                    "Two direct organization-type statements use mutually exclusive classifications; "
                    "the analyzer does not infer conflicts from ordinary multi-service descriptions."
                ),
                recommendation="Verify the organization description and publish one consistent primary description.",
                impact=5,
                effort=2,
                additional=[second],
                conflicting_excerpt=second.excerpt,
            )

        clear = _first_candidate(
            primary_entity, pages, lambda text, _page: _purpose_strength(text) == 2,
            question_id="purpose", roles=("home", "about", "company", "product", "service"),
        )
        if clear:
            return _result(
                "purpose",
                AnswerStatus.CLEARLY_ANSWERED,
                Confidence.HIGH,
                clear,
                explanation="A descriptive content passage states what the organization provides or is.",
                recommendation="Keep this direct explanation near the start of key pages.",
                impact=5,
                effort=1,
            )
        partial = _first_candidate(
            primary_entity, pages, lambda text, _page: _purpose_strength(text) == 1,
            question_id="purpose", roles=("home", "about", "company", "product", "service"),
        )
        if partial:
            return _result(
                "purpose",
                AnswerStatus.PARTIALLY_ANSWERED,
                Confidence.MEDIUM,
                partial,
                explanation="The site names an offering or mission, but the nearby text is too brief or generic to explain the core purpose clearly.",
                recommendation="Add one plain-language sentence that states what the organization does and the outcome it provides.",
                impact=5,
                effort=2,
            )
        return _absence_result(
            "purpose",
            fallback_url,
            "No descriptive paragraph explaining the organization’s purpose was detected on the homepage, About, service, or product pages.",
            "No qualifying descriptive page content was found; headings and navigation labels were not treated as answers.",
            "Add a plain-language purpose statement near the top of the homepage or About page.",
            impact=5,
            effort=2,
        )

    def _audience_result(
        self, primary_entity: PrimaryEntityContext, pages: list[CrawledPage], fallback_url: str
    ) -> AnswerabilityResult:
        clear = _first_candidate(
            primary_entity, pages, _has_specific_audience,
            question_id="audience", roles=("home", "product", "service", "about"),
        )
        if clear:
            return _result(
                "audience",
                AnswerStatus.CLEARLY_ANSWERED,
                Confidence.HIGH,
                clear,
                explanation="A content passage explicitly identifies a meaningful audience, rather than relying on a menu label.",
                recommendation="Keep the audience description close to the primary purpose statement.",
                impact=4,
                effort=1,
            )
        partial = _first_candidate(
            primary_entity, pages, _has_generic_audience,
            question_id="audience", roles=("home", "product", "service", "about"),
        )
        if partial:
            return _result(
                "audience",
                AnswerStatus.PARTIALLY_ANSWERED,
                Confidence.MEDIUM,
                partial,
                explanation="The site refers to an audience, but the wording is too broad to identify who the offering is for.",
                recommendation="Name the primary user, customer group, industry, or use case in a complete sentence.",
                impact=4,
                effort=2,
            )
        return _absence_result(
            "audience",
            fallback_url,
            "No meaningful audience statement was detected in crawled content; navigation labels were excluded.",
            "The crawler found no descriptive passage that identifies a specific audience.",
            "Add a sentence that names the primary people or organizations the offering serves.",
            impact=4,
            effort=2,
        )

    def _offerings_result(
        self, primary_entity: PrimaryEntityContext, pages: list[CrawledPage], fallback_url: str
    ) -> AnswerabilityResult:
        clear = _first_candidate(
            primary_entity, pages, lambda text, _page: _offering_strength(text) == 2,
            question_id="offerings", roles=("product", "service", "home", "pricing"),
        )
        if clear:
            return _result(
                "offerings",
                AnswerStatus.CLEARLY_ANSWERED,
                Confidence.HIGH,
                clear,
                explanation="A descriptive content passage names products, services, or a specific offering.",
                recommendation="Keep offering descriptions specific and accessible from high-priority pages.",
                impact=5,
                effort=1,
            )
        partial = _first_candidate(
            primary_entity, pages, lambda text, _page: _offering_strength(text) == 1,
            question_id="offerings", roles=("product", "service", "home", "pricing"),
        )
        if partial:
            return _result(
                "offerings",
                AnswerStatus.PARTIALLY_ANSWERED,
                Confidence.MEDIUM,
                partial,
                explanation="An offering-related term was found, but the nearby text does not describe what is actually provided.",
                recommendation="Describe the main products or services in complete, visitor-facing sentences.",
                impact=5,
                effort=2,
            )
        return _absence_result(
            "offerings",
            fallback_url,
            "No descriptive product or service passage was detected; headings and navigation labels were excluded.",
            "The crawler found no meaningful page content that names and describes an offering.",
            "Add a concise products or services description to the homepage and relevant offering pages.",
            impact=5,
            effort=2,
        )

    def _location_result(
        self,
        primary_entity: PrimaryEntityContext,
        pages: list[CrawledPage],
        fallback_url: str,
        commercial: bool,
        global_digital: Candidate | None,
    ) -> AnswerabilityResult:
        address = _visible_address_candidate(primary_entity, pages)
        if address:
            return _result(
                "location", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, address,
                explanation="A visible postal address was extracted from crawled page content.",
                recommendation="Keep the published address current and consistent across primary pages.", impact=3, effort=1,
            )
        if global_digital:
            return _not_applicable_result(
                "location", global_digital,
                "The site explicitly describes a globally available digital offering, so a local service area is not required.",
                "No location change is needed unless regional eligibility, offices, or in-person delivery become commercially relevant.",
            )
        location = _first_candidate(
            primary_entity, pages, _has_location_statement,
            question_id="location", roles=("contact", "locations", "service_area", "about"),
        )
        if location:
            return _result(
                "location", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, location,
                explanation="A descriptive content passage states an operating location or service area.",
                recommendation="Keep geographic coverage visible where it affects eligibility or service availability.", impact=3, effort=1,
            )
        physical = _first_candidate(
            primary_entity, pages, lambda text, _page: bool(PHYSICAL_RELEVANCE_PATTERN.search(text)),
            question_id="location", roles=("contact", "locations", "service_area", "about"),
        )
        if commercial and physical:
            return _absence_result(
                "location", fallback_url,
                "The crawled content indicates a local or in-person offering, but no operating location or service area was detected.",
                "Location is commercially relevant from the detected in-person or local-service wording, yet no coverage statement was found.",
                "State the service area, office location, or regions served in visible page content.",
                impact=3,
                effort=2,
            )
        return _absence_result(
            "location",
            fallback_url,
            "No geographic location, service area, supported-country, or global availability statement was detected in relevant crawled content.",
            "No explicit geographic evidence was found, so the analyzer cannot assume that location is irrelevant.",
            "State the operating location, service area, supported countries, or globally available scope where relevant.",
            impact=3,
            effort=2,
        )

    def _contact_result(
        self, primary_entity: PrimaryEntityContext, pages: list[CrawledPage], fallback_url: str
    ) -> AnswerabilityResult:
        for page in _ordered_pages(pages, ("contact", "home", "about")):
            if page.has_contact_form:
                candidate = _candidate(
                    primary_entity,
                    page,
                    "A public contact form was detected on this crawled page.",
                    "HTML contact form",
                    question_id="contact",
                    page_priority=_page_priority(page, ("contact", "support", "home")),
                    answer_reason="A public contact form provides a direct engagement method.",
                )
                if candidate is None:
                    continue
                return _result(
                    "contact", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, candidate,
                    explanation="A publicly available contact form gives visitors a direct engagement path.",
                    recommendation="Keep the form accessible and describe the expected response path where appropriate.", impact=4, effort=1,
                )
            labels = _page_labels(page)
            if {"contact", "support"} & labels:
                page_kind = "Support" if "support" in labels and "contact" not in labels else "Contact"
                candidate = _candidate(
                    primary_entity,
                    page,
                    f"A crawled {page_kind} page is available at {page.url}.",
                    f"crawled {page_kind} page",
                    question_id="contact",
                    page_priority=_page_priority(page, ("contact", "support", "home")),
                    answer_reason=f"A dedicated {page_kind} page provides a direct engagement path.",
                    allow_page_scope=True,
                )
                if candidate:
                    return _result(
                        "contact", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, candidate,
                        explanation="A dedicated Contact or Support page was crawled for the primary entity.",
                        recommendation="Keep the direct engagement path easy to find and current.", impact=4, effort=1,
                    )
        contact = _first_candidate(
            primary_entity, pages, _has_contact_method,
            question_id="contact", roles=("contact", "support", "home"),
        )
        if contact:
            return _result(
                "contact", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, contact,
                explanation="A content passage provides a direct contact method or engagement instruction.",
                recommendation="Keep the contact method easy to find and current.", impact=4, effort=1,
            )
        return _absence_result(
            "contact",
            fallback_url,
            "No contact form, published email or phone number, or direct engagement instruction was detected in crawled content.",
            "Internal navigation labels alone were not treated as a complete contact answer.",
            "Publish a direct contact method or clearly available contact form on a crawled page.",
            impact=4,
            effort=2,
        )

    def _pricing_result(
        self,
        primary_entity: PrimaryEntityContext,
        pages: list[CrawledPage],
        fallback_url: str,
        commercial: bool,
        noncommercial: Candidate | None,
    ) -> AnswerabilityResult:
        price = _first_candidate(
            primary_entity, pages, _has_numeric_pricing,
            question_id="pricing", roles=("pricing", "plan", "product", "checkout", "billing"),
        )
        if price:
            return _result(
                "pricing", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, price,
                explanation="A pricing amount or structured price signal appears in meaningful crawled content.",
                recommendation="Keep pricing details current and explain any material limits or billing cadence.", impact=4, effort=1,
            )
        pricing_path = _first_candidate(
            primary_entity, pages, _has_pricing_contact_path,
            question_id="pricing", roles=("pricing", "plan", "product", "checkout", "billing"),
        )
        if pricing_path:
            return _result(
                "pricing", AnswerStatus.PARTIALLY_ANSWERED, Confidence.HIGH, pricing_path,
                explanation="The site gives a route to obtain pricing, but no amount or plan detail was detected.",
                recommendation="Add starting prices, plan ranges, or a concise explanation of how pricing is determined where safe to publish.", impact=4, effort=2,
            )
        if noncommercial:
            return _not_applicable_result(
                "pricing",
                replace(
                    noncommercial,
                    answer_reason="The excerpt explicitly identifies a non-commercial, community, or donation-funded context.",
                ),
                "The crawled content explicitly identifies a non-commercial, community, or donation-funded context and no paid offering was detected.",
                "No pricing change is needed unless the site begins offering paid products or services.",
            )
        if commercial:
            return _absence_result(
                "pricing",
                fallback_url,
                "Commercial offering signals were detected, but no price, plan, quote route, or pricing explanation was found in crawled content.",
                "The site appears to offer a commercial product or service, yet visitors cannot find pricing information in the audited pages.",
                "Add a pricing page, starting price, plan range, or a clear quote-request path.",
                impact=4,
                effort=2,
            )
        return _not_applicable_result(
            "pricing",
            Candidate(fallback_url, "No commercial offering or published pricing signal was detected in the crawled content.", "crawled page audit"),
            "The available pages do not establish that pricing applies to this site.",
            "Reassess this question if paid products, services, subscriptions, or quote-based work are added.",
            confidence=Confidence.LOW,
        )

    def _trust_result(
        self,
        primary_entity: PrimaryEntityContext,
        pages: list[CrawledPage],
        fallback_url: str,
        entity_trust: EntityTrustAnalysis | None,
    ) -> AnswerabilityResult:
        clear = _first_candidate(
            primary_entity, pages, _has_strong_trust_signal,
            question_id="trust", roles=("security", "compliance", "about", "case_study", "home"),
        )
        if clear:
            return _result(
                "trust", AnswerStatus.CLEARLY_ANSWERED, Confidence.MEDIUM, clear,
                explanation="A visible trust signal such as a certification, regulation, audit, or named customer proof was detected in page content.",
                recommendation="Keep trust claims specific and link to supporting details where available.", impact=4, effort=1,
            )
        partial = _first_candidate(
            primary_entity, pages, _has_partial_trust_signal,
            question_id="trust", roles=("security", "compliance", "about", "case_study", "home"),
        )
        if partial:
            return _result(
                "trust", AnswerStatus.PARTIALLY_ANSWERED, Confidence.MEDIUM, partial,
                explanation="The site contains a visible trust-related signal, but the nearby content does not provide a strong, self-contained trust explanation.",
                recommendation="Add factual, verifiable trust evidence such as credentials, customer proof, methodology, or policy links with context.", impact=4, effort=2,
            )
        credibility = _phase4_credibility_candidate(entity_trust)
        if credibility:
            return _result(
                "trust", AnswerStatus.PARTIALLY_ANSWERED, Confidence.MEDIUM, credibility,
                explanation="Phase 4 detected a visible credibility signal in crawled content, but this analyzer did not find a self-contained trust explanation beside it.",
                recommendation="Add concise context that explains the detected credential, customer proof, source, or award and links to supporting details where possible.", impact=4, effort=2,
            )
        policy = _available_policy_candidate(entity_trust)
        if policy:
            return _result(
                "trust", AnswerStatus.PARTIALLY_ANSWERED, Confidence.MEDIUM, policy,
                explanation="Phase 4 detected a publicly available policy page, which is a limited trust signal but not a complete trust justification.",
                recommendation="Add concise, factual trust evidence to the homepage, About page, or relevant offering page.", impact=4, effort=2,
            )
        return _absence_result(
            "trust",
            fallback_url,
            "No specific certification, policy, customer proof, or other visible trust explanation was detected in crawled content.",
            "The audited pages do not give visitors a clear, evidence-based reason to trust the organization.",
            "Add factual, verifiable trust signals with supporting context on a primary page.",
            impact=4,
            effort=2,
        )

    def _differentiation_result(
        self, primary_entity: PrimaryEntityContext, pages: list[CrawledPage], fallback_url: str
    ) -> AnswerabilityResult:
        clear = _first_candidate(
            primary_entity, pages, _has_specific_differentiator,
            question_id="differentiation", roles=("comparison", "alternative", "home", "product"),
        )
        if clear:
            return _result(
                "differentiation", AnswerStatus.CLEARLY_ANSWERED, Confidence.MEDIUM, clear,
                explanation="A content passage explains a difference using a comparison or a concrete distinguishing attribute.",
                recommendation="Keep differentiators specific and supported by the surrounding content.", impact=3, effort=1,
            )
        partial = _first_candidate(
            primary_entity, pages, _has_generic_differentiator,
            question_id="differentiation", roles=("comparison", "alternative", "home", "product"),
        )
        if partial:
            return _result(
                "differentiation", AnswerStatus.PARTIALLY_ANSWERED, Confidence.LOW, partial,
                explanation="The site uses a broad superiority claim, but it does not explain the basis for comparison.",
                recommendation="State one concrete difference, the relevant alternative or workflow, and the resulting visitor benefit.", impact=3, effort=2,
            )
        return _absence_result(
            "differentiation",
            fallback_url,
            "No comparison, alternative, or concrete differentiator statement was detected in crawled content.",
            "The audited pages do not explain how the offering differs from alternatives.",
            "Add a concise, factual differentiator statement with the context visitors need to understand it.",
            impact=3,
            effort=2,
        )

    def _next_action_result(
        self, primary_entity: PrimaryEntityContext, pages: list[CrawledPage], fallback_url: str
    ) -> AnswerabilityResult:
        cta_candidates: list[Candidate] = []
        roles = ("home", "product", "service", "contact", "pricing")
        for page in _ordered_pages(pages, roles):
            if _is_legal_page(page) or _is_low_priority_noise_page(page):
                continue
            if _page_priority(page, roles) <= 0:
                continue
            cta_items = [
                (signal.label, signal.location, signal.near_primary_heading)
                for signal in page.call_to_action_signals
            ] or [(label, None, False) for label in page.call_to_action_labels]
            for label, location, near_primary_heading in cta_items:
                if location in {"footer", "aside"}:
                    continue
                if CTA_PATTERN.search(label) and not GENERIC_CTA_PATTERN.fullmatch(label.strip()):
                    candidate = _candidate(
                        primary_entity,
                        page,
                        label,
                        "call-to-action button or link",
                        question_id="next_action",
                        page_priority=_page_priority(page, roles),
                        answer_reason="The label gives the visitor a concrete next action.",
                        allow_page_scope=True,
                    )
                    if candidate:
                        cta_candidates.append(
                            replace(
                                candidate,
                                relevance_score=candidate.relevance_score + (1 if near_primary_heading else 0),
                            )
                        )
        if cta_candidates:
            candidate = max(cta_candidates, key=lambda item: (item.page_priority, item.relevance_score))
            return _result(
                "next_action", AnswerStatus.CLEARLY_ANSWERED, Confidence.HIGH, candidate,
                explanation="The highest-priority relevant page contains a specific call-to-action button or link.",
                recommendation="Keep the primary call to action visible and consistent with the page purpose.", impact=3, effort=1,
            )
        action = _first_candidate(
            primary_entity, pages, _has_cta_instruction,
            question_id="next_action", roles=roles,
        )
        if action:
            return _result(
                "next_action", AnswerStatus.CLEARLY_ANSWERED, Confidence.MEDIUM, action,
                explanation="A visible content passage gives visitors a specific next step.",
                recommendation="Keep the next-step instruction near the relevant offering or decision point.", impact=3, effort=1,
            )
        return _absence_result(
            "next_action",
            fallback_url,
            "No specific call-to-action button, link, or content instruction was detected in crawled pages.",
            "The site does not give visitors a clear, explicit next step after reading the available content.",
            "Add one primary call to action such as starting a trial, contacting the organization, requesting a quote, or signing up.",
            impact=3,
            effort=1,
        )


def _result(
    question_id: str,
    status: AnswerStatus,
    confidence: Confidence,
    candidate: Candidate,
    *,
    explanation: str,
    recommendation: str,
    impact: int,
    effort: int,
    additional: list[Candidate] | None = None,
    conflicting_excerpt: str | None = None,
) -> AnswerabilityResult:
    candidates = [candidate, *(additional or [])]
    return AnswerabilityResult(
        question=QUESTIONS[question_id],
        status=status,
        confidence=confidence,
        answer_excerpt=candidate.excerpt,
        supporting_urls=_ordered_unique(item.page_url for item in candidates if item.page_url),
        evidence=[_answer_evidence(item) for item in candidates],
        conflicting_excerpt=conflicting_excerpt,
        explanation=explanation,
        recommendation=recommendation,
        impact=impact,
        effort=effort,
    )


def _absence_result(
    question_id: str,
    fallback_url: str,
    absence_evidence: str,
    explanation: str,
    recommendation: str,
    *,
    impact: int,
    effort: int,
) -> AnswerabilityResult:
    candidate = Candidate(fallback_url, absence_evidence, "crawled page audit")
    return AnswerabilityResult(
        question=QUESTIONS[question_id],
        status=AnswerStatus.NOT_ANSWERED,
        confidence=Confidence.MEDIUM,
        answer_excerpt=None,
        supporting_urls=[],
        evidence=[_answer_evidence(candidate)] if fallback_url else [],
        explanation=explanation,
        recommendation=recommendation,
        impact=impact,
        effort=effort,
    )


def _not_applicable_result(
    question_id: str,
    candidate: Candidate,
    explanation: str,
    recommendation: str,
    *,
    confidence: Confidence = Confidence.HIGH,
) -> AnswerabilityResult:
    return AnswerabilityResult(
        question=QUESTIONS[question_id],
        status=AnswerStatus.NOT_APPLICABLE,
        confidence=confidence,
        answer_excerpt=candidate.excerpt,
        supporting_urls=[candidate.page_url] if candidate.page_url else [],
        evidence=[_answer_evidence(candidate)],
        explanation=explanation,
        recommendation=recommendation,
        impact=1,
        effort=1,
    )


def _answer_evidence(candidate: Candidate) -> AnswerEvidence:
    return AnswerEvidence(
        page_url=candidate.page_url,
        excerpt=candidate.excerpt,
        source_type=candidate.source_type,
        context=candidate.context,
        answer_reason=candidate.answer_reason,
        entity_relevance_reason=candidate.entity_relevance_reason,
        relevance_score=candidate.relevance_score,
    )


def _finding_for_result(
    result: AnswerabilityResult,
    fallback_url: str,
) -> DiscoverabilityFinding | None:
    if result.status in {AnswerStatus.CLEARLY_ANSWERED, AnswerStatus.NOT_APPLICABLE}:
        return None
    title, severity, why_it_matters = _finding_details(result.question.id, result.status)
    affected_url = result.supporting_urls[0] if result.supporting_urls else fallback_url
    evidence = [
        Evidence(
            page_url=item.page_url,
            exact_text=item.excerpt,
            source_type=item.source_type,
            context=item.context,
        )
        for item in result.evidence
    ]
    return DiscoverabilityFinding(
        id=f"answerability-{uuid4().hex}",
        category=AuditCategory.ANSWERABILITY,
        title=title,
        severity=severity,
        confidence=result.confidence,
        affected_url=affected_url,
        evidence=evidence,
        why_it_matters=why_it_matters,
        recommendation=result.recommendation,
        copy_paste_fix=None,
        impact=result.impact,
        effort=result.effort,
    )


def _finding_details(question_id: str, status: AnswerStatus) -> tuple[str, Severity, str]:
    if status == AnswerStatus.CONFLICTING_ANSWER:
        return (
            "Contradictory organization descriptions",
            Severity.HIGH,
            "Conflicting primary descriptions can leave visitors and answer systems unsure which statement represents the organization.",
        )
    details = {
        "purpose": ("Core purpose is not clearly explained", Severity.HIGH, "A clear purpose lets visitors and answer systems identify what the organization does without guessing."),
        "audience": ("Target audience is unclear", Severity.MEDIUM, "Visitors and answer systems need a specific audience statement to judge relevance."),
        "offerings": ("Products or services are not clearly described", Severity.HIGH, "Undescribed offerings are difficult to retrieve, summarize, and match to a visitor need."),
        "location": ("Geographic coverage is unclear where relevant", Severity.MEDIUM, "Location or service-area details can determine whether an offering is available to a visitor."),
        "contact": ("Contact or engagement method is unclear", Severity.MEDIUM, "Visitors need a direct way to contact or engage with the organization after finding it."),
        "pricing": ("Pricing is not findable where commercially relevant", Severity.MEDIUM, "When a paid offering is implied, a clear price or quote path helps visitors make an informed next step."),
        "trust": ("Trust justification is weak", Severity.MEDIUM, "Specific, supportable trust signals give visitors and answer systems a reason to rely on the organization."),
        "differentiation": ("Differentiation from alternatives is unclear", Severity.LOW, "Concrete differences help visitors understand why this offering may fit better than alternatives."),
        "next_action": ("Next action is unclear", Severity.LOW, "A clear next step helps visitors act after they understand the offering."),
    }
    return details[question_id]


def _summary(results: Iterable[AnswerabilityResult]) -> AnswerabilitySummary:
    counts = {status: 0 for status in AnswerStatus}
    for result in results:
        counts[result.status] += 1
    return AnswerabilitySummary(
        clearly_answered=counts[AnswerStatus.CLEARLY_ANSWERED],
        partially_answered=counts[AnswerStatus.PARTIALLY_ANSWERED],
        not_answered=counts[AnswerStatus.NOT_ANSWERED],
        conflicting_answer=counts[AnswerStatus.CONFLICTING_ANSWER],
        not_applicable=counts[AnswerStatus.NOT_APPLICABLE],
    )


def _primary_entity_context(
    pages: list[CrawledPage],
    site_url: str | None,
) -> PrimaryEntityContext:
    """Establish the audited publisher before evaluating any answer candidate."""

    homepage = _homepage_page(pages, site_url)
    homepage_url = homepage.url if homepage else site_url
    choices: list[tuple[int, str, str | None]] = []
    aliases: list[str] = []
    if homepage:
        for item in _json_ld_nodes(homepage.json_ld):
            types = _schema_types(item)
            if not (types & {"organization", "corporation", "localbusiness", "professionalservice", "website"}):
                continue
            name = _clean_entity_name(item.get("name") or item.get("legalName"))
            if name:
                entity_type = "Organization" if types - {"website"} else "WebSite"
                choices.append((10 if entity_type == "Organization" else 9, name, entity_type))
                aliases.append(name)
        site_name = homepage.open_graph.get("og:site_name")
        if site_name:
            choices.append((8, _clean_entity_name(site_name), "WebSite"))
            aliases.append(_clean_entity_name(site_name))
        if homepage.title:
            choices.append((5, _clean_entity_name(homepage.title), "WebSite"))
        for heading in homepage.headings:
            if heading.level == 1:
                choices.append((4, _clean_entity_name(heading.text), "WebSite"))
                break
    hostname = urlsplit(homepage_url or "").hostname or ""
    host_alias = hostname.lower().removeprefix("www.")
    if host_alias:
        choices.append((3, host_alias.split(".")[0], "WebSite"))
        aliases.extend([host_alias, host_alias.split(".")[0]])

    choices = [(score, name, entity_type) for score, name, entity_type in choices if name]
    choices.sort(key=lambda item: (-item[0], len(item[1])))
    entity_name = choices[0][1] if choices else None
    entity_type = choices[0][2] if choices else None
    if entity_name:
        aliases.append(entity_name)
    aliases = _ordered_unique(_clean_entity_name(value) for value in aliases if _is_useful_alias(value))
    confidence = (
        Confidence.HIGH
        if choices and choices[0][0] >= 9
        else Confidence.MEDIUM
        if entity_name
        else Confidence.LOW
    )
    return PrimaryEntityContext(
        entity_name=entity_name,
        aliases=aliases,
        entity_type=entity_type,
        homepage_url=homepage_url,
        confidence=confidence,
    )


def _homepage_page(pages: list[CrawledPage], site_url: str | None) -> CrawledPage | None:
    if not pages:
        return None
    requested_host = urlsplit(site_url or "").hostname
    for page in pages:
        parts = urlsplit(page.url)
        if not parts.path.strip("/") and (not requested_host or parts.hostname == requested_host):
            return page
    return pages[0]


def _json_ld_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _json_ld_nodes(item)
    elif isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _json_ld_nodes(item)


def _schema_types(item: dict[str, Any]) -> set[str]:
    values = item.get("@type", [])
    if isinstance(values, str):
        values = [values]
    return {str(value).lower() for value in values}


def _clean_entity_name(value: Any) -> str:
    text = " ".join(str(value or "").replace("|", " - ").split())
    text = re.sub(r"^(?:welcome to|official website of|the official website of)\s+", "", text, flags=re.I)
    return re.split(r"\s[-:|]\s", text, maxsplit=1)[0].strip()


def _is_useful_alias(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", value.lower())
    return len(normalized) >= 3 and normalized not in {"www", "website", "home"}


def _first_candidate(
    primary_entity: PrimaryEntityContext,
    pages: list[CrawledPage],
    predicate: Callable[[str, CrawledPage], bool],
    *,
    question_id: str,
    roles: tuple[str, ...],
) -> Candidate | None:
    candidates: list[Candidate] = []
    for page in _ordered_pages(pages, roles):
        page_priority = _page_priority(page, roles)
        for block in _answer_blocks(page):
            for excerpt in _sentences(block.text):
                if not predicate(excerpt, page):
                    continue
                candidate = _candidate(
                    primary_entity,
                    page,
                    excerpt,
                    _source_type(block),
                    question_id=question_id,
                    page_priority=page_priority,
                    answer_reason=_answer_reason(question_id, excerpt),
                )
                if candidate:
                    candidates.append(candidate)
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.relevance_score, item.page_priority, len(item.excerpt)))


def _candidate(
    primary_entity: PrimaryEntityContext,
    page: CrawledPage,
    text: str,
    source_type: str,
    *,
    question_id: str,
    page_priority: int,
    answer_reason: str,
    allow_page_scope: bool = False,
) -> Candidate | None:
    """Score one candidate and reject weakly attributed or noisy content."""

    reasons: list[str] = []
    entity_points = 0
    alias = _matching_alias(text, primary_entity.aliases)
    first_person = bool(FIRST_PERSON_PATTERN.search(text))
    page_scoped = _page_scoped_to_entity(page, primary_entity)
    structured = _page_structured_for_entity(page, primary_entity)
    external_subject = bool(EXTERNAL_SUBJECT_PATTERN.search(text)) and not alias and not first_person

    if question_id == "differentiation" and not (alias or first_person):
        return None

    if alias:
        entity_points += 7
        reasons.append(f'Primary entity alias "{alias}" appears in the excerpt')
    if first_person:
        entity_points += 5
        reasons.append("The excerpt uses first-person publisher language")
    if structured:
        entity_points += 3
        reasons.append("Relevant page structured data names the primary entity")
    if page_scoped and not external_subject:
        entity_points += 4
        reasons.append("The page title or H1 is scoped to the primary entity")
    if allow_page_scope and page_scoped:
        entity_points += 2

    if not reasons:
        return None

    negative_points = 0
    third_party_context = (
        THIRD_PARTY_CONTEXT_PATTERN.search(text)
        or _is_external_relationship(text, primary_entity.aliases)
        or _is_low_priority_noise_page(page)
    )
    if question_id in {"purpose", "audience", "offerings", "pricing", "location", "differentiation"}:
        if external_subject:
            negative_points += 14
            reasons.append("Rejected because the excerpt names another entity as its subject")
        if third_party_context:
            negative_points += 14
            reasons.append("Rejected because the page or excerpt is customer, partner, case-study, grant, or cited-content context")
    if question_id == "pricing" and PRICE_NEGATIVE_PATTERN.search(text):
        negative_points += 16
        reasons.append("Rejected because the amount appears in statistic, funding, grant, revenue, or transaction context")
    if question_id == "next_action" and (_is_legal_page(page) or _is_low_priority_noise_page(page)):
        return None

    completeness = 2 if _word_count(text) >= 8 else 1
    score = entity_points + (page_priority * 2) + completeness + 3 - negative_points
    if score < MIN_CANDIDATE_SCORE:
        return None
    return Candidate(
        page_url=page.url,
        excerpt=_excerpt(text),
        source_type=source_type,
        answer_reason=answer_reason,
        entity_relevance_reason="; ".join(reasons),
        relevance_score=score,
        page_priority=page_priority,
    )


def _is_external_relationship(text: str, aliases: Iterable[str]) -> bool:
    """Recognize a customer or partner speaking about the primary entity, not as it."""

    for alias in aliases:
        if re.search(
            rf"\b(?:partnering|partnered|partners?|working|worked|collaborating|collaborated)\s+with\s+(?:the\s+)?{re.escape(alias)}\b",
            text,
            re.I,
        ):
            return True
        if re.search(
            rf"\b(?:company|customer|retailer|merchant|business)\b.{{0,70}}\bcalled\s+on\s+(?:the\s+)?{re.escape(alias)}\b",
            text,
            re.I,
        ):
            return True
    return False


def _matching_alias(text: str, aliases: Iterable[str]) -> str | None:
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.I):
            return alias
    return None


def _page_scoped_to_entity(page: CrawledPage, primary_entity: PrimaryEntityContext) -> bool:
    labels = [page.title or "", *(heading.text for heading in page.headings if heading.level == 1)]
    return any(_matching_alias(label, primary_entity.aliases) for label in labels)


def _page_structured_for_entity(page: CrawledPage, primary_entity: PrimaryEntityContext) -> bool:
    for item in _json_ld_nodes(page.json_ld):
        if _matching_alias(str(item.get("name") or item.get("legalName") or ""), primary_entity.aliases):
            return True
    return False


def _ordered_pages(pages: list[CrawledPage], roles: tuple[str, ...]) -> list[CrawledPage]:
    indexed = list(enumerate(pages))
    return [
        page
        for _, page in sorted(
            indexed,
            key=lambda item: (-_page_priority(item[1], roles), item[0]),
        )
    ]


def _page_priority(page: CrawledPage, roles: tuple[str, ...]) -> int:
    labels = _page_labels(page)
    for index, role in enumerate(roles):
        if role in labels:
            return len(roles) - index
    return 0


def _page_labels(page: CrawledPage) -> set[str]:
    path = urlsplit(page.url).path.strip("/").lower()
    label_text = " ".join(
        [path, page.title or "", *(heading.text for heading in page.headings[:2])]
    ).lower()
    labels: set[str] = {"home"} if not path else set()
    role_terms = {
        "about": ("about", "mission", "who we are"),
        "company": ("company", "organization", "team"),
        "service": ("service", "solution", "consult", "training"),
        "product": ("product", "platform", "software", "feature", "app"),
        "pricing": ("pricing", "price", "plan", "quote"),
        "plan": ("plan",),
        "checkout": ("checkout",),
        "billing": ("billing",),
        "faq": ("faq", "frequently asked"),
        "contact": ("contact", "support", "get in touch"),
        "support": ("support", "help center"),
        "locations": ("locations", "location", "offices"),
        "service_area": ("service area", "where we serve", "coverage"),
        "security": ("security",),
        "compliance": ("compliance", "privacy", "trust center"),
        "case_study": ("case study", "customer story"),
        "comparison": ("compare", "comparison"),
        "alternative": ("alternative", "versus", "vs"),
    }
    for role, terms in role_terms.items():
        if any(term in label_text for term in terms):
            labels.add(role)
    return labels


def _is_low_priority_noise_page(page: CrawledPage) -> bool:
    descriptor = " ".join([urlsplit(page.url).path, page.title or "", *(heading.text for heading in page.headings[:2])])
    return bool(NOISE_PAGE_PATTERN.search(descriptor))


def _is_legal_page(page: CrawledPage) -> bool:
    descriptor = " ".join([urlsplit(page.url).path, page.title or "", *(heading.text for heading in page.headings[:2])])
    return bool(LEGAL_PAGE_PATTERN.search(descriptor))


def _answer_blocks(page: CrawledPage) -> list[ContentBlock]:
    """Return descriptive page content only; headings and nav labels are excluded."""

    return [block for block in page.content_blocks if block.kind in {"paragraph", "list_item", "table", "button"}]


def _sentences(text: str) -> list[str]:
    return [segment.strip() for segment in SENTENCE_PATTERN.split(text) if segment.strip()]


def _source_type(block: ContentBlock) -> str:
    return {
        "paragraph": "HTML paragraph",
        "list_item": "HTML list item",
        "table": "HTML table",
        "button": "HTML button",
    }.get(block.kind, "visible page content")


def _answer_reason(question_id: str, _excerpt: str) -> str:
    """State why the detected pattern is relevant without inventing an answer."""

    reasons = {
        "purpose": "The excerpt uses a descriptive purpose or offering statement.",
        "audience": "The excerpt identifies a meaningful intended audience.",
        "offerings": "The excerpt names a product, service, or offering with surrounding description.",
        "location": "The excerpt contains explicit geographic or operating-scope evidence.",
        "contact": "The excerpt provides a direct contact or engagement method.",
        "pricing": "The excerpt places an amount or pricing route in explicit pricing context.",
        "trust": "The excerpt contains a visible trust-related signal.",
        "differentiation": "The excerpt uses explicit comparison or differentiation language.",
        "next_action": "The excerpt gives a concrete next action to a visitor.",
    }
    return reasons[question_id]


def _excerpt(text: str, limit: int = 350) -> str:
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"


def _word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def _purpose_strength(text: str) -> int:
    if not PURPOSE_VERB_PATTERN.search(text):
        return 0
    if not (OFFERING_PATTERN.search(text) or PURPOSE_TYPE_PATTERN.search(text)):
        return 0
    return 2 if _word_count(text) >= 9 else 1


def _has_specific_audience(text: str, _page: CrawledPage) -> bool:
    if _word_count(text) < 7 or STATISTIC_CONTEXT_PATTERN.search(text):
        return False
    for match in AUDIENCE_PATTERN.finditer(text):
        audience = {word.lower() for word in WORD_PATTERN.findall(match.group(1))}
        if audience & AUDIENCE_TERMS and not audience <= GENERIC_AUDIENCES:
            return True
    return False


def _has_generic_audience(text: str, _page: CrawledPage) -> bool:
    if _word_count(text) < 5 or STATISTIC_CONTEXT_PATTERN.search(text):
        return False
    for match in AUDIENCE_PATTERN.finditer(text):
        audience = {word.lower() for word in WORD_PATTERN.findall(match.group(1))}
        if audience and (audience <= GENERIC_AUDIENCES or not audience & AUDIENCE_TERMS):
            return True
    return False


def _offering_strength(text: str) -> int:
    if not OFFERING_PATTERN.search(text):
        return 0
    action = re.search(r"\b(?:offers?|provides?|includes?|delivers?|our)\b", text, re.I)
    if action and _word_count(text) >= 8:
        return 2
    return 1 if _word_count(text) >= 4 else 0


def _is_noncommercial(text: str, _page: CrawledPage) -> bool:
    return bool(NONCOMMERCIAL_PATTERN.search(text)) and _word_count(text) >= 5


def _is_commercial(primary_entity: PrimaryEntityContext, pages: list[CrawledPage]) -> bool:
    return bool(
        _first_candidate(
            primary_entity,
            pages,
            lambda text, _page: bool(COMMERCIAL_PATTERN.search(text)) and not bool(PRICE_NEGATIVE_PATTERN.search(text)),
            question_id="pricing",
            roles=("pricing", "plan", "product", "checkout", "billing"),
        )
    )


def _has_numeric_pricing(text: str, _page: CrawledPage) -> bool:
    if PRICE_NEGATIVE_PATTERN.search(text):
        return False
    return bool(CURRENCY_PATTERN.search(text) and PRICE_CONTEXT_PATTERN.search(text))


def _has_pricing_contact_path(text: str, _page: CrawledPage) -> bool:
    return bool(PRICE_CONTACT_PATTERN.search(text)) and _word_count(text) >= 4


def _visible_address_candidate(
    primary_entity: PrimaryEntityContext,
    pages: list[CrawledPage],
) -> Candidate | None:
    for page in _ordered_pages(pages, ("contact", "about", "home")):
        if page.visible_addresses:
            candidate = _candidate(
                primary_entity,
                page,
                page.visible_addresses[0],
                "visible postal address",
                question_id="location",
                page_priority=_page_priority(page, ("contact", "locations", "service_area", "about")),
                answer_reason="The excerpt is a visible postal address for the audited organization.",
                allow_page_scope=True,
            )
            if candidate:
                return candidate
    return None


def _has_location_statement(text: str, _page: CrawledPage) -> bool:
    if _word_count(text) < 5:
        return False
    if re.search(
        r"\bavailable\s+in\s+\d+\s+countries\b|"
        r"\b(?:available|operate|operating|serve|serving|support(?:ed)?)\b.{0,40}"
        r"\b(?:worldwide|globally|supported countries)\b",
        text,
        re.I,
    ):
        return True
    match = LOCATION_PATTERN.search(text)
    if not match:
        return False
    location_value = match.group(0)
    return bool(re.search(r"\b[A-Z][A-Za-z.'-]{2,}\b|\b\d+\s+countries\b", location_value))


def _is_global_digital(text: str, _page: CrawledPage) -> bool:
    visible_text = re.sub(r"https?://\S+", "", text)
    return bool(
        GLOBAL_AVAILABILITY_PATTERN.search(visible_text) and DIGITAL_PATTERN.search(visible_text)
    ) and _word_count(visible_text) >= 6


def _has_contact_method(text: str, _page: CrawledPage) -> bool:
    if re.search(r"(?:print\s*\(|\b(?:example\s+code|code\s+example)\b|\b(?:let|var|const)\s+\w+\s*=)", text, re.I):
        return False
    return bool(EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text) or CONTACT_PATTERN.search(text))


def _has_strong_trust_signal(text: str, _page: CrawledPage) -> bool:
    if re.search(r"\bcertified\s+partners?\b|\bpartners?\b.{0,20}\bcertified\b", text, re.I):
        return False
    return bool(TRUST_STRONG_PATTERN.search(text)) and _word_count(text) >= 5


def _has_partial_trust_signal(text: str, _page: CrawledPage) -> bool:
    return bool(TRUST_PARTIAL_PATTERN.search(text)) and _word_count(text) >= 5


def _available_policy_candidate(entity_trust: EntityTrustAnalysis | None) -> Candidate | None:
    if entity_trust is None:
        return None
    for policy in entity_trust.trust_policy_pages:
        if policy.available:
            return Candidate(
                policy.url,
                f"A crawled {policy.policy_type} page is available at {policy.url}.",
                "Phase 4 trust policy signal",
                answer_reason="A published policy page is a limited visible trust signal.",
                entity_relevance_reason="Phase 4 detected the policy page within the audited site crawl.",
                relevance_score=MIN_CANDIDATE_SCORE,
            )
    return None


def _phase4_credibility_candidate(entity_trust: EntityTrustAnalysis | None) -> Candidate | None:
    """Reuse only exact Phase 4 signals that were extracted from crawled page content."""

    if entity_trust is None:
        return None
    for signal in entity_trust.credibility_signals:
        for value, label in (
            *((item, "visible certification or award") for item in signal.certifications_or_awards),
            *((item, "visible customer proof") for item in signal.customer_logo_signals),
            *((item, "visible testimonial signal") for item in signal.testimonial_signals),
            *((item, "visible case-study signal") for item in signal.case_study_signals),
            *((item, "visible source label") for item in signal.named_source_labels),
        ):
            return Candidate(
                signal.page_url,
                value,
                f"Phase 4 {label}",
                answer_reason="Phase 4 extracted this visible credibility signal from the audited crawl.",
                entity_relevance_reason="The signal was extracted from a crawled page on the audited site.",
                relevance_score=MIN_CANDIDATE_SCORE,
            )
    return None


def _has_specific_differentiator(text: str, _page: CrawledPage) -> bool:
    return bool(DIFFERENTIATOR_PATTERN.search(text)) and _word_count(text) >= 8


def _has_generic_differentiator(text: str, _page: CrawledPage) -> bool:
    return bool(GENERIC_DIFFERENTIATOR_PATTERN.search(text)) and _word_count(text) >= 5


def _has_cta_instruction(text: str, _page: CrawledPage) -> bool:
    return bool(CTA_PATTERN.search(text)) and not bool(GENERIC_CTA_PATTERN.fullmatch(text.strip()))


def _purpose_conflict(
    primary_entity: PrimaryEntityContext,
    pages: list[CrawledPage],
) -> tuple[Candidate, Candidate] | None:
    """Only flag directly stated, mutually exclusive organization classifications."""

    seen: dict[str, Candidate] = {}
    mutually_exclusive = (
        {"nonprofit", "commercial"},
        {"nonprofit", "for-profit"},
        {"government", "commercial"},
        {"public-sector", "commercial"},
    )
    for page in _ordered_pages(pages, ("home", "about")):
        for block in _answer_blocks(page):
            for text in _sentences(block.text):
                match = PURPOSE_CLASS_PATTERN.search(text)
                if not match:
                    continue
                kind = _normalized_purpose_class(match.group("kind"))
                candidate = _candidate(
                    primary_entity,
                    page,
                    text,
                    _source_type(block),
                    question_id="purpose",
                    page_priority=_page_priority(page, ("home", "about", "company")),
                    answer_reason="The excerpt directly classifies the primary organization.",
                )
                if candidate is None:
                    continue
                for first_kind, first_candidate in seen.items():
                    if {first_kind, kind} in mutually_exclusive and first_candidate.page_url != candidate.page_url:
                        return first_candidate, candidate
                seen.setdefault(kind, candidate)
    return None


def _normalized_purpose_class(value: str) -> str:
    value = value.lower().replace("_", " ")
    if "non" in value or "not" in value:
        return "nonprofit"
    if "for" in value:
        return "for-profit"
    if "government" in value:
        return "government"
    if "public" in value:
        return "public-sector"
    return "commercial" if "commercial" in value else value


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
