"""Offline checks for the shared discoverability finding contract."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from citeready.analyzers.discoverability import DiscoverabilityEngine
from citeready.cli import _print_findings, main
from citeready.config import CrawlerSettings
from citeready.models import (
    AuditCategory,
    CrawlResult,
    CrawledPage,
    DiscoverabilityFinding,
    FindingStatus,
    ResourceFetch,
)


SITE_URL = "https://example.com/"


class DiscoverabilityFindingTests(unittest.TestCase):
    """All five analyzers should use one complete, evidence-backed model."""

    def setUp(self) -> None:
        now = datetime.now(timezone.utc)
        self.pages = [
            CrawledPage(
                requested_url=SITE_URL,
                url=SITE_URL,
                status_code=200,
                robots_meta={"robots": "noindex, follow"},
                fetched_at=now,
            )
        ]
        self.resources = {
            "https://example.com/robots.txt": ResourceFetch(
                requested_url="https://example.com/robots.txt",
                final_url="https://example.com/robots.txt",
                status_code=404,
            ),
            "https://example.com/sitemap.xml": ResourceFetch(
                requested_url="https://example.com/sitemap.xml",
                final_url="https://example.com/sitemap.xml",
                status_code=404,
            ),
            "https://example.com/llms.txt": ResourceFetch(
                requested_url="https://example.com/llms.txt",
                final_url="https://example.com/llms.txt",
                status_code=404,
            ),
        }

    def test_all_analyzers_return_complete_shared_findings(self) -> None:
        analysis = DiscoverabilityEngine().analyze(SITE_URL, self.pages, self.resources.__getitem__)

        analyzer_findings = [
            *analysis.robots_txt.findings,
            *analysis.sitemap.findings,
            *analysis.canonical.findings,
            *analysis.meta_robots.findings,
            *analysis.llms_txt.findings,
        ]
        self.assertEqual(len(analyzer_findings), 5)
        self.assertEqual(analysis.findings, analyzer_findings)

        for finding in analyzer_findings:
            self.assertIsInstance(finding, DiscoverabilityFinding)
            self.assertTrue(finding.id.startswith("disc-"))
            self.assertEqual(finding.category, AuditCategory.DISCOVERABILITY)
            self.assertEqual(finding.status, FindingStatus.DETECTED)
            self.assertTrue(finding.affected_url)
            self.assertTrue(finding.evidence)
            self.assertTrue(all(item.page_url and item.exact_text for item in finding.evidence))
            self.assertTrue(finding.why_it_matters)
            self.assertTrue(finding.recommendation)
            self.assertIsNone(finding.impact)
            self.assertIsNone(finding.effort)
            self.assertTrue(finding.copy_paste_fix is None or bool(finding.copy_paste_fix))

    def test_detailed_cli_output_uses_actual_finding_evidence(self) -> None:
        analysis = DiscoverabilityEngine().analyze(SITE_URL, self.pages, self.resources.__getitem__)
        now = datetime.now(timezone.utc)
        result = CrawlResult(
            requested_url=SITE_URL,
            analyzed_url=SITE_URL,
            pages=self.pages,
            discoverability=analysis,
            max_pages=12,
            started_at=now,
            completed_at=now,
        )
        output = io.StringIO()

        with redirect_stdout(output):
            _print_findings(result)

        text = output.getvalue()
        self.assertIn("[MEDIUM] Canonical URL is missing", text)
        self.assertIn('Evidence: No rel="canonical" element was found in the page head.', text)
        self.assertIn("Recommended action: Add a self-referencing canonical tag in the page head.", text)
        self.assertIn('<link rel="canonical" href="https://example.com/" />', text)

    def test_show_findings_flag_prints_detailed_output(self) -> None:
        analysis = DiscoverabilityEngine().analyze(SITE_URL, self.pages, self.resources.__getitem__)
        now = datetime.now(timezone.utc)
        result = CrawlResult(
            requested_url=SITE_URL,
            analyzed_url=SITE_URL,
            pages=self.pages,
            discoverability=analysis,
            max_pages=12,
            started_at=now,
            completed_at=now,
        )
        output = io.StringIO()

        with (
            patch("citeready.cli.load_crawler_settings", return_value=CrawlerSettings()),
            patch("citeready.cli.SiteCrawler") as crawler_type,
            patch("sys.argv", ["citeready", SITE_URL, "--show-findings"]),
            redirect_stdout(output),
        ):
            crawler_type.return_value.crawl.return_value = result
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("DISCOVERABILITY REPORT", output.getvalue())
        self.assertIn("Detailed findings", output.getvalue())


if __name__ == "__main__":
    unittest.main()
