"""Deterministic checks for entity clarity, attribution, and visible trust signals."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from ..models import (
    AuditCategory,
    AuthorEditorialSignal,
    BusinessContactDetail,
    CompanyPageSignal,
    Confidence,
    CrawledPage,
    CrawlWarning,
    DiscoverabilityFinding,
    EntityIdentitySignal,
    EntityTrustAnalysis,
    Evidence,
    ExternalCredibilitySignal,
    ExternalLinkSignal,
    OrganizationStructuredData,
    Severity,
    SocialProfileSignal,
    TrustPolicySignal,
)
from ..url_utils import is_same_domain, normalize_url


ORGANIZATION_TYPES = {
    "organization",
    "corporation",
    "localbusiness",
    "professionalservice",
    "softwareapplication",
}
WEBSITE_TYPES = {"website"}
PERSON_TYPES = {"person"}
ARTICLE_TYPES = {"article", "newsarticle", "blogposting", "report", "techarticle"}
PERSON_TYPE = "person"
COMPANY_PAGE_KEYWORDS = {
    "about": ("about", "company", "team"),
    "contact": ("contact",),
    "support": ("support", "help"),
}
POLICY_KEYWORDS = {
    "Privacy Policy": ("privacy",),
    "Terms of Service": ("terms", "conditions"),
    "Security": ("security",),
    "Cookie Policy": ("cookie",),
    "Accessibility": ("accessibility",),
    "Refund or cancellation policy": ("refund", "cancellation", "returns"),
}
SOCIAL_NETWORKS = {
    "linkedin.com": "LinkedIn",
    "twitter.com": "X/Twitter",
    "x.com": "X/Twitter",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "github.com": "GitHub",
    "crunchbase.com": "Crunchbase",
    "wikidata.org": "Wikidata",
    "wikipedia.org": "Wikipedia",
}
LEGAL_NAME_TOKENS = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "plc",
    "gmbh",
    "sa",
}
EDITORIAL_PATH_PATTERN = re.compile(r"/(?:blog|article|articles|guide|guides|resource|resources|insights|news)(?:/|$)", re.I)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{6,}\d)(?!\w)")
BYLINE_PATTERN = re.compile(r"\bby\s+([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})\b")
SOURCE_PATTERN = re.compile(r"\b(?:sources?|references?|according to|research from|study by)\b", re.I)
AWARD_PATTERN = re.compile(r"\b(?:award-winning|award|certified|certification|accredited)\b", re.I)
TESTIMONIAL_PATTERN = re.compile(r"\b(?:testimonials?|what our customers say|customer stories?)\b", re.I)
CASE_STUDY_PATTERN = re.compile(r"\b(?:case stud(?:y|ies)|success stor(?:y|ies))\b", re.I)
WORD_PATTERN = re.compile(r"\b[\w'-]+\b")
COPYRIGHT_PATTERN = re.compile(r"(?:©|copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?\s*)?(.+)", re.I)


class EntityTrustAnalyzer:
    """Assess evidence that helps systems identify an organization and its expertise."""

    def analyze(
        self,
        site_url: str,
        pages: list[CrawledPage],
        warnings: list[CrawlWarning] | None = None,
    ) -> EntityTrustAnalysis:
        """Return deterministic, unscored Entity and Trust results for a completed crawl."""

        entities = _structured_entities(pages)
        organization_data = [entity for entity in entities if entity.entity_type == "organization"]
        person_entities = [entity for entity in entities if entity.entity_type == "person"]
        website_entities = [entity for entity in entities if entity.entity_type == "website"]
        article_entities = [entity for entity in entities if entity.entity_type == "article"]
        company_pages = _company_pages(pages, warnings or [])
        structured_focus_pages = _structured_focus_pages(site_url, pages, company_pages)
        identity_focus_pages = _identity_focus_pages(site_url, pages, company_pages)
        identity_signals = _identity_signals(identity_focus_pages, organization_data, website_entities)
        contact_details = _contact_details(pages, organization_data)
        editorial_signals = _editorial_signals(pages)
        credibility_signals = _credibility_signals(pages)
        trust_policy_pages = _trust_policy_pages(pages, warnings or [])
        social_profiles, malformed_same_as = _social_profiles(
            pages,
            organization_data,
            website_entities,
        )

        findings: list[DiscoverabilityFinding] = []
        findings.extend(
            self._structured_data_findings(
                structured_focus_pages,
                organization_data,
                person_entities,
                website_entities,
            )
        )
        findings.extend(self._identity_findings(identity_focus_pages, identity_signals, organization_data))
        findings.extend(self._company_page_findings(site_url, pages, company_pages))
        findings.extend(self._contact_findings(site_url, contact_details))
        findings.extend(self._editorial_findings(editorial_signals, pages))
        findings.extend(self._trust_policy_findings(site_url, pages, trust_policy_pages))
        findings.extend(self._social_findings(site_url, social_profiles, malformed_same_as))

        return EntityTrustAnalysis(
            organization_data=organization_data,
            person_entities=person_entities,
            website_entities=website_entities,
            article_entities=article_entities,
            identity_signals=identity_signals,
            company_pages=company_pages,
            contact_details=contact_details,
            editorial_signals=editorial_signals,
            credibility_signals=credibility_signals,
            trust_policy_pages=trust_policy_pages,
            social_profiles=social_profiles,
            findings=findings,
        )

    def _structured_data_findings(
        self,
        focus_pages: list[CrawledPage],
        organization_data: list[OrganizationStructuredData],
        person_entities: list[OrganizationStructuredData],
        website_entities: list[OrganizationStructuredData],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        focus_urls = {page.url for page in focus_pages}
        focus_records = [record for record in organization_data if record.page_url in focus_urls]
        focus_people = [record for record in person_entities if record.page_url in focus_urls]
        focus_websites = [record for record in website_entities if record.page_url in focus_urls]
        fallback_url = focus_pages[0].url if focus_pages else ""

        if focus_pages and not focus_records:
            findings.append(
                _finding(
                    title="Organization-like structured data was not detected",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_url=fallback_url,
                    evidence=[
                        Evidence(
                            page_url=fallback_url,
                            exact_text=(
                                "No Organization, Corporation, LocalBusiness, ProfessionalService, "
                                "SoftwareApplication JSON-LD object was detected "
                                "on the homepage or an About page."
                            ),
                            source_type="JSON-LD",
                        )
                    ],
                    why_it_matters=(
                        "Structured data gives search and AI systems an explicit, machine-readable "
                        "description of the entity behind a website."
                    ),
                    recommendation=(
                        "Add organization-like JSON-LD to the homepage or About page using only "
                        "accurate organization details."
                    ),
                    impact=3,
                    effort=2,
                )
            )

        for page in focus_pages:
            for warning in page.parse_warnings:
                if "json-ld" in warning.lower():
                    findings.append(
                        _finding(
                            title="Malformed JSON-LD structured data was detected",
                            severity=Severity.MEDIUM,
                            confidence=Confidence.HIGH,
                            affected_url=page.url,
                            evidence=[
                                Evidence(
                                    page_url=page.url,
                                    exact_text=warning,
                                    source_type="HTML parser warning",
                                )
                            ],
                            why_it_matters=(
                                "Malformed JSON-LD may be ignored by systems that rely on structured "
                                "data to identify the organization."
                            ),
                            recommendation="Correct the JSON syntax and validate the published JSON-LD.",
                            impact=3,
                            effort=2,
                        )
                    )

        for record in focus_records:
            if not record.name and not record.legal_name:
                findings.append(
                    _finding(
                        title="Organization structured data is missing a name",
                        severity=Severity.MEDIUM,
                        confidence=Confidence.HIGH,
                        affected_url=record.page_url,
                        evidence=[
                            Evidence(
                                page_url=record.page_url,
                                exact_text=(
                                    f"JSON-LD types: {', '.join(record.schema_types)}; "
                                    "no name or legalName property was detected."
                                ),
                                source_type="JSON-LD",
                            )
                        ],
                        why_it_matters=(
                            "A stable organization name is the primary structured-data signal that "
                            "connects content to its publisher."
                        ),
                        recommendation="Add the organization name to the JSON-LD name property.",
                        impact=3,
                        effort=1,
                    )
                )
            if not record.url:
                findings.append(
                    _finding(
                        title="Organization structured data is missing an official URL",
                        severity=Severity.LOW,
                        confidence=Confidence.HIGH,
                        affected_url=record.page_url,
                        evidence=[
                            Evidence(
                                page_url=record.page_url,
                                exact_text=(
                                    f"JSON-LD types: {', '.join(record.schema_types)}; "
                                    "no url property was detected."
                                ),
                                source_type="JSON-LD",
                            )
                        ],
                        why_it_matters=(
                            "A published canonical organization URL helps connect structured data to the "
                            "website where it appears."
                        ),
                        recommendation="Add the official website URL to the JSON-LD url property.",
                        impact=2,
                        effort=1,
                    )
                )
            if not record.same_as:
                findings.append(
                    _finding(
                        title="Organization structured data has no sameAs profiles",
                        severity=Severity.LOW,
                        confidence=Confidence.HIGH,
                        affected_url=record.page_url,
                        evidence=[
                            Evidence(
                                page_url=record.page_url,
                                exact_text=(
                                    f"JSON-LD types: {', '.join(record.schema_types)}; "
                                    "no sameAs property was detected."
                                ),
                                source_type="JSON-LD",
                            )
                        ],
                        why_it_matters=(
                            "sameAs can help systems connect an entity to official profiles that are "
                            "already publicly visible."
                        ),
                        recommendation=(
                            "Add only verified official profile URLs to sameAs when those profiles are "
                            "intended to represent the organization."
                        ),
                        impact=2,
                        effort=1,
                    )
                )

        findings.extend(_person_field_findings(focus_people))
        findings.extend(_website_field_findings(focus_websites))

        name_pair = _first_conflicting_pair(
            [
                EntityIdentitySignal(
                    page_url=record.page_url,
                    entity_type="organization",
                    source_type="JSON-LD organization name",
                    value=record.name or record.legal_name or "",
                )
                for record in focus_records
                if record.name or record.legal_name
            ]
        )
        if name_pair:
            findings.append(
                _structured_conflict_finding("names", name_pair))

        url_pair = _first_conflicting_url_pair(focus_records)
        if url_pair:
            findings.append(_structured_conflict_finding("URLs", url_pair))
        return findings

    def _identity_findings(
        self,
        focus_pages: list[CrawledPage],
        identity_signals: list[EntityIdentitySignal],
        organization_data: list[OrganizationStructuredData],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        pair = _first_conflicting_pair(identity_signals)
        if pair:
            findings.append(
                _finding(
                    title="Entity Consistency Risk",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    affected_url=pair[0].page_url,
                    evidence=_conflict_evidence(pair),
                    why_it_matters=(
                        "Conflicting organization identity signals can make it harder for search and AI "
                        "systems to determine which entity publishes the content."
                    ),
                    recommendation=(
                        "Review the conflicting public identity labels and standardize them where they "
                        "refer to the same organization."
                    ),
                    impact=4,
                    effort=2,
                )
            )

        focus_urls = {page.url for page in focus_pages}
        url_pair = _first_conflicting_url_pair(
            [record for record in organization_data if record.page_url in focus_urls]
        )
        if url_pair:
            findings.append(
                _finding(
                    title="Entity Consistency Risk",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    affected_url=url_pair[0].page_url,
                    evidence=_url_conflict_evidence(url_pair),
                    why_it_matters=(
                        "Conflicting organization URLs can weaken the connection between an organization "
                        "identity and its official web presence."
                    ),
                    recommendation=(
                        "Use one official organization URL in structured data unless separate legal "
                        "entities are intentionally represented."
                    ),
                    impact=3,
                    effort=1,
                )
            )
        return findings

    def _company_page_findings(
        self,
        site_url: str,
        pages: list[CrawledPage],
        company_pages: list[CompanyPageSignal],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        homepage_url = _homepage_url(site_url, pages)
        for page_type in ("about", "contact"):
            matching = [item for item in company_pages if item.page_type == page_type]
            if not matching:
                findings.append(
                    _finding(
                        title=f"No {page_type.title()} page was detected",
                        severity=Severity.LOW,
                        confidence=Confidence.MEDIUM,
                        affected_url=homepage_url,
                        evidence=[
                            Evidence(
                                page_url=homepage_url,
                                exact_text=(
                                    f"No crawled page or internal link matched the {page_type} page "
                                    "detection terms."
                                ),
                                source_type="internal links and page labels",
                            )
                        ],
                        why_it_matters=(
                            "A clearly discoverable organization page helps readers and systems identify who "
                            "is responsible for the site and how to reach them."
                        ),
                        recommendation=(
                            f"Add a clearly labelled {page_type.title()} page and link to it from an "
                            "important internal navigation area when it is appropriate for the organization."
                        ),
                        impact=2,
                        effort=2,
                    )
                )
                continue

            for signal in matching:
                if signal.available is False:
                    findings.append(
                        _finding(
                            title=f"Linked {page_type.title()} page is unavailable",
                            severity=Severity.MEDIUM,
                            confidence=Confidence.HIGH,
                            affected_url=signal.url,
                            evidence=[
                                Evidence(
                                    page_url=signal.url,
                                    exact_text=(
                                        f"An internal link matching {page_type} was detected, but the "
                                        "crawler recorded an unsuccessful response for this URL."
                                    ),
                                    source_type="crawler response",
                                )
                            ],
                            why_it_matters=(
                                "A broken organization or contact page removes a public trust and attribution "
                                "path that users and systems may rely on."
                            ),
                            recommendation="Restore the page or update the internal link to a working URL.",
                            impact=3,
                            effort=2,
                        )
                    )
                elif signal.available and not signal.has_meaningful_text:
                    findings.append(
                        _finding(
                            title=f"Detected {page_type.title()} page has insufficient visible text",
                            severity=Severity.LOW,
                            confidence=Confidence.HIGH,
                            affected_url=signal.url,
                            evidence=[
                                Evidence(
                                    page_url=signal.url,
                                    exact_text=(
                                        f"Visible word count: {signal.visible_word_count}; the page has "
                                        "fewer than 40 visible words."
                                    ),
                                    source_type="visible page text",
                                )
                            ],
                            why_it_matters=(
                                "Very little visible context may not clearly establish the organization, its "
                                "team, or a reliable way to contact it."
                            ),
                            recommendation=(
                                "Add concise, factual organization or contact information that explains the "
                                "page's purpose."
                            ),
                            impact=2,
                            effort=1,
                        )
                    )
        return findings

    def _contact_findings(
        self,
        site_url: str,
        contact_details: list[BusinessContactDetail],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        details_by_type: dict[str, dict[str, dict[str, str]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        for detail in contact_details:
            if detail.detail_type not in {"email", "telephone", "address", "location"}:
                continue
            normalized_value = _normalized_contact_value(detail.value, detail.detail_type)
            if normalized_value:
                details_by_type[detail.detail_type][normalized_value].setdefault(
                    detail.page_url,
                    detail.value,
                )

        for detail_type, by_value in details_by_type.items():
            values_per_page: dict[str, set[str]] = defaultdict(set)
            for normalized_value, page_values in by_value.items():
                for page_url in page_values:
                    values_per_page[page_url].add(normalized_value)
            # A page that publishes several numbers, inboxes, or locations may
            # intentionally serve different regions or purposes. Do not infer
            # that those values should collapse to one primary organization contact.
            if any(len(page_values) > 1 for page_values in values_per_page.values()):
                continue
            page_urls = {
                page_url
                for page_values in by_value.values()
                for page_url in page_values
            }
            if len(by_value) < 2 or len(page_urls) < 2:
                continue
            evidence: list[Evidence] = []
            for normalized_value, page_values in sorted(by_value.items())[:5]:
                page_url, value = sorted(page_values.items())[0]
                evidence.append(
                    Evidence(
                        page_url=page_url,
                        exact_text=(
                            f"Public {detail_type}: {_redact_contact_value(value, detail_type)}"
                        ),
                            source_type="visible organization contact information",
                    )
                )
            findings.append(
                _finding(
                    title="Public organization contact details may be inconsistent",
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                    affected_url=site_url,
                    evidence=evidence,
                    why_it_matters=(
                        "Different public contact details can make it unclear which organization contact "
                        "channel is current or authoritative."
                    ),
                    recommendation=(
                        "Review the publicly visible organization contact details and standardize the primary "
                        "contact information where the differences are unintended."
                    ),
                    impact=2,
                    effort=2,
                )
            )
        return findings

    def _editorial_findings(
        self,
        editorial_signals: list[AuthorEditorialSignal],
        pages: list[CrawledPage],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        pages_by_url = {page.url: page for page in pages}
        for signal in editorial_signals:
            if not signal.is_editorial or signal.visible_word_count < 300:
                continue
            page = pages_by_url[signal.page_url]
            if not signal.author_names:
                findings.append(
                    _finding(
                        title="Substantial editorial page has no attributable author",
                        severity=Severity.MEDIUM,
                        confidence=Confidence.HIGH,
                        affected_url=signal.page_url,
                        evidence=[
                            Evidence(
                                page_url=signal.page_url,
                                exact_text=(
                                    f"Editorial page word count: {signal.visible_word_count}; no visible "
                                    "byline or JSON-LD author name was detected."
                                ),
                                source_type="visible page text and JSON-LD",
                            )
                        ],
                        why_it_matters=(
                            "Clear authorship helps readers and systems understand who is responsible for "
                            "substantial editorial content."
                        ),
                        recommendation=(
                            "Add an accurate author byline and, where appropriate, connect it to an author "
                            "profile or Article JSON-LD."
                        ),
                        impact=3,
                        effort=2,
                    )
                )
            elif not signal.author_links and not signal.has_author_bio:
                findings.append(
                    _finding(
                        title="Editorial author has no supporting profile or bio",
                        severity=Severity.LOW,
                        confidence=Confidence.MEDIUM,
                        affected_url=signal.page_url,
                        evidence=[
                            Evidence(
                                page_url=signal.page_url,
                                exact_text=f"Detected author: {signal.author_names[0]}",
                                source_type="visible byline or JSON-LD",
                                context="No author link or visible author bio was detected.",
                            )
                        ],
                        why_it_matters=(
                            "A profile or bio provides context about an author's role and expertise without "
                            "requiring systems to infer it."
                        ),
                        recommendation=(
                            "Link the byline to an accurate author profile or add a concise bio with the "
                            "author's relevant role or credentials."
                        ),
                        impact=2,
                        effort=2,
                    )
                )
            if not signal.publication_dates:
                findings.append(
                    _finding(
                        title="Editorial page has no published or updated date",
                        severity=Severity.LOW,
                        confidence=Confidence.MEDIUM,
                        affected_url=signal.page_url,
                        evidence=[
                            Evidence(
                                page_url=signal.page_url,
                                exact_text=(
                                    "No published or updated date was detected in HTML time elements, "
                                    "date metadata, or Article JSON-LD."
                                ),
                                source_type="freshness signals",
                            )
                        ],
                        why_it_matters=(
                            "Visible publication or update dates give readers useful context about editorial "
                            "content without making an automatic recency judgment."
                        ),
                        recommendation=(
                            "Publish an accurate datePublished or dateModified signal when it is appropriate "
                            "for this editorial content."
                        ),
                        impact=2,
                        effort=1,
                    )
                )
        return findings

    def _trust_policy_findings(
        self,
        site_url: str,
        pages: list[CrawledPage],
        policy_pages: list[TrustPolicySignal],
    ) -> list[DiscoverabilityFinding]:
        if not _is_commercial_context(pages):
            return []
        detected = {item.policy_type for item in policy_pages if item.available is not False}
        if "Privacy Policy" in detected or "Terms of Service" in detected:
            return []
        homepage_url = _homepage_url(site_url, pages)
        return [
            _finding(
                title="Core trust policy pages were not detected",
                severity=Severity.LOW,
                confidence=Confidence.LOW,
                affected_url=homepage_url,
                evidence=[
                    Evidence(
                        page_url=homepage_url,
                        exact_text=(
                            "Commercial page signals were detected, but no linked or crawled Privacy Policy "
                            "or Terms page was identified within the bounded crawl."
                        ),
                        source_type="internal links and page labels",
                    )
                ],
                why_it_matters=(
                    "For commercial sites, accessible policy information can give customers important "
                    "context before they share data or make a purchase."
                ),
                recommendation=(
                    "Confirm that applicable privacy and terms information is publicly reachable and linked "
                    "from a suitable navigation area."
                ),
                impact=2,
                effort=2,
            )
        ]

    def _social_findings(
        self,
        site_url: str,
        profiles: list[SocialProfileSignal],
        malformed_same_as: list[SocialProfileSignal],
    ) -> list[DiscoverabilityFinding]:
        findings: list[DiscoverabilityFinding] = []
        visible = [profile for profile in profiles if profile.source_type == "visible social link"]
        same_as = [profile for profile in profiles if profile.source_type == "JSON-LD sameAs"]
        same_as_identities = {_social_identity(profile.url) for profile in same_as}
        missing_profiles = [
            profile for profile in visible if _social_identity(profile.url) not in same_as_identities
        ]
        missing_by_network: dict[str, list[SocialProfileSignal]] = defaultdict(list)
        for profile in missing_profiles:
            missing_by_network[profile.network].append(profile)
        for network, profiles_for_network in missing_by_network.items():
            multiple_candidates = len(profiles_for_network) > 1
            findings.append(
                _finding(
                    title=(
                        f"Multiple potential {network} profiles detected"
                        if multiple_candidates
                        else "Potential official profiles are missing from organization sameAs"
                    ),
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                    affected_url=site_url,
                    evidence=[
                        Evidence(
                            page_url=profile.page_url,
                            exact_text=f"Potential {profile.network} profile detected: {profile.url}",
                            source_type="visible social link",
                            context="; ".join(profile.relevance_signals) or None,
                        )
                        for profile in profiles_for_network
                    ],
                    why_it_matters=(
                        "When a potential profile represents the organization or publisher, matching sameAs data can help "
                        "systems connect the website to that official profile."
                    ),
                    recommendation=(
                        "Verify which profile represents the organization before adding it to sameAs."
                        if multiple_candidates
                        else "Add verified official profile URLs to organization sameAs, or leave them out "
                        "when they are not intended to represent the organization."
                    ),
                    impact=2,
                    effort=1,
                )
            )
        for profile in malformed_same_as:
            findings.append(
                _finding(
                    title="JSON-LD sameAs value appears malformed",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_url=profile.page_url,
                    evidence=[
                        Evidence(
                            page_url=profile.page_url,
                            exact_text=f"sameAs value: {profile.url}",
                            source_type="JSON-LD sameAs",
                        )
                    ],
                    why_it_matters=(
                        "Malformed profile URLs cannot reliably connect structured data to the referenced "
                        "external identity."
                    ),
                    recommendation="Replace the sameAs value with the complete public HTTPS profile URL.",
                    impact=2,
                    effort=1,
                )
            )
        return findings


def _structured_entities(pages: list[CrawledPage]) -> list[OrganizationStructuredData]:
    """Extract and normalize typed JSON-LD entities without mixing their roles."""

    records: list[OrganizationStructuredData] = []
    records_by_identity: dict[tuple[str, str, str], OrganizationStructuredData] = {}
    for page in pages:
        for value in page.json_ld:
            for item, source_property in _json_entity_objects(value):
                types = _schema_types(item)
                entity_type = _entity_type(types)
                if entity_type is None:
                    continue
                record = OrganizationStructuredData(
                    page_url=page.url,
                    entity_type=entity_type,
                    schema_types=types,
                    source_property=source_property,
                    name=_string_value(item.get("name")),
                    legal_name=_string_value(item.get("legalName")),
                    url=_string_value(item.get("url")),
                    logo=_url_or_string(item.get("logo")),
                    description=_string_value(item.get("description")),
                    email=_string_value(item.get("email")),
                    telephone=_string_value(item.get("telephone")),
                    address=_address_value(item.get("address")),
                    location=_address_value(item.get("location")),
                    same_as=_string_list(item.get("sameAs")),
                    founder=_person_or_name(item.get("founder")),
                    founding_date=_string_value(item.get("foundingDate")),
                )
                identity = _entity_identity_key(record)
                existing = records_by_identity.get(identity)
                if existing is None:
                    records_by_identity[identity] = record
                    records.append(record)
                else:
                    _merge_entity_record(existing, record)
    return records


def _company_pages(pages: list[CrawledPage], warnings: list[CrawlWarning]) -> list[CompanyPageSignal]:
    all_internal_links = {link for page in pages for link in page.internal_links}
    crawled_by_url = {page.url: page for page in pages}
    unavailable_urls = {
        warning.url
        for warning in warnings
        if warning.url
        and warning.code
        in {"http_status_skipped", "request_failed", "response_read_failed", "response_too_large"}
    }
    candidates: dict[tuple[str, str], CompanyPageSignal] = {}

    for page in pages:
        for page_type in _company_roles(_page_label(page)):
            candidates[(page_type, page.url)] = CompanyPageSignal(
                page_type=page_type,
                url=page.url,
                internally_linked=page.url in all_internal_links,
                available=True,
                visible_word_count=_word_count(page.text_content),
                has_meaningful_text=_word_count(page.text_content) >= 40,
            )
        for link in page.internal_links:
            for page_type in _company_roles(link):
                if link in crawled_by_url:
                    continue
                candidates[(page_type, link)] = CompanyPageSignal(
                    page_type=page_type,
                    url=link,
                    internally_linked=True,
                    available=False if link in unavailable_urls else None,
                )
    return sorted(candidates.values(), key=lambda item: (item.page_type, item.url))


def _structured_focus_pages(
    site_url: str,
    pages: list[CrawledPage],
    company_pages: list[CompanyPageSignal],
) -> list[CrawledPage]:
    homepage_url = _homepage_url(site_url, pages)
    focus_urls = {homepage_url}
    focus_urls.update(item.url for item in company_pages if item.page_type == "about" and item.available)
    return [page for page in pages if page.url in focus_urls]


def _identity_focus_pages(
    site_url: str,
    pages: list[CrawledPage],
    company_pages: list[CompanyPageSignal],
) -> list[CrawledPage]:
    """Use homepage, About, and Contact labels for cross-page identity comparison."""

    homepage_url = _homepage_url(site_url, pages)
    focus_urls = {homepage_url}
    focus_urls.update(
        item.url
        for item in company_pages
        if item.page_type in {"about", "contact"} and item.available
    )
    return [page for page in pages if page.url in focus_urls]


def _identity_signals(
    pages: list[CrawledPage],
    organization_data: list[OrganizationStructuredData],
    website_entities: list[OrganizationStructuredData],
) -> list[EntityIdentitySignal]:
    signals: list[EntityIdentitySignal] = []
    focus_urls = {page.url for page in pages}
    for record in organization_data:
        if record.page_url not in focus_urls:
            continue
        if record.name:
            signals.append(
                EntityIdentitySignal(
                    page_url=record.page_url,
                    entity_type="organization",
                    source_type="Organization name from JSON-LD",
                    value=record.name,
                )
            )
        if record.legal_name:
            signals.append(
                EntityIdentitySignal(
                    page_url=record.page_url,
                    entity_type="organization",
                    source_type="Organization legalName from JSON-LD",
                    value=record.legal_name,
                )
            )
    for record in website_entities:
        if record.page_url not in focus_urls or not record.name:
            continue
        signals.append(
            EntityIdentitySignal(
                page_url=record.page_url,
                entity_type="website",
                source_type="WebSite name from JSON-LD",
                value=record.name,
            )
        )

    has_organization_entity = any(
        record.page_url in focus_urls for record in organization_data
    )
    if not has_organization_entity:
        return _deduplicate_signals(signals)
    for page in pages:
        og_name = page.open_graph.get("og:site_name")
        if og_name:
            signals.append(
                EntityIdentitySignal(
                    page_url=page.url,
                    entity_type="organization",
                    source_type="Organization name from OpenGraph",
                    value=og_name,
                )
            )
        title_value = _title_identity(page.title)
        if title_value and _matches_known_organization(title_value, organization_data, focus_urls):
            signals.append(
                EntityIdentitySignal(
                    page_url=page.url,
                    entity_type="organization",
                    source_type="Organization name from page title",
                    value=title_value,
                )
            )
        h1_value = _h1_identity(page)
        if h1_value and _matches_known_organization(h1_value, organization_data, focus_urls):
            signals.append(
                EntityIdentitySignal(
                    page_url=page.url,
                    entity_type="organization",
                    source_type="Organization name from H1",
                    value=h1_value,
                )
            )
        footer_value = _footer_identity(page.footer_text)
        if footer_value and _matches_known_organization(footer_value, organization_data, focus_urls):
            signals.append(
                EntityIdentitySignal(
                    page_url=page.url,
                    entity_type="organization",
                    source_type="Organization name from footer copyright",
                    value=footer_value,
                )
            )
    return _deduplicate_signals(signals)


def _contact_details(
    pages: list[CrawledPage],
    organization_data: list[OrganizationStructuredData],
) -> list[BusinessContactDetail]:
    details: list[BusinessContactDetail] = []
    for page in pages:
        visible_text = " ".join([page.text_content, page.footer_text])
        for email in EMAIL_PATTERN.findall(visible_text):
            details.append(BusinessContactDetail(detail_type="email", value=email, page_url=page.url, source_type="visible text"))
        for phone in PHONE_PATTERN.findall(visible_text):
            details.append(BusinessContactDetail(detail_type="telephone", value=phone, page_url=page.url, source_type="visible text"))
        for address in page.visible_addresses:
            details.append(BusinessContactDetail(detail_type="address", value=address, page_url=page.url, source_type="HTML address"))
        if page.has_contact_form:
            details.append(BusinessContactDetail(detail_type="contact form", value="Detected", page_url=page.url, source_type="HTML form"))
        for link in page.internal_links:
            if "support" in link.lower() or "help" in link.lower():
                details.append(BusinessContactDetail(detail_type="support link", value=link, page_url=page.url, source_type="internal link"))
    for record in organization_data:
        if record.email:
            details.append(BusinessContactDetail(detail_type="email", value=record.email, page_url=record.page_url, source_type="JSON-LD"))
        if record.telephone:
            details.append(BusinessContactDetail(detail_type="telephone", value=record.telephone, page_url=record.page_url, source_type="JSON-LD"))
        if record.address:
            details.append(BusinessContactDetail(detail_type="address", value=record.address, page_url=record.page_url, source_type="JSON-LD"))
        if record.location:
            details.append(BusinessContactDetail(detail_type="location", value=record.location, page_url=record.page_url, source_type="JSON-LD"))
    return _deduplicate_contacts(details)


def _editorial_signals(pages: list[CrawledPage]) -> list[AuthorEditorialSignal]:
    signals: list[AuthorEditorialSignal] = []
    for page in pages:
        objects = [item for value in page.json_ld for item in _json_objects(value)]
        types = {schema_type for item in objects for schema_type in _schema_types(item)}
        is_editorial = bool(EDITORIAL_PATH_PATTERN.search(urlsplit(page.url).path)) or bool(types & ARTICLE_TYPES)
        authors: list[str] = []
        roles: list[str] = []
        for item in objects:
            if set(_schema_types(item)) & ARTICLE_TYPES:
                author_names, author_roles = _authors_from_json(item.get("author"))
                authors.extend(author_names)
                roles.extend(author_roles)
        authors.extend(BYLINE_PATTERN.findall(page.text_content))
        authors = _ordered_unique(authors)
        roles = _ordered_unique(roles)
        text_lower = page.text_content.lower()
        has_bio = "about the author" in text_lower or any(
            re.search(rf"\b{re.escape(name)}\b\s+(?:is|has|serves|leads)\b", page.text_content, re.I)
            for name in authors
        )
        publication_dates = [
            signal.value
            for signal in page.freshness_signals
            if signal.source_type != "copyright notice"
            and any(word in signal.source_type.lower() for word in ("date", "time", "published", "modified", "updated"))
        ]
        signals.append(
            AuthorEditorialSignal(
                page_url=page.url,
                is_editorial=is_editorial,
                visible_word_count=_word_count(page.text_content),
                author_names=authors,
                author_links=page.author_links,
                has_author_bio=has_bio,
                roles_or_credentials=roles,
                publication_dates=_ordered_unique(publication_dates),
                has_article_schema=bool(types & ARTICLE_TYPES),
                has_person_schema=PERSON_TYPE in types,
            )
        )
    return signals


def _credibility_signals(pages: list[CrawledPage]) -> list[ExternalCredibilitySignal]:
    signals: list[ExternalCredibilitySignal] = []
    for page in pages:
        content_links = sorted({link for block in page.content_blocks for link in block.links if not is_same_domain(link, page.url)})
        source_labels = [match.group(0) for match in SOURCE_PATTERN.finditer(page.text_content)]
        awards = [match.group(0) for match in AWARD_PATTERN.finditer(page.text_content)]
        customer_logos = [
            alt_text
            for alt_text in page.image_alt_text
            if "logo" in alt_text.lower() or "trusted by" in alt_text.lower()
        ]
        if "trusted by" in page.text_content.lower():
            customer_logos.append("Visible 'trusted by' wording")
        testimonials = [match.group(0) for match in TESTIMONIAL_PATTERN.finditer(page.text_content)]
        case_studies = [match.group(0) for match in CASE_STUDY_PATTERN.finditer(page.text_content)]
        signals.append(
            ExternalCredibilitySignal(
                page_url=page.url,
                outbound_citation_urls=content_links,
                named_source_labels=_ordered_unique(source_labels),
                certifications_or_awards=_ordered_unique(awards),
                customer_logo_signals=_ordered_unique(customer_logos),
                testimonial_signals=_ordered_unique(testimonials),
                case_study_signals=_ordered_unique(case_studies),
            )
        )
    return signals


def _trust_policy_pages(pages: list[CrawledPage], warnings: list[CrawlWarning]) -> list[TrustPolicySignal]:
    all_internal_links = {link for page in pages for link in page.internal_links}
    crawled_urls = {page.url for page in pages}
    unavailable_urls = {warning.url for warning in warnings if warning.url and warning.code == "http_status_skipped"}
    candidates: dict[tuple[str, str], TrustPolicySignal] = {}
    for page in pages:
        for policy_type in _policy_roles(_page_label(page)):
            candidates[(policy_type, page.url)] = TrustPolicySignal(
                policy_type=policy_type,
                url=page.url,
                internally_linked=page.url in all_internal_links,
                available=True,
            )
        for link in page.internal_links:
            for policy_type in _policy_roles(link):
                if link in crawled_urls:
                    continue
                candidates[(policy_type, link)] = TrustPolicySignal(
                    policy_type=policy_type,
                    url=link,
                    internally_linked=True,
                    available=False if link in unavailable_urls else None,
                )
    return sorted(candidates.values(), key=lambda item: (item.policy_type, item.url))


def _social_profiles(
    pages: list[CrawledPage],
    organization_data: list[OrganizationStructuredData],
    website_entities: list[OrganizationStructuredData],
) -> tuple[list[SocialProfileSignal], list[SocialProfileSignal]]:
    profiles: list[SocialProfileSignal] = []
    malformed: list[SocialProfileSignal] = []
    publisher_names = _publisher_names(pages, organization_data, website_entities)
    same_as_urls = {
        _social_identity(url)
        for record in organization_data
        for url in record.same_as
        if _is_http_url(url)
    }
    for page in pages:
        link_signals = _page_external_link_signals(page)
        for url, links in link_signals.items():
            network = _social_network(url)
            if not network:
                continue
            relevance = _social_relevance_signals(
                network,
                url,
                links,
                publisher_names,
                _social_identity(url) in same_as_urls,
            )
            if relevance:
                profiles.append(
                    SocialProfileSignal(
                        network=network,
                        url=url,
                        page_url=page.url,
                        source_type="visible social link",
                        relevance_signals=relevance,
                    )
                )
    for record in organization_data:
        for url in record.same_as:
            network = _social_network(url)
            relevance = _social_relevance_signals(
                network,
                url,
                [],
                publisher_names,
                True,
            )
            if network and relevance:
                profiles.append(
                    SocialProfileSignal(
                        network=network,
                        url=url,
                        page_url=record.page_url,
                        source_type="JSON-LD sameAs",
                        relevance_signals=relevance,
                    )
                )
            elif not _is_http_url(url):
                malformed.append(
                    SocialProfileSignal(
                        network="Unknown",
                        url=url,
                        page_url=record.page_url,
                        source_type="JSON-LD sameAs",
                    )
                )
    return _deduplicate_profiles(profiles), malformed


def _publisher_names(
    pages: list[CrawledPage],
    organization_data: list[OrganizationStructuredData],
    website_entities: list[OrganizationStructuredData],
) -> list[str]:
    """Return only explicit names suitable for conservative entity matching."""

    names = [
        value
        for record in [*organization_data, *website_entities]
        for value in (record.name, record.legal_name)
        if value
    ]
    if not names:
        names.extend(
            page.open_graph["og:site_name"]
            for page in pages
            if page.open_graph.get("og:site_name")
        )
    return _ordered_unique(names)


def _page_external_link_signals(
    page: CrawledPage,
) -> dict[str, list[ExternalLinkSignal]]:
    """Use rich parser data where available while retaining safe fixture compatibility."""

    signals_by_url: dict[str, list[ExternalLinkSignal]] = defaultdict(list)
    for signal in page.external_link_signals:
        signals_by_url[signal.url].append(signal)
    for url in page.external_links:
        if url not in signals_by_url:
            signals_by_url[url].append(ExternalLinkSignal(url=url))
    return signals_by_url


def _social_relevance_signals(
    network: str | None,
    url: str,
    link_signals: list[ExternalLinkSignal],
    publisher_names: list[str],
    is_structured_relationship: bool,
) -> list[str]:
    """Require a published relationship before treating a URL as an entity candidate."""

    if network is None:
        return []
    if network in {"Wikipedia", "Wikidata"}:
        return _knowledge_graph_relevance(url, link_signals, publisher_names)

    signals: list[str] = []
    if is_structured_relationship:
        signals.append("listed in organization JSON-LD sameAs")
    slug = _profile_slug(network, url)
    if slug and any(_approximately_matches(slug, name) for name in publisher_names):
        signals.append("profile URL slug matches an organization name")
    for link in link_signals:
        link_label = " ".join(item for item in (link.anchor_text, link.aria_label or "") if item)
        if link_label and any(_contains_entity_name(link_label, name) for name in publisher_names):
            signals.append("visible link label references the organization")
        if link.location in {"header", "footer"} and link.in_social_area:
            signals.append("link appears in a header or footer social-links area")
        rel_values = {value.lower() for value in link.rel_values}
        if rel_values & {"me", "publisher", "organization"}:
            signals.append("link rel identifies an entity relationship")
        aria_label = (link.aria_label or "").lower()
        if "official" in aria_label or "organization" in aria_label:
            signals.append("ARIA label identifies an organization profile")
    return _ordered_unique(signals)


def _knowledge_graph_relevance(
    url: str,
    link_signals: list[ExternalLinkSignal],
    publisher_names: list[str],
) -> list[str]:
    """Accept Wikipedia/Wikidata only with a conservative published-name match."""

    if not publisher_names:
        return []
    labels = [_knowledge_graph_label(url)]
    labels.extend(
        " ".join(item for item in (link.anchor_text, link.aria_label or "") if item)
        for link in link_signals
    )
    for label in labels:
        if label and any(_approximately_matches(label, name) for name in publisher_names):
            return ["knowledge-graph link label matches an organization name"]
    return []


def _knowledge_graph_label(url: str) -> str:
    parts = [segment for segment in urlsplit(url).path.split("/") if segment]
    if len(parts) == 2 and parts[0].lower() == "wiki":
        label = parts[1].replace("_", " ")
        return "" if re.fullmatch(r"Q\d+", label, re.I) else label
    return ""


def _profile_slug(network: str, url: str) -> str:
    parts = [segment for segment in urlsplit(url).path.split("/") if segment]
    if network == "LinkedIn" and len(parts) == 2:
        return parts[1]
    if network == "GitHub" and len(parts) == 1:
        return parts[0]
    if network == "X/Twitter" and len(parts) == 1:
        return parts[0]
    if network in {"Facebook", "Instagram"} and len(parts) == 1:
        return parts[0]
    if network == "YouTube" and parts and parts[0].startswith("@"):
        return parts[0][1:]
    if network == "Crunchbase" and len(parts) == 2:
        return parts[1]
    return ""


def _approximately_matches(candidate: str, entity_name: str) -> bool:
    candidate_tokens = set(_normalize_identity(candidate).split())
    entity_tokens = set(_normalize_identity(entity_name).split())
    if not candidate_tokens or not entity_tokens:
        return False
    if candidate_tokens == entity_tokens:
        return True
    return (
        len(entity_tokens) >= 2 and entity_tokens.issubset(candidate_tokens)
    ) or (
        len(candidate_tokens) >= 2 and candidate_tokens.issubset(entity_tokens)
    )


def _contains_entity_name(label: str, entity_name: str) -> bool:
    label_tokens = set(_normalize_identity(label).split())
    entity_tokens = set(_normalize_identity(entity_name).split())
    return bool(label_tokens and entity_tokens and entity_tokens.issubset(label_tokens))


def _finding(
    *,
    title: str,
    severity: Severity,
    confidence: Confidence,
    affected_url: str,
    evidence: list[Evidence],
    why_it_matters: str,
    recommendation: str,
    impact: int,
    effort: int,
    copy_paste_fix: str | None = None,
) -> DiscoverabilityFinding:
    """Create a Phase 4 finding using the existing shared Pydantic contract."""

    return DiscoverabilityFinding(
        id=f"entity-{uuid4().hex}",
        category=AuditCategory.ENTITY_TRUST,
        title=title,
        severity=severity,
        confidence=confidence,
        affected_url=affected_url,
        evidence=evidence,
        why_it_matters=why_it_matters,
        recommendation=recommendation,
        copy_paste_fix=copy_paste_fix,
        impact=impact,
        effort=effort,
    )


def _structured_conflict_finding(
    field_name: str,
    pair: tuple[EntityIdentitySignal, EntityIdentitySignal],
) -> DiscoverabilityFinding:
    return _finding(
        title=f"Organization structured data contains conflicting {field_name}",
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        affected_url=pair[0].page_url,
        evidence=_conflict_evidence(pair) if field_name == "names" else _url_conflict_evidence(pair),
        why_it_matters=(
            "Conflicting organization structured data can make it difficult to connect the website to one "
            "clear organization entity."
        ),
        recommendation="Use consistent organization details across the relevant JSON-LD objects.",
        impact=3,
        effort=1,
    )


def _person_field_findings(
    records: list[OrganizationStructuredData],
) -> list[DiscoverabilityFinding]:
    """Flag only useful missing fields on direct Person profile entities."""

    findings: list[DiscoverabilityFinding] = []
    for record in records:
        if not record.name:
            findings.append(
                _finding(
                    title="Person structured data is missing a name",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_url=record.page_url,
                    evidence=[
                        Evidence(
                            page_url=record.page_url,
                            exact_text="Person JSON-LD has no name property.",
                            source_type="JSON-LD",
                        )
                    ],
                    why_it_matters=(
                        "A Person entity without a name cannot clearly identify the author, founder, "
                        "or profile it is intended to describe."
                    ),
                    recommendation="Add the accurate person's name when this JSON-LD represents a profile.",
                    impact=2,
                    effort=1,
                )
            )
        elif record.source_property in {None, "@graph"} and not record.url and not record.same_as:
            findings.append(
                _finding(
                    title="Person structured data is missing a profile URL",
                    severity=Severity.LOW,
                    confidence=Confidence.MEDIUM,
                    affected_url=record.page_url,
                    evidence=[
                        Evidence(
                            page_url=record.page_url,
                            exact_text=f"Person JSON-LD name: {record.name}; no url or sameAs profile was detected.",
                            source_type="JSON-LD",
                        )
                    ],
                    why_it_matters=(
                        "For a published person profile, a URL can provide useful context that distinguishes "
                        "the person from people with similar names."
                    ),
                    recommendation=(
                        "Add an accurate public profile URL only when this Person entity represents a "
                        "maintained profile."
                    ),
                    impact=1,
                    effort=1,
                )
            )
    return findings


def _website_field_findings(
    records: list[OrganizationStructuredData],
) -> list[DiscoverabilityFinding]:
    findings: list[DiscoverabilityFinding] = []
    for record in records:
        if not record.name:
            findings.append(
                _finding(
                    title="WebSite structured data is missing a name",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_url=record.page_url,
                    evidence=[
                        Evidence(
                            page_url=record.page_url,
                            exact_text="WebSite JSON-LD has no name property.",
                            source_type="JSON-LD",
                        )
                    ],
                    why_it_matters="A WebSite name helps identify the website described by the structured data.",
                    recommendation="Add the public website name to the JSON-LD name property.",
                    impact=1,
                    effort=1,
                )
            )
        if not record.url:
            findings.append(
                _finding(
                    title="WebSite structured data is missing a URL",
                    severity=Severity.LOW,
                    confidence=Confidence.HIGH,
                    affected_url=record.page_url,
                    evidence=[
                        Evidence(
                            page_url=record.page_url,
                            exact_text="WebSite JSON-LD has no url property.",
                            source_type="JSON-LD",
                        )
                    ],
                    why_it_matters="A WebSite URL anchors the structured-data entity to its public website.",
                    recommendation="Add the canonical website URL to the JSON-LD url property.",
                    impact=1,
                    effort=1,
                )
            )
    return findings


def _json_entity_objects(
    value: Any,
    source_property: str | None = None,
) -> list[tuple[dict[str, Any], str | None]]:
    """Return JSON objects with their immediate relationship to a parent object."""

    objects: list[tuple[dict[str, Any], str | None]] = []
    if isinstance(value, dict):
        objects.append((value, source_property))
        for key, nested_value in value.items():
            objects.extend(_json_entity_objects(nested_value, str(key)))
    elif isinstance(value, list):
        for nested_value in value:
            objects.extend(_json_entity_objects(nested_value, source_property))
    return objects


def _json_objects(value: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(value, dict):
        objects.append(value)
        for nested_value in value.values():
            objects.extend(_json_objects(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            objects.extend(_json_objects(nested_value))
    return objects


def _entity_type(schema_types: list[str]) -> str | None:
    types = set(schema_types)
    if types & ORGANIZATION_TYPES:
        return "organization"
    if types & WEBSITE_TYPES:
        return "website"
    if types & PERSON_TYPES:
        return "person"
    if types & ARTICLE_TYPES:
        return "article"
    return None


def _entity_identity_key(record: OrganizationStructuredData) -> tuple[str, str, str]:
    name = _normalize_identity(record.name or record.legal_name or "")
    url = _normalized_entity_url(record.url)
    return record.entity_type, name, url


def _normalized_entity_url(value: str | None) -> str:
    if not value:
        return ""
    return normalize_url(value) or value.strip().lower().rstrip("/")


def _merge_entity_record(
    target: OrganizationStructuredData,
    source: OrganizationStructuredData,
) -> None:
    """Combine duplicate JSON-LD objects so absent fields do not create duplicate issues."""

    target.schema_types = _ordered_unique([*target.schema_types, *source.schema_types])
    target.same_as = _ordered_unique([*target.same_as, *source.same_as])
    for field_name in (
        "name",
        "legal_name",
        "url",
        "logo",
        "description",
        "email",
        "telephone",
        "address",
        "location",
        "founder",
        "founding_date",
    ):
        if getattr(target, field_name) is None and getattr(source, field_name) is not None:
            setattr(target, field_name, getattr(source, field_name))


def _schema_types(value: dict[str, Any]) -> list[str]:
    schema_type = value.get("@type")
    values = schema_type if isinstance(schema_type, list) else [schema_type]
    return [str(item).strip().lower() for item in values if isinstance(item, (str, int, float)) and str(item).strip()]


def _string_value(value: Any) -> str | None:
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text or None
    return None


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return _ordered_unique(str(item).strip() for item in values if isinstance(item, (str, int, float)) and str(item).strip())


def _url_or_string(value: Any) -> str | None:
    if isinstance(value, dict):
        return _string_value(value.get("url")) or _string_value(value.get("contentUrl"))
    return _string_value(value)


def _address_value(value: Any) -> str | None:
    if isinstance(value, dict):
        nested_address = _address_value(value.get("address")) if value.get("address") else None
        if nested_address:
            return nested_address
        keys = ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry")
        text = ", ".join(str(value[key]).strip() for key in keys if _string_value(value.get(key)))
        return text or _string_value(value.get("name"))
    return _string_value(value)


def _person_or_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return _string_value(value.get("name"))
    return _string_value(value)


def _company_roles(text: str) -> set[str]:
    normalized = text.lower()
    return {
        page_type
        for page_type, keywords in COMPANY_PAGE_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    }


def _policy_roles(text: str) -> set[str]:
    normalized = text.lower()
    roles: set[str] = set()
    for policy_type, keywords in POLICY_KEYWORDS.items():
        if policy_type == "Terms of Service":
            if any(keyword in normalized for keyword in keywords):
                roles.add(policy_type)
        elif any(keyword in normalized for keyword in keywords):
            roles.add(policy_type)
    return roles


def _page_label(page: CrawledPage) -> str:
    h1 = " ".join(heading.text for heading in page.headings if heading.level == 1)
    return " ".join(item for item in (page.url, page.title or "", h1) if item)


def _homepage_url(site_url: str, pages: list[CrawledPage]) -> str:
    normalized_site = normalize_url(site_url) or site_url
    for page in pages:
        if normalize_url(page.url) == normalized_site:
            return page.url
    return pages[0].url if pages else normalized_site


def _title_identity(title: str | None) -> str | None:
    if not title:
        return None
    candidate = re.split(r"\s+[|–—-]\s+", title, maxsplit=1)[0].strip()
    return candidate if 1 <= _word_count(candidate) <= 6 and not _is_generic_entity_label(candidate) else None


def _h1_identity(page: CrawledPage) -> str | None:
    h1 = next((heading.text for heading in page.headings if heading.level == 1), None)
    if not h1:
        return None
    candidate = re.sub(r"^(?:about|meet|contact)\s+", "", h1, flags=re.I).strip()
    return candidate if 1 <= _word_count(candidate) <= 5 and not _is_generic_entity_label(candidate) else None


def _footer_identity(footer_text: str) -> str | None:
    if not footer_text:
        return None
    match = COPYRIGHT_PATTERN.search(footer_text)
    if not match:
        return None
    candidate = re.split(r"[|•]", match.group(1), maxsplit=1)[0].strip(" .")
    return candidate if 1 <= _word_count(candidate) <= 6 else None


def _is_generic_entity_label(value: str) -> bool:
    return _normalize_identity(value) in {"about us", "contact us", "welcome", "home", "our team"}


def _normalize_identity(value: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower().replace("&", " and "))
    return " ".join(token for token in tokens if token not in LEGAL_NAME_TOKENS and token != "the")


def _equivalent_identity(first: str, second: str) -> bool:
    first_tokens = set(_normalize_identity(first).split())
    second_tokens = set(_normalize_identity(second).split())
    if not first_tokens or not second_tokens:
        return False
    return first_tokens == second_tokens or first_tokens.issubset(second_tokens) or second_tokens.issubset(first_tokens)


def _matches_known_organization(
    value: str,
    records: list[OrganizationStructuredData],
    focus_urls: set[str],
) -> bool:
    """Require visible labels to overlap a known organization before comparing them."""

    return any(
        record.page_url in focus_urls
        and (record.name or record.legal_name)
        and _equivalent_identity(value, record.name or record.legal_name or "")
        for record in records
    )


def _first_conflicting_pair(
    signals: list[EntityIdentitySignal],
) -> tuple[EntityIdentitySignal, EntityIdentitySignal] | None:
    compatible_signals = [signal for signal in signals if signal.entity_type == "organization"]
    for index, first in enumerate(compatible_signals):
        for second in compatible_signals[index + 1 :]:
            if not _comparable_entity_sources(first, second):
                continue
            if not _equivalent_identity(first.value, second.value):
                return first, second
    return None


def _comparable_entity_sources(
    first: EntityIdentitySignal,
    second: EntityIdentitySignal,
) -> bool:
    """Compare only explicit organization-identity sources, never page-topic labels."""

    first_is_json_ld = "JSON-LD" in first.source_type
    second_is_json_ld = "JSON-LD" in second.source_type
    if first_is_json_ld and second_is_json_ld:
        return True
    if not (first_is_json_ld or second_is_json_ld):
        return False
    other = second if first_is_json_ld else first
    return other.source_type in {
        "Organization name from OpenGraph",
        "Organization name from footer copyright",
    }


def _first_conflicting_url_pair(
    records: list[OrganizationStructuredData],
) -> tuple[EntityIdentitySignal, EntityIdentitySignal] | None:
    urls = [record for record in records if record.url]
    for index, first in enumerate(urls):
        for second in urls[index + 1 :]:
            if _url_entity_key(first.url or "") != _url_entity_key(second.url or ""):
                return (
                    EntityIdentitySignal(
                        page_url=first.page_url,
                        entity_type="organization",
                        source_type="Organization URL from JSON-LD",
                        value=first.url or "",
                    ),
                    EntityIdentitySignal(
                        page_url=second.page_url,
                        entity_type="organization",
                        source_type="Organization URL from JSON-LD",
                        value=second.url or "",
                    ),
                )
    return None


def _url_entity_key(value: str) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return value.lower().strip()
    parts = urlsplit(normalized)
    return parts.hostname.lower().removeprefix("www.") if parts.hostname else normalized


def _conflict_evidence(pair: tuple[EntityIdentitySignal, EntityIdentitySignal]) -> list[Evidence]:
    return [
        Evidence(
            page_url=pair[0].page_url,
            exact_text=f"Source A:\n{pair[0].source_type}: {pair[0].value}",
            source_type="entity identity signal",
        ),
        Evidence(
            page_url=pair[1].page_url,
            exact_text=f"Source B:\n{pair[1].source_type}: {pair[1].value}",
            source_type="entity identity signal",
        ),
    ]


def _url_conflict_evidence(pair: tuple[EntityIdentitySignal, EntityIdentitySignal]) -> list[Evidence]:
    return [
        Evidence(
            page_url=pair[0].page_url,
            exact_text=f"Source A: {pair[0].value}",
            source_type="JSON-LD URL",
        ),
        Evidence(
            page_url=pair[1].page_url,
            exact_text=f"Source B: {pair[1].value}",
            source_type="JSON-LD URL",
        ),
    ]


def _deduplicate_signals(signals: list[EntityIdentitySignal]) -> list[EntityIdentitySignal]:
    result: list[EntityIdentitySignal] = []
    seen: set[tuple[str, str, str]] = set()
    for signal in signals:
        key = (signal.page_url, signal.source_type, signal.value)
        if key not in seen:
            seen.add(key)
            result.append(signal)
    return result


def _deduplicate_contacts(details: list[BusinessContactDetail]) -> list[BusinessContactDetail]:
    result: list[BusinessContactDetail] = []
    seen: set[tuple[str, str, str]] = set()
    for detail in details:
        key = (
            detail.detail_type,
            _normalized_contact_value(detail.value, detail.detail_type),
            detail.page_url,
        )
        if key not in seen:
            seen.add(key)
            result.append(detail)
    return result


def _authors_from_json(value: Any) -> tuple[list[str], list[str]]:
    values = value if isinstance(value, list) else [value]
    names: list[str] = []
    roles: list[str] = []
    for item in values:
        if isinstance(item, dict):
            name = _string_value(item.get("name"))
            role = _string_value(item.get("jobTitle"))
            if name:
                names.append(name)
            if role:
                roles.append(role)
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names, roles


def _is_commercial_context(pages: list[CrawledPage]) -> bool:
    return any(
        re.search(r"\b(?:pricing|price|buy|purchase|subscribe|cart|checkout)\b", _page_label(page), re.I)
        for page in pages
    )


def _social_network(url: str) -> str | None:
    try:
        hostname = urlsplit(url).hostname
    except ValueError:
        return None
    if not hostname:
        return None
    hostname = hostname.lower().removeprefix("www.")
    for domain, network in SOCIAL_NETWORKS.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return network if _is_profile_path(network, urlsplit(url).path) else None
    return None


def _is_profile_path(network: str, path: str) -> bool:
    """Reject content, share, embed, and repository URLs from social profile checks."""

    parts = [segment.lower() for segment in path.split("/") if segment]
    if network == "YouTube":
        return bool(parts) and (
            parts[0].startswith("@")
            or (len(parts) == 2 and parts[0] in {"channel", "c", "user"})
        )
    if network == "GitHub":
        return len(parts) == 1 and parts[0] not in {"about", "contact", "features", "login", "topics"}
    if network == "LinkedIn":
        return len(parts) == 2 and parts[0] in {"company", "in", "school", "showcase"}
    if network == "X/Twitter":
        return len(parts) == 1 and parts[0] not in {"home", "search", "intent", "share", "i", "settings"}
    if network == "Facebook":
        return len(parts) == 1 and parts[0] not in {"share", "sharer", "plugins", "watch", "reel", "photo", "posts"}
    if network == "Instagram":
        return len(parts) == 1 and parts[0] not in {"p", "reel", "reels", "tv", "stories", "explore"}
    if network == "Crunchbase":
        return len(parts) == 2 and parts[0] in {"organization", "person"}
    if network == "Wikidata":
        return len(parts) == 2 and parts[0] == "wiki" and parts[1].startswith("q")
    if network == "Wikipedia":
        return len(parts) == 2 and parts[0] == "wiki"
    return False


def _social_identity(url: str) -> str:
    normalized = normalize_url(url) or url.strip().lower()
    parts = urlsplit(normalized)
    network = _social_network(normalized) or (parts.hostname or "").lower()
    return f"{network.lower()}:{parts.path.rstrip('/').lower()}"


def _is_http_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and bool(parts.hostname)


def _deduplicate_profiles(profiles: list[SocialProfileSignal]) -> list[SocialProfileSignal]:
    result: list[SocialProfileSignal] = []
    seen: set[tuple[str, str, str]] = set()
    for profile in profiles:
        key = (profile.source_type, _social_identity(profile.url))
        if key not in seen:
            seen.add(key)
            result.append(profile)
    return result


def _redact_contact_value(value: str, detail_type: str) -> str:
    if detail_type == "email" and "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}***@{domain}"
    if detail_type == "telephone":
        digits = _normalized_contact_value(value, detail_type)
        return f"+{digits[:3]}...{digits[-4:]}" if len(digits) >= 7 else "***"
    if detail_type in {"address", "location"}:
        return "[public location differs]"
    return value


def _normalized_contact_value(value: str, detail_type: str) -> str:
    """Normalize public values only enough for conservative equality comparisons."""

    if detail_type == "email":
        return value.strip().lower()
    if detail_type == "telephone":
        digits = re.sub(r"\D", "", value)
        if digits.startswith("00"):
            digits = digits[2:]
        # Normalize the optional North American country code without guessing
        # the country code for any other number.
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        return digits
    if detail_type in {"address", "location"}:
        return " ".join(re.findall(r"[a-z0-9]+", value.lower()))
    return value.strip().lower()


def _word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def _ordered_unique(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result
