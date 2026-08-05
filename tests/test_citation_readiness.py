"""Offline coverage for deterministic Citation Readiness heuristics."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from citeready.analyzers.citation_readiness import CitationReadinessAnalyzer
from citeready.cli import main
from citeready.config import CrawlerSettings
from citeready.models import (
    CitationReadinessAnalysis,
    Confidence,
    ContentBlock,
    CrawlResult,
    CrawledPage,
    FreshnessSignal,
    Heading,
)
from citeready.parser import parse_html_page


PAGE_URL = "https://example.com/"


def heading(level: int, text: str) -> ContentBlock:
    return ContentBlock(kind="heading", text=text, heading_level=level)


def paragraph(text: str, links: list[str] | None = None) -> ContentBlock:
    return ContentBlock(kind="paragraph", text=text, links=links or [])


def words(count: int) -> str:
    return " ".join(f"word{index}" for index in range(count))


def page(
    *,
    title: str = "Acme Analytics Platform",
    headings: list[Heading] | None = None,
    blocks: list[ContentBlock] | None = None,
    text_content: str | None = None,
    json_ld: list[object] | None = None,
    freshness_signals: list[FreshnessSignal] | None = None,
) -> CrawledPage:
    page_headings = headings if headings is not None else [Heading(level=1, text=title)]
    page_blocks = (
        blocks
        if blocks is not None
        else [heading(1, title), paragraph("Acme Analytics Platform is a service for teams.")]
    )
    return CrawledPage(
        requested_url=PAGE_URL,
        url=PAGE_URL,
        status_code=200,
        title=title,
        headings=page_headings,
        content_blocks=page_blocks,
        text_content=text_content or " ".join(block.text for block in page_blocks),
        json_ld=json_ld or [],
        freshness_signals=freshness_signals or [],
        fetched_at=datetime.now(timezone.utc),
    )


class CitationReadinessAnalyzerTests(unittest.TestCase):
    """Test each Phase 3 heuristic with local, deterministic fixtures."""

    def setUp(self) -> None:
        self.analyzer = CitationReadinessAnalyzer()

    def _findings_for(self, crawled_page: CrawledPage):
        return self.analyzer.analyze([crawled_page]).findings

    def _titles_for(self, crawled_page: CrawledPage) -> list[str]:
        return [finding.title for finding in self._findings_for(crawled_page)]

    def test_long_paragraph_records_exact_word_count_and_200_character_excerpt(self) -> None:
        content = words(121)
        findings = self._findings_for(page(blocks=[heading(1, "Acme Analytics Platform"), paragraph(content)]))
        finding = next(item for item in findings if item.title.startswith("Paragraph is difficult"))

        self.assertEqual(finding.evidence[0].exact_text, content[:200])
        self.assertEqual(finding.evidence[0].context, "Paragraph word count: 121.")
        self.assertEqual(finding.confidence, Confidence.HIGH)

    def test_short_paragraph_is_not_flagged(self) -> None:
        self.assertNotIn("Paragraph is difficult to extract as a concise passage", self._titles_for(page()))

    def test_missing_h1_is_flagged(self) -> None:
        crawled_page = page(headings=[Heading(level=2, text="Analytics")], blocks=[heading(2, "Analytics")])
        self.assertIn("Page is missing an H1 heading", self._titles_for(crawled_page))

    def test_multiple_h1_is_flagged(self) -> None:
        crawled_page = page(
            headings=[Heading(level=1, text="Acme"), Heading(level=1, text="Analytics")],
            blocks=[heading(1, "Acme"), heading(1, "Analytics")],
        )
        self.assertIn("Page has multiple H1 headings", self._titles_for(crawled_page))

    def test_skipped_heading_level_is_flagged(self) -> None:
        crawled_page = page(
            headings=[Heading(level=1, text="Acme"), Heading(level=3, text="Details")],
            blocks=[heading(1, "Acme"), heading(3, "Details")],
        )
        self.assertIn("Heading hierarchy skips levels", self._titles_for(crawled_page))

    def test_generic_heading_is_flagged(self) -> None:
        crawled_page = page(
            headings=[Heading(level=1, text="Acme"), Heading(level=2, text="Learn More")],
            blocks=[heading(1, "Acme"), heading(2, "Learn More")],
        )
        self.assertIn("Page uses generic headings", self._titles_for(crawled_page))

    def test_page_analysis_returns_complete_heading_hierarchy(self) -> None:
        hierarchy = [Heading(level=1, text="Acme"), Heading(level=2, text="Details")]
        result = self.analyzer.analyze([page(headings=hierarchy, blocks=[heading(1, "Acme"), heading(2, "Details")])])
        self.assertEqual(result.pages[0].heading_hierarchy, hierarchy)

    def test_strong_direct_answer_is_explained(self) -> None:
        opening = (
            "Acme Analytics Platform is a reporting service for revenue teams that need clear pipeline "
            "insights, reliable forecasts, and shared performance dashboards. It provides practical views "
            "of sales activity so managers can identify changes, answer planning questions, and improve "
            "weekly decisions without assembling reports manually."
        )
        result = self.analyzer.analyze([page(blocks=[heading(1, "Acme Analytics Platform"), paragraph(opening)])])
        assessment = result.pages[0].direct_answer

        self.assertTrue(assessment.is_strong)
        self.assertIn("explanatory statement pattern", assessment.reason)
        self.assertNotIn("Opening does not clearly state what the page is about", [item.title for item in result.findings])

    def test_weak_direct_answer_records_its_reason_and_opening_evidence(self) -> None:
        opening = "Welcome to a place where teams explore possibilities and build tomorrow together. " * 4
        findings = self._findings_for(page(blocks=[heading(1, "Acme Analytics Platform"), paragraph(opening)]))
        finding = next(item for item in findings if item.title.startswith("Opening does not"))

        self.assertIn("does not repeat enough", finding.evidence[0].context or "")
        self.assertEqual(finding.evidence[0].exact_text, " ".join(opening.split()[:200]))

    def test_faq_schema_and_visible_faq_are_distinguished(self) -> None:
        result = self.analyzer.analyze(
            [
                page(
                    headings=[Heading(level=1, text="Acme"), Heading(level=2, text="Frequently Asked Questions")],
                    blocks=[heading(1, "Acme"), heading(2, "Frequently Asked Questions")],
                    json_ld=[{"@context": "https://schema.org", "@type": "FAQPage"}],
                )
            ]
        )
        faq = result.pages[0].faq

        self.assertTrue(faq.has_faq_schema)
        self.assertEqual(faq.visible_faq_headings, ["Frequently Asked Questions"])
        self.assertEqual(faq.unanswered_question_headings, [])

    def test_question_heading_without_answer_is_flagged(self) -> None:
        crawled_page = page(
            headings=[Heading(level=1, text="Acme"), Heading(level=2, text="How does pricing work?")],
            blocks=[heading(1, "Acme"), heading(2, "How does pricing work?")],
        )
        self.assertIn("Question headings do not have visible answers", self._titles_for(crawled_page))

    def test_long_page_without_lists_or_tables_is_flagged(self) -> None:
        content = words(501)
        crawled_page = page(
            blocks=[heading(1, "Acme Analytics Platform"), paragraph(content)],
            text_content=content,
        )
        self.assertIn("Long page has no lists or tables", self._titles_for(crawled_page))

    def test_simple_page_without_lists_or_tables_is_not_flagged(self) -> None:
        self.assertNotIn("Long page has no lists or tables", self._titles_for(page()))

    def test_unsupported_claims_are_confidence_based_and_never_called_false(self) -> None:
        content = "Our fastest platform improved results by 20% in 2024."
        finding = next(
            item
            for item in self._findings_for(page(blocks=[heading(1, "Acme"), paragraph(content)]))
            if item.title.startswith("Potentially unsupported claims")
        )

        self.assertEqual(finding.confidence, Confidence.MEDIUM)
        self.assertIn("does not state that any claim is false", finding.why_it_matters)
        self.assertIn("20%", finding.evidence[0].exact_text)
        self.assertIn("No nearby source", finding.evidence[0].context or "")

    def test_claim_with_nearby_url_is_not_flagged(self) -> None:
        crawled_page = page(
            blocks=[
                heading(1, "Acme"),
                paragraph("Our fastest platform improved results by 20%.", ["https://source.example/study"]),
            ]
        )
        self.assertNotIn("Potentially unsupported claims (confidence-based)", self._titles_for(crawled_page))

    def test_long_section_has_specific_split_and_heading_suggestion(self) -> None:
        content = words(450)
        finding = next(
            item
            for item in self._findings_for(
                page(
                    headings=[Heading(level=1, text="Acme"), Heading(level=2, text="Pricing")],
                    blocks=[heading(1, "Acme"), heading(2, "Pricing"), paragraph(content)],
                )
            )
            if item.title == "Section is too long to be easily chunked"
        )

        self.assertIn("Split the “Pricing” section after the paragraph beginning", finding.recommendation)
        self.assertIn("Insert an H3 such as “Pricing details”", finding.recommendation)

    def test_parser_extracts_all_freshness_signal_types_without_outdated_finding(self) -> None:
        parsed = parse_html_page(
            requested_url=PAGE_URL,
            final_url=PAGE_URL,
            status_code=200,
            content_type="text/html",
            html=(
                '<html><head><meta property="article:published_time" content="2024-01-02">'
                '<script type="application/ld+json">{"dateModified":"2025-02-03"}</script></head>'
                '<body><h1>Acme</h1><time datetime="2025-03-04">March 4, 2025</time>'
                '<footer>© 2025 Acme</footer></body></html>'
            ),
        )
        result = self.analyzer.analyze([parsed])
        values = {signal.value for signal in result.pages[0].freshness_signals}

        self.assertTrue({"2024-01-02", "2025-02-03", "2025-03-04", "2025"}.issubset(values))
        self.assertFalse(any("outdated" in finding.title.lower() for finding in result.findings))

    def test_citation_findings_have_required_shared_fields(self) -> None:
        findings = self._findings_for(
            page(
                headings=[],
                blocks=[paragraph(words(121))],
            )
        )
        self.assertTrue(findings)
        for finding in findings:
            self.assertTrue(finding.id.startswith("citation-"))
            self.assertEqual(finding.category.value, "Citation Readiness")
            self.assertIsNotNone(finding.confidence)
            self.assertTrue(finding.evidence)
            self.assertTrue(finding.affected_url)
            self.assertTrue(finding.why_it_matters)
            self.assertTrue(finding.recommendation)
            self.assertIsNotNone(finding.impact)
            self.assertIsNotNone(finding.effort)

    def test_show_citation_findings_flag_prints_structured_details(self) -> None:
        analysis = self.analyzer.analyze([page(headings=[], blocks=[paragraph(words(121))])])
        now = datetime.now(timezone.utc)
        result = CrawlResult(
            requested_url=PAGE_URL,
            analyzed_url=PAGE_URL,
            citation_readiness=analysis,
            max_pages=12,
            started_at=now,
            completed_at=now,
        )
        output = io.StringIO()

        with (
            patch("citeready.cli.load_crawler_settings", return_value=CrawlerSettings()),
            patch("citeready.cli.SiteCrawler") as crawler_type,
            patch("sys.argv", ["citeready", PAGE_URL, "--show-citation-findings"]),
            redirect_stdout(output),
        ):
            crawler_type.return_value.crawl.return_value = result
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("Citation Readiness findings", output.getvalue())
        self.assertIn("Confidence: High", output.getvalue())
        self.assertIn("Impact: ", output.getvalue())


if __name__ == "__main__":
    unittest.main()
