"""Meta-robots noindex analysis for crawled HTML pages."""

from __future__ import annotations

import re

from ..models import (
    CrawledPage,
    DiscoverabilityFinding,
    Evidence,
    MetaRobotsAnalysis,
    NoindexPage,
    Severity,
)


DIRECTIVE_SPLIT = re.compile(r"[\s,]+")


class MetaRobotsAnalyzer:
    """Detect page-level noindex directives without judging intentional use."""

    def analyze(self, pages: list[CrawledPage]) -> MetaRobotsAnalysis:
        """Return pages where a robots meta tag requests no indexing."""

        noindex_pages: list[NoindexPage] = []
        findings: list[DiscoverabilityFinding] = []
        for page in pages:
            noindex_directives = {
                name: content
                for name, content in page.robots_meta.items()
                if _contains_noindex(content)
            }
            if not noindex_directives:
                continue
            noindex_pages.append(NoindexPage(page_url=page.url, directives=noindex_directives))
            findings.append(self._noindex_finding(page, noindex_directives))

        return MetaRobotsAnalysis(
            checked_page_count=len(pages),
            noindex_pages=noindex_pages,
            findings=findings,
        )

    @staticmethod
    def _noindex_finding(
        page: CrawledPage,
        directives: dict[str, str],
    ) -> DiscoverabilityFinding:
        exact_tags = "; ".join(
            f'<meta name="{name}" content="{content}">' for name, content in directives.items()
        )
        return DiscoverabilityFinding(
            title="Page has a noindex meta directive",
            severity=Severity.HIGH,
            evidence=[Evidence(page_url=page.url, exact_text=exact_tags, source_type="HTML metadata")],
            affected_url=page.url,
            why_it_matters=(
                "A noindex directive asks search engines not to include this page in their index, which "
                "can make it harder to discover and cite."
            ),
            recommendation="Remove noindex from public pages that should be discoverable, or replace it with index, follow.",
            copy_paste_fix=None,
        )


def _contains_noindex(content: str) -> bool:
    directives = {value.lower() for value in DIRECTIVE_SPLIT.split(content) if value}
    return "noindex" in directives or "none" in directives
