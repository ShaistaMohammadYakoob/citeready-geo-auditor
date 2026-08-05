"""Canonical-tag analysis across the bounded crawled page set."""

from __future__ import annotations

from ..models import (
    CanonicalAnalysis,
    CanonicalPageResult,
    CanonicalState,
    CrawledPage,
    DiscoverabilityFinding,
    Evidence,
    Severity,
)
from ..url_utils import is_same_domain


class CanonicalAnalyzer:
    """Find missing and cross-domain canonical signals without scoring them."""

    def analyze(self, pages: list[CrawledPage], site_url: str) -> CanonicalAnalysis:
        """Return one canonical status per crawled HTML page."""

        page_results: list[CanonicalPageResult] = []
        missing_page_urls: list[str] = []
        external_page_urls: list[str] = []
        findings: list[DiscoverabilityFinding] = []

        for page in pages:
            state = self._state_for(page, site_url)
            page_results.append(
                CanonicalPageResult(
                    page_url=page.url,
                    canonical_url=page.canonical_url,
                    state=state,
                )
            )
            if state == CanonicalState.MISSING:
                missing_page_urls.append(page.url)
                findings.append(self._missing_finding(page))
            elif state == CanonicalState.EXTERNAL:
                external_page_urls.append(page.url)
                findings.append(self._external_finding(page))

        return CanonicalAnalysis(
            pages=page_results,
            missing_page_urls=missing_page_urls,
            external_canonical_page_urls=external_page_urls,
            findings=findings,
        )

    @staticmethod
    def _state_for(page: CrawledPage, site_url: str) -> CanonicalState:
        if not page.canonical_url:
            return CanonicalState.MISSING
        if not is_same_domain(page.canonical_url, site_url):
            return CanonicalState.EXTERNAL
        if page.canonical_url == page.url:
            return CanonicalState.SELF
        return CanonicalState.INTERNAL_OTHER

    @staticmethod
    def _missing_finding(page: CrawledPage) -> DiscoverabilityFinding:
        return DiscoverabilityFinding(
            title="Canonical URL is missing",
            severity=Severity.MEDIUM,
            evidence=[
                Evidence(
                    page_url=page.url,
                    exact_text="No <link rel=\"canonical\"> tag was extracted from this page.",
                    source_type="HTML metadata",
                )
            ],
            affected_url=page.url,
            why_it_matters=(
                "A canonical URL tells crawlers which version of a page should represent the content when "
                "similar URLs exist."
            ),
            recommended_fix="Add one absolute canonical link in the page <head> that points to the preferred URL.",
            copy_paste_fix=f'<link rel="canonical" href="{page.url}">',
        )

    @staticmethod
    def _external_finding(page: CrawledPage) -> DiscoverabilityFinding:
        canonical_url = page.canonical_url or ""
        return DiscoverabilityFinding(
            title="Canonical URL points outside the audited domain",
            severity=Severity.HIGH,
            evidence=[
                Evidence(
                    page_url=page.url,
                    exact_text=f'<link rel="canonical" href="{canonical_url}">',
                    source_type="HTML metadata",
                )
            ],
            affected_url=page.url,
            why_it_matters=(
                "An external canonical can tell crawlers to attribute this page's content to another website, "
                "reducing the chance that your domain is selected as the source."
            ),
            recommended_fix="Confirm the cross-domain canonical is intentional; otherwise replace it with this page's preferred URL.",
            copy_paste_fix=f'<link rel="canonical" href="{page.url}">',
        )
