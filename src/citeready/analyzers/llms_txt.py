"""Availability analysis for the optional llms.txt convention."""

from __future__ import annotations

from urllib.parse import urljoin

from ..models import DiscoverabilityFinding, Evidence, LlmsTxtAnalysis, ResourceFetch, Severity
from .base import TextResourceFetcher, is_successful, resource_evidence


class LlmsTxtAnalyzer:
    """Check whether an accessible, non-empty llms.txt file is published."""

    def analyze(self, site_url: str, fetch: TextResourceFetcher) -> LlmsTxtAnalysis:
        """Return llms.txt availability; absence is reported as an optional enhancement."""

        llms_url = urljoin(site_url, "/llms.txt")
        resource = fetch(llms_url)
        found = is_successful(resource) and bool((resource.text or "").strip()) and not _looks_like_html(resource)
        if found:
            return LlmsTxtAnalysis(
                url=llms_url,
                found=True,
                status_code=resource.status_code,
                line_count=len((resource.text or "").splitlines()),
            )

        return LlmsTxtAnalysis(
            url=llms_url,
            found=False,
            status_code=resource.status_code,
            findings=[self._missing_finding(llms_url, resource)],
        )

    @staticmethod
    def _missing_finding(llms_url: str, resource: ResourceFetch) -> DiscoverabilityFinding:
        return DiscoverabilityFinding(
            title="llms.txt is missing or empty",
            severity=Severity.LOW,
            evidence=[resource_evidence(resource, "llms.txt")],
            affected_url=llms_url,
            why_it_matters=(
                "llms.txt is an emerging, optional convention for presenting a concise map of useful site "
                "content to language-model tools. It is not a guarantee of inclusion."
            ),
            recommendation="Consider publishing a short, accurate llms.txt file that links to your most useful public pages.",
            copy_paste_fix=None,
        )


def _looks_like_html(resource: ResourceFetch) -> bool:
    content_type = (resource.content_type or "").lower()
    text = (resource.text or "").lstrip().lower()
    return "text/html" in content_type or text.startswith("<!doctype html") or text.startswith("<html")
