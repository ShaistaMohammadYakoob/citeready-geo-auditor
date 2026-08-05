"""Phase 2 orchestrator for unscored discoverability analyzers."""

from __future__ import annotations

from ..models import CrawledPage, DiscoverabilityAnalysis
from .base import TextResourceFetcher
from .canonical import CanonicalAnalyzer
from .llms_txt import LlmsTxtAnalyzer
from .meta_robots import MetaRobotsAnalyzer
from .robots_txt import RobotsTxtAnalyzer
from .sitemap import SitemapAnalyzer


class DiscoverabilityEngine:
    """Run all discoverability analyzers against one completed crawl."""

    def __init__(self) -> None:
        self.robots_txt = RobotsTxtAnalyzer()
        self.sitemap = SitemapAnalyzer()
        self.canonical = CanonicalAnalyzer()
        self.meta_robots = MetaRobotsAnalyzer()
        self.llms_txt = LlmsTxtAnalyzer()

    def analyze(
        self,
        site_url: str,
        pages: list[CrawledPage],
        fetch: TextResourceFetcher,
    ) -> DiscoverabilityAnalysis:
        """Collect all findings; no score or prioritization is calculated here."""

        robots_result = self.robots_txt.analyze(site_url, fetch)
        sitemap_result = self.sitemap.analyze(site_url, fetch, robots_result.sitemap_urls)
        canonical_result = self.canonical.analyze(pages, site_url)
        meta_robots_result = self.meta_robots.analyze(pages)
        llms_result = self.llms_txt.analyze(site_url, fetch)
        findings = [
            *robots_result.findings,
            *sitemap_result.findings,
            *canonical_result.findings,
            *meta_robots_result.findings,
            *llms_result.findings,
        ]
        return DiscoverabilityAnalysis(
            robots_txt=robots_result,
            sitemap=sitemap_result,
            canonical=canonical_result,
            meta_robots=meta_robots_result,
            llms_txt=llms_result,
            findings=findings,
        )
