"""Offline coverage for the transparent, configurable Phase 6 scoring engine."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone

from citeready.cli import _print_score, _score_label
from citeready.models import (
    AuditCategory,
    Confidence,
    CrawlResult,
    DiscoverabilityFinding,
    Evidence,
    RuleScoreStatus,
    Severity,
)
from citeready.scoring import GeoScoringEngine
from citeready.scoring_rules import DEFAULT_SCORING_RULES, RuleEvaluation, ScoringRule


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
URL = "https://example.com/"


def result() -> CrawlResult:
    return CrawlResult(
        requested_url=URL,
        analyzed_url=URL,
        max_pages=12,
        started_at=NOW,
        completed_at=NOW,
    )


def finding(
    *,
    title: str = "Evidence-backed issue",
    category: AuditCategory = AuditCategory.DISCOVERABILITY,
    confidence: Confidence = Confidence.HIGH,
    severity: Severity = Severity.HIGH,
    evidence: bool = True,
    impact: int = 3,
    effort: int = 2,
    page_url: str = URL,
    identifier: str | None = None,
    recommendation: str = "Make the documented improvement.",
) -> DiscoverabilityFinding:
    return DiscoverabilityFinding(
        id=identifier or f"finding-{title.replace(' ', '-').lower()}",
        category=category,
        title=title,
        severity=severity,
        confidence=confidence,
        affected_url=page_url,
        evidence=[Evidence(page_url=page_url, exact_text="Observed response evidence.", source_type="test")]
        if evidence
        else [],
        why_it_matters="The issue affects retrieval.",
        recommendation=recommendation,
        impact=impact,
        effort=effort,
    )


def evaluation(
    quality: float,
    *,
    findings: tuple[DiscoverabilityFinding, ...] = (),
    keys: tuple[str, ...] = (),
    status: RuleScoreStatus | None = None,
) -> RuleEvaluation:
    return RuleEvaluation(
        quality=quality,
        status=status
        or (RuleScoreStatus.PASS if quality == 1 else RuleScoreStatus.FAIL if quality == 0 else RuleScoreStatus.PARTIAL),
        reason="Test rule outcome.",
        findings=findings,
        deduction_keys=keys,
    )


def rule(
    rule_id: str,
    points: float,
    outcome: RuleEvaluation,
    *,
    category: AuditCategory = AuditCategory.DISCOVERABILITY,
) -> ScoringRule:
    return ScoringRule(
        id=rule_id,
        category=category,
        title=rule_id.replace("_", " ").title(),
        maximum_points=points,
        evaluation_function=lambda _context: outcome,
        deduction_reason="Test deduction reason.",
        explanation="Test explanation.",
    )


class TransparentScoringTests(unittest.TestCase):
    def score(self, *rules: ScoringRule):
        return GeoScoringEngine(rules).score(result())

    def test_default_rule_allocations_total_one_hundred_points(self) -> None:
        self.assertEqual(sum(item.maximum_points for item in DEFAULT_SCORING_RULES), 100)

    def test_default_rules_have_four_twenty_five_point_categories(self) -> None:
        totals: dict[AuditCategory, float] = {}
        for item in DEFAULT_SCORING_RULES:
            totals[item.category] = totals.get(item.category, 0) + item.maximum_points
        self.assertEqual(set(totals), set(AuditCategory))
        self.assertEqual(set(totals.values()), {25})

    def test_every_default_rule_is_documented_and_configurable(self) -> None:
        for item in DEFAULT_SCORING_RULES:
            self.assertTrue(item.id)
            self.assertTrue(item.title)
            self.assertGreater(item.maximum_points, 0)
            self.assertTrue(item.deduction_reason)
            self.assertTrue(item.explanation)
            self.assertTrue(callable(item.evaluation_function))

    def test_perfect_score(self) -> None:
        score = self.score(rule("perfect", 25, evaluation(1)))
        self.assertEqual(score.overall_points, 25)
        self.assertEqual(score.overall_percentage, 100)

    def test_zero_score(self) -> None:
        score = self.score(rule("zero", 25, evaluation(0)))
        self.assertEqual(score.overall_points, 0)
        self.assertEqual(score.overall_percentage, 0)

    def test_category_calculation(self) -> None:
        score = self.score(rule("first", 10, evaluation(1)), rule("second", 10, evaluation(0.5)))
        category = score.category_scores[0]
        self.assertEqual(category.maximum_points, 20)
        self.assertEqual(category.earned_points, 15)
        self.assertEqual(category.percentage, 75)

    def test_overall_calculation(self) -> None:
        score = self.score(
            rule("discoverability", 20, evaluation(0.5)),
            rule("citation", 20, evaluation(1), category=AuditCategory.CITATION_READINESS),
        )
        self.assertEqual(score.overall_points, 30)
        self.assertEqual(score.overall_percentage, 75)

    def test_point_rounding_is_consistent(self) -> None:
        score = self.score(rule("thirds", 25, evaluation(1 / 3)))
        self.assertEqual(score.category_scores[0].earned_points, 8.33)
        self.assertEqual(score.overall_percentage, 33.32)

    def test_rule_breakdown_retains_transparent_title_and_reason(self) -> None:
        score = self.score(rule("visible_rule", 5, evaluation(0.5)))
        rule_score = score.category_scores[0].rule_breakdown[0]
        self.assertEqual(rule_score.title, "Visible Rule")
        self.assertEqual(rule_score.reason, "Test rule outcome.")

    def test_duplicate_deduction_key_is_not_deducted_twice(self) -> None:
        item = finding(severity=Severity.CRITICAL)
        score = self.score(
            rule("one", 10, evaluation(0, findings=(item,), keys=("same-issue",))),
            rule("two", 10, evaluation(0, findings=(item,), keys=("same-issue",))),
        )
        first, second = score.category_scores[0].rule_breakdown
        self.assertEqual(first.earned_points, 0)
        self.assertEqual(second.earned_points, 10)
        self.assertIn("already deducted", second.reason)

    def test_distinct_deduction_keys_can_be_scored_independently(self) -> None:
        item = finding(severity=Severity.CRITICAL)
        score = self.score(
            rule("one", 10, evaluation(0, findings=(item,), keys=("first",))),
            rule("two", 10, evaluation(0, findings=(item,), keys=("second",))),
        )
        self.assertEqual(score.overall_points, 0)

    def test_low_confidence_finding_cannot_deduct_full_rule(self) -> None:
        item = finding(confidence=Confidence.LOW)
        score = self.score(rule("low_confidence", 10, evaluation(0, findings=(item,), keys=("issue",))))
        self.assertEqual(score.category_scores[0].earned_points, 5)
        self.assertIn("deduction is capped", score.category_scores[0].rule_breakdown[0].reason)

    def test_high_confidence_finding_can_apply_full_rule_deduction(self) -> None:
        item = finding(confidence=Confidence.HIGH, severity=Severity.CRITICAL)
        score = self.score(rule("high_confidence", 10, evaluation(0, findings=(item,), keys=("issue",))))
        self.assertEqual(score.category_scores[0].earned_points, 0)

    def test_critical_evidence_deducts_more_than_a_cosmetic_issue(self) -> None:
        critical = finding(title="Critical", severity=Severity.CRITICAL)
        cosmetic = finding(title="Cosmetic", severity=Severity.LOW)
        critical_score = self.score(rule("critical", 10, evaluation(0, findings=(critical,), keys=("critical",))))
        cosmetic_score = self.score(rule("cosmetic", 10, evaluation(0, findings=(cosmetic,), keys=("cosmetic",))))
        self.assertLess(
            critical_score.category_scores[0].earned_points,
            cosmetic_score.category_scores[0].earned_points,
        )

    def test_missing_finding_evidence_cannot_deduct_points(self) -> None:
        item = finding(evidence=False)
        score = self.score(rule("no_evidence", 10, evaluation(0, findings=(item,), keys=("issue",))))
        self.assertEqual(score.category_scores[0].earned_points, 10)
        self.assertEqual(score.category_scores[0].rule_breakdown[0].status, RuleScoreStatus.NOT_APPLICABLE)

    def test_not_applicable_rule_keeps_points_without_deduction(self) -> None:
        score = self.score(
            rule(
                "not_applicable",
                10,
                evaluation(1, status=RuleScoreStatus.NOT_APPLICABLE),
            )
        )
        rule_score = score.category_scores[0].rule_breakdown[0]
        self.assertEqual(rule_score.earned_points, 10)
        self.assertEqual(rule_score.status, RuleScoreStatus.NOT_APPLICABLE)

    def test_strength_extraction_uses_passing_rules(self) -> None:
        score = self.score(rule("robots", 5, evaluation(1)))
        self.assertEqual(len(score.top_strengths), 1)
        self.assertIn("Robots", score.top_strengths[0])

    def test_weakness_extraction_orders_largest_point_loss_first(self) -> None:
        score = self.score(rule("small", 2, evaluation(0)), rule("large", 8, evaluation(0)))
        self.assertIn("Large", score.top_weaknesses[0])

    def test_priority_actions_use_finding_recommendations(self) -> None:
        item = finding(title="Missing canonical")
        score = self.score(rule("canonical", 4, evaluation(0, findings=(item,), keys=("canonical",))))
        action = score.highest_priority_actions[0]
        self.assertEqual(action.title, "Missing canonical")
        self.assertEqual(action.recommendation, "Make the documented improvement.")

    def test_priority_actions_prefer_higher_impact(self) -> None:
        low = finding(title="Low impact", impact=2)
        high = finding(title="High impact", impact=5)
        score = self.score(
            rule("low", 4, evaluation(0, findings=(low,), keys=("low",))),
            rule("high", 4, evaluation(0, findings=(high,), keys=("high",))),
        )
        self.assertEqual(score.highest_priority_actions[0].title, "High impact")

    def test_priority_actions_prefer_lower_effort_when_impact_matches(self) -> None:
        slow = finding(title="Slow", impact=4, effort=4)
        quick = finding(title="Quick", impact=4, effort=1)
        score = self.score(
            rule("slow", 4, evaluation(0, findings=(slow,), keys=("slow",))),
            rule("quick", 4, evaluation(0, findings=(quick,), keys=("quick",))),
        )
        self.assertEqual(score.highest_priority_actions[0].title, "Quick")

    def test_priority_actions_group_identical_recommendations_and_affected_pages(self) -> None:
        first = finding(
            title="Weak opening on first page",
            identifier="first-opening",
            page_url="https://example.com/first",
            recommendation="Improve opening summaries.",
            impact=4,
            effort=1,
        )
        second = finding(
            title="Weak opening on second page",
            identifier="second-opening",
            page_url="https://example.com/second",
            recommendation="Improve opening summaries.",
            impact=4,
            effort=1,
        )
        score = self.score(
            rule("first_opening", 4, evaluation(0, findings=(first,), keys=("first",))),
            rule("second_opening", 4, evaluation(0, findings=(second,), keys=("second",))),
        )

        self.assertEqual(len(score.highest_priority_actions), 1)
        action = score.highest_priority_actions[0]
        self.assertEqual(action.recommendation, "Improve opening summaries.")
        self.assertEqual(action.frequency, 2)
        self.assertEqual(action.affected_urls, ["https://example.com/first", "https://example.com/second"])
        self.assertEqual(set(action.linked_finding_ids), {"first-opening", "second-opening"})

    def test_priority_actions_use_frequency_after_impact_and_effort(self) -> None:
        common_one = finding(title="Common one", identifier="common-one", recommendation="Common action.", impact=4, effort=2)
        common_two = finding(title="Common two", identifier="common-two", recommendation="Common action.", impact=4, effort=2)
        rare = finding(title="Rare", identifier="rare", recommendation="Rare action.", impact=4, effort=2)
        score = self.score(
            rule("common_one", 4, evaluation(0, findings=(common_one,), keys=("common-one",))),
            rule("common_two", 4, evaluation(0, findings=(common_two,), keys=("common-two",))),
            rule("rare", 4, evaluation(0, findings=(rare,), keys=("rare",))),
        )
        self.assertEqual(score.highest_priority_actions[0].recommendation, "Common action.")

    def test_priority_actions_are_not_created_without_findings(self) -> None:
        score = self.score(rule("abstract", 4, evaluation(0, keys=("abstract",))))
        self.assertEqual(score.highest_priority_actions, [])

    def test_linked_finding_ids_are_retained_in_rule_breakdown(self) -> None:
        item = finding(title="Linked evidence")
        score = self.score(rule("linked", 4, evaluation(0, findings=(item,), keys=("linked",))))
        self.assertEqual(score.category_scores[0].rule_breakdown[0].linked_finding_ids, [item.id])

    def test_cli_score_view_shows_categories_rules_and_actions(self) -> None:
        item = finding(title="Missing llms.txt")
        prepared = result()
        prepared = prepared.model_copy(
            update={"scoring": GeoScoringEngine((rule("llms", 3, evaluation(0, findings=(item,), keys=("llms",))),)).score(prepared)}
        )
        output = io.StringIO()
        with redirect_stdout(output):
            _print_score(prepared)
        rendered = output.getvalue()
        self.assertIn("Overall GEO Score", rendered)
        self.assertIn("AI Discoverability", rendered)
        self.assertIn("Llms", rendered)
        self.assertIn("25%", rendered)
        self.assertIn("Priority actions", rendered)
        self.assertIn("Missing llms.txt", rendered)
        self.assertIn("Affected pages:", rendered)
        self.assertNotIn("finding-missing-llms.txt", rendered)

    def test_score_labels_are_stable_at_each_threshold(self) -> None:
        self.assertEqual(_score_label(85), "Excellent")
        self.assertEqual(_score_label(70), "Good")
        self.assertEqual(_score_label(50), "Needs Improvement")
        self.assertEqual(_score_label(49.99), "Poor")

    def test_cli_score_view_handles_unavailable_scoring(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _print_score(result())
        self.assertIn("Transparent scoring was unavailable", output.getvalue())

    def test_default_engine_returns_all_four_categories(self) -> None:
        score = GeoScoringEngine().score(result())
        self.assertEqual([item.category for item in score.category_scores], list(AuditCategory))

    def test_default_engine_without_analyzer_data_does_not_deduct(self) -> None:
        score = GeoScoringEngine().score(result())
        self.assertEqual(score.overall_points, 100)
        self.assertTrue(all(item.status == RuleScoreStatus.NOT_APPLICABLE for category in score.category_scores for item in category.rule_breakdown))


if __name__ == "__main__":
    unittest.main()
