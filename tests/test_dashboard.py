"""Offline tests for Phase 7 dashboard presentation helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import requests

from citeready.dashboard import (
    action_cards,
    category_card,
    dashboard_score_label,
    deserialize_report_state,
    findings_by_category,
    page_inventory,
    safe_error_message,
    serialize_report_state,
    validate_dashboard_url,
)
from citeready.models import (
    AuditCategory,
    CategoryScore,
    CitationReadinessAnalysis,
    CrawlResult,
    CrawledPage,
    DiscoverabilityFinding,
    Evidence,
    OverallScore,
    PriorityAction,
    Severity,
)


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
URL = "https://example.com/"


def finding(
    identifier: str,
    *,
    category: AuditCategory = AuditCategory.CITATION_READINESS,
    url: str = URL,
) -> DiscoverabilityFinding:
    return DiscoverabilityFinding(
        id=identifier,
        category=category,
        title=f"Finding {identifier}",
        severity=Severity.MEDIUM,
        affected_url=url,
        evidence=[Evidence(page_url=url, exact_text="Observed evidence.", source_type="test")],
        why_it_matters="This affects the clarity of the website.",
        recommendation="Improve the page summary.",
        copy_paste_fix="<meta name=\"description\" content=\"Clear summary\" />",
        impact=4,
        effort=1,
    )


def report(*, actions: list[PriorityAction] | None = None, findings: list[DiscoverabilityFinding] | None = None) -> CrawlResult:
    current_findings = findings or []
    citation = CitationReadinessAnalysis(pages=[], findings=current_findings)
    score = OverallScore(
        overall_points=75,
        overall_percentage=75,
        category_scores=[],
        highest_priority_actions=actions or [],
    )
    return CrawlResult(
        requested_url=URL,
        analyzed_url=URL,
        citation_readiness=citation,
        scoring=score,
        max_pages=12,
        started_at=NOW,
        completed_at=NOW,
    )


class DashboardHelperTests(unittest.TestCase):
    def test_score_label_mapping(self) -> None:
        self.assertEqual(dashboard_score_label(90), "Excellent")
        self.assertEqual(dashboard_score_label(75), "Good")
        self.assertEqual(dashboard_score_label(60), "Needs Improvement")
        self.assertEqual(dashboard_score_label(59.99), "Poor")

    def test_category_card_formatting(self) -> None:
        card = category_card(
            CategoryScore(
                category=AuditCategory.DISCOVERABILITY,
                maximum_points=25,
                earned_points=23,
                percentage=92,
            )
        )
        self.assertEqual(card.title, "AI Discoverability")
        self.assertEqual(card.status_label, "Excellent")
        self.assertEqual(card.earned_points, 23)

    def test_priority_actions_are_deduplicated_by_recommendation(self) -> None:
        first = finding("first", url="https://example.com/one")
        second = finding("second", url="https://example.com/two")
        actions = [
            PriorityAction(title="First", recommendation="Improve the page summary.", linked_finding_ids=["first"], impact=4, effort=1),
            PriorityAction(title="Second", recommendation="Improve the page summary.", linked_finding_ids=["second"], impact=4, effort=1),
        ]
        cards = action_cards(report(actions=actions, findings=[first, second]))

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].frequency, 2)

    def test_affected_page_aggregation_is_retained(self) -> None:
        first = finding("first", url="https://example.com/one")
        second = finding("second", url="https://example.com/two")
        action = PriorityAction(
            title="Improve summary",
            recommendation="Improve the page summary.",
            linked_finding_ids=["first", "second"],
            impact=4,
            effort=1,
        )
        card = action_cards(report(actions=[action], findings=[first, second]))[0]

        self.assertEqual(card.affected_urls, ("https://example.com/one", "https://example.com/two"))

    def test_action_cards_sort_by_impact_effort_then_affected_pages(self) -> None:
        first = finding("first", url="https://example.com/one")
        second = finding("second", url="https://example.com/two")
        high = PriorityAction(title="High", recommendation="High action", linked_finding_ids=["first"], impact=5, effort=4)
        low_effort = PriorityAction(title="Lower effort", recommendation="Low effort action", linked_finding_ids=["second"], impact=5, effort=1)
        cards = action_cards(report(actions=[high, low_effort], findings=[first, second]))

        self.assertEqual(cards[0].title, "Lower effort")

    def test_findings_are_grouped_by_category(self) -> None:
        citation = finding("citation")
        entity = finding("entity", category=AuditCategory.ENTITY_TRUST)
        groups = findings_by_category(report(findings=[citation, entity]))

        self.assertEqual(groups[AuditCategory.CITATION_READINESS], [citation])
        self.assertEqual(groups[AuditCategory.ENTITY_TRUST], [entity])
        self.assertEqual(groups[AuditCategory.DISCOVERABILITY], [])

    def test_page_inventory_contains_business_readable_columns(self) -> None:
        audited_report = report()
        page = CrawledPage(
            requested_url=URL,
            url=URL,
            status_code=200,
            title="Example page",
            text_content="One two three four",
            robots_meta={"robots": "index, follow"},
            fetched_at=NOW,
        )
        audited_report = audited_report.model_copy(update={"pages": [page]})
        inventory = page_inventory(audited_report)

        self.assertEqual(inventory[0]["URL"], URL)
        self.assertEqual(inventory[0]["Word count"], 4)
        self.assertEqual(inventory[0]["Indexability"], "Indexable")
        self.assertIn("Canonical", inventory[0])

    def test_safe_error_messages_hide_technical_details(self) -> None:
        self.assertIn("SSL certificate", safe_error_message(requests.exceptions.SSLError("private details")))
        self.assertNotIn("private details", safe_error_message(RuntimeError("private details")))

    def test_report_state_round_trip_is_serializable(self) -> None:
        original = report(findings=[finding("serialized")])
        restored = deserialize_report_state(serialize_report_state(original))

        self.assertEqual(restored.analyzed_url, original.analyzed_url)
        self.assertEqual(restored.citation_readiness.findings[0].id, "serialized")

    def test_url_validation_rejects_private_and_accepts_public_hosts(self) -> None:
        public_url, public_error = validate_dashboard_url("example.com")
        private_url, private_error = validate_dashboard_url("http://127.0.0.1")

        self.assertEqual(public_url, URL)
        self.assertIsNone(public_error)
        self.assertIsNone(private_url)
        self.assertIn("private network", private_error)


if __name__ == "__main__":
    unittest.main()
