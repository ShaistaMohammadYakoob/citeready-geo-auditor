"""Offline smoke coverage for sitemap status and completeness behavior."""

from __future__ import annotations

import unittest

from citeready.analyzers.sitemap import SitemapAnalyzer
from citeready.config import CrawlerSettings
from citeready.crawler import SiteCrawler
from citeready.models import ResourceFetch, SitemapAnalysisStatus


SITE_URL = "https://example.com/"


def resource(url: str, *, status: int, text: str | None = None, error: str | None = None) -> ResourceFetch:
    """Build a small fake resource response for an offline analyzer test."""

    return ResourceFetch(
        requested_url=url,
        final_url=url,
        status_code=status,
        text=text,
        error=error,
    )


class SitemapAnalyzerSmokeTests(unittest.TestCase):
    """Exercise the five sitemap outcomes without external HTTP requests."""

    def test_normal_sitemap_is_complete(self) -> None:
        sitemap_url = "https://example.com/sitemap.xml"
        result = SitemapAnalyzer().analyze(
            SITE_URL,
            {sitemap_url: resource(sitemap_url, status=200, text=_urlset("/", "/about"))}.__getitem__,
        )

        self.assertEqual(result.status, SitemapAnalysisStatus.COMPLETE)
        self.assertEqual(result.parsed_url_count, 2)
        self.assertTrue(result.url_count_is_complete)
        self.assertEqual(result.successfully_parsed_sitemap_files, [sitemap_url])
        self.assertEqual(result.skipped_sitemap_files, [])

    def test_sitemap_index_counts_urls_from_child_file(self) -> None:
        fallback_url = "https://example.com/sitemap.xml"
        index_url = "https://example.com/sitemap-index.xml"
        child_url = "https://example.com/products.xml"
        resources = {
            fallback_url: resource(fallback_url, status=404),
            index_url: resource(index_url, status=200, text=_sitemap_index(child_url)),
            child_url: resource(child_url, status=200, text=_urlset("/", "/pricing")),
        }

        result = SitemapAnalyzer().analyze(SITE_URL, resources.__getitem__, [index_url])

        self.assertEqual(result.status, SitemapAnalysisStatus.COMPLETE)
        self.assertEqual(result.parsed_url_count, 2)
        self.assertTrue(result.url_count_is_complete)
        self.assertEqual(result.successfully_parsed_sitemap_files, [index_url, child_url])

    def test_oversized_child_sitemap_is_partial_and_keeps_reason(self) -> None:
        fallback_url = "https://example.com/sitemap.xml"
        index_url = "https://example.com/sitemap-index.xml"
        large_child_url = "https://example.com/large-partition.xml"
        resources = {
            fallback_url: resource(fallback_url, status=404),
            index_url: resource(index_url, status=200, text=_sitemap_index(large_child_url)),
            large_child_url: resource(
                large_child_url,
                status=200,
                error="Response exceeds the 2,000,000-byte safety limit.",
            ),
        }

        result = SitemapAnalyzer().analyze(SITE_URL, resources.__getitem__, [index_url])

        self.assertEqual(result.status, SitemapAnalysisStatus.PARTIAL)
        self.assertFalse(result.url_count_is_complete)
        self.assertEqual(result.parsed_url_count, 0)
        self.assertEqual(len(result.skipped_sitemap_files), 1)
        self.assertEqual(result.skipped_sitemap_files[0].url, large_child_url)
        self.assertIn("2,000,000-byte safety limit", result.skipped_sitemap_files[0].reason)

    def test_invalid_sitemap_has_invalid_status(self) -> None:
        sitemap_url = "https://example.com/sitemap.xml"
        result = SitemapAnalyzer().analyze(
            SITE_URL,
            {sitemap_url: resource(sitemap_url, status=200, text="<urlset><url>")}.__getitem__,
        )

        self.assertEqual(result.status, SitemapAnalysisStatus.INVALID)
        self.assertFalse(result.url_count_is_complete)
        self.assertEqual(result.parsed_url_count, 0)

    def test_missing_sitemap_is_unavailable(self) -> None:
        sitemap_url = "https://example.com/sitemap.xml"
        result = SitemapAnalyzer().analyze(
            SITE_URL,
            {sitemap_url: resource(sitemap_url, status=404)}.__getitem__,
        )

        self.assertEqual(result.status, SitemapAnalysisStatus.UNAVAILABLE)
        self.assertFalse(result.url_count_is_complete)
        self.assertEqual(result.parsed_url_count, 0)

    def test_oversized_resource_warning_includes_url_and_reason(self) -> None:
        oversized_url = "https://example.com/large-partition.xml"
        crawler = SiteCrawler(CrawlerSettings())
        crawler.session = _OversizedSession(oversized_url)
        warnings = []

        fetched = crawler._fetch_text_resource(oversized_url, SITE_URL, warnings)

        self.assertIsNotNone(fetched.error)
        self.assertIn("2,000,000-byte safety limit", fetched.error or "")
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].url, oversized_url)
        self.assertIn("2,000,000-byte safety limit", warnings[0].message)


class _OversizedSession:
    """Minimal requests.Session replacement for the safety-limit smoke test."""

    def __init__(self, url: str) -> None:
        self.headers: dict[str, str] = {}
        self.response = _OversizedResponse(url)

    def get(self, url: str, **_: object) -> "_OversizedResponse":
        return self.response


class _OversizedResponse:
    """A response that declares a body larger than the configured safety limit."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": "application/xml", "Content-Length": "2000001"}
        self.history: list[object] = []

    def close(self) -> None:
        pass


def _urlset(*paths: str) -> str:
    entries = "".join(f"<url><loc>https://example.com{path}</loc></url>" for path in paths)
    return f"<urlset>{entries}</urlset>"


def _sitemap_index(child_url: str) -> str:
    return f"<sitemapindex><sitemap><loc>{child_url}</loc></sitemap></sitemapindex>"


if __name__ == "__main__":
    unittest.main()
