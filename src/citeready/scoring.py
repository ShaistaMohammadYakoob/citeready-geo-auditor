"""Transparent aggregation of configurable GEO scoring rules."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import (
    CategoryScore,
    Confidence,
    CrawlResult,
    OverallScore,
    PriorityAction,
    RuleScore,
    RuleScoreStatus,
)
from .scoring_rules import (
    DEFAULT_SCORING_RULES,
    LOW_CONFIDENCE_MAX_DEDUCTION,
    SEVERITY_DEDUCTION_CAPS,
    RuleEvaluation,
    ScoringContext,
    ScoringRule,
)


ROUNDING_PLACES = 2
MAX_SUMMARY_ITEMS = 5


class GeoScoringEngine:
    """Convert deterministic analyses into an explainable, evidence-linked score.

    Rules remain independent and configured in :mod:`citeready.scoring_rules`.
    This class only applies cross-cutting safeguards: absent evidence cannot
    deduct, a low-confidence signal cannot remove more than half of a rule,
    and an already-used deduction key cannot remove points twice.
    """

    def __init__(self, rules: Iterable[ScoringRule] = DEFAULT_SCORING_RULES) -> None:
        self.rules = tuple(rules)

    def score(self, result: CrawlResult) -> OverallScore:
        """Return the complete score without changing any analyzer result."""

        context = ScoringContext(result=result)
        grouped_rules: dict = defaultdict(list)
        for rule in self.rules:
            grouped_rules[rule.category].append(rule)

        used_deduction_keys: set[str] = set()
        category_scores: list[CategoryScore] = []
        weak_rules: list[tuple[float, RuleScore, RuleEvaluation]] = []
        strong_rules: list[RuleScore] = []

        # Custom rule sets used by integrators and tests should produce only the
        # categories they configure. The default configuration already supplies
        # all four 25-point categories in its documented order.
        category_order = tuple(grouped_rules.keys())
        for category in category_order:
            rule_breakdown: list[RuleScore] = []
            for rule in grouped_rules.get(category, []):
                evaluation = rule.evaluation_function(context)
                rule_score = self._score_rule(rule, evaluation, used_deduction_keys)
                rule_breakdown.append(rule_score)
                if rule_score.status == RuleScoreStatus.PASS:
                    strong_rules.append(rule_score)
                elif rule_score.status in {RuleScoreStatus.PARTIAL, RuleScoreStatus.FAIL}:
                    weak_rules.append((rule_score.max_points - rule_score.earned_points, rule_score, evaluation))

            maximum_points = round(sum(rule.max_points for rule in rule_breakdown), ROUNDING_PLACES)
            earned_points = round(sum(rule.earned_points for rule in rule_breakdown), ROUNDING_PLACES)
            percentage = round((earned_points / maximum_points * 100) if maximum_points else 100, ROUNDING_PLACES)
            category_scores.append(
                CategoryScore(
                    category=category,
                    maximum_points=maximum_points,
                    earned_points=earned_points,
                    percentage=percentage,
                    rule_breakdown=rule_breakdown,
                )
            )

        maximum_points = sum(category.maximum_points for category in category_scores)
        overall_points = round(sum(category.earned_points for category in category_scores), ROUNDING_PLACES)
        overall_percentage = round(
            (overall_points / maximum_points * 100) if maximum_points else 100,
            ROUNDING_PLACES,
        )
        ordered_weaknesses = sorted(weak_rules, key=lambda item: (-item[0], item[1].title))
        return OverallScore(
            overall_points=overall_points,
            overall_percentage=overall_percentage,
            category_scores=category_scores,
            top_strengths=[
                f"{score.title}: {score.reason}"
                for score in sorted(strong_rules, key=lambda item: (-item.max_points, item.title))[
                    :MAX_SUMMARY_ITEMS
                ]
            ],
            top_weaknesses=[
                f"{score.title}: {score.reason}"
                for _, score, _ in ordered_weaknesses[:MAX_SUMMARY_ITEMS]
            ],
            highest_priority_actions=self._priority_actions(ordered_weaknesses),
        )

    def _score_rule(
        self,
        rule: ScoringRule,
        evaluation: RuleEvaluation,
        used_deduction_keys: set[str],
    ) -> RuleScore:
        """Apply the safeguards shared by every configurable rule."""

        quality = evaluation.quality
        status = evaluation.status
        reason = evaluation.reason
        linked_finding_ids = [finding.id for finding in evaluation.findings]

        # A finding must carry evidence before it can take points from a site.
        if evaluation.findings and not any(finding.evidence for finding in evaluation.findings):
            quality = 1.0
            status = RuleScoreStatus.NOT_APPLICABLE
            reason = "No evidence-backed finding was available, so this rule was not deducted."
        # Severity is a configurable safeguard: a critical issue can affect an
        # entire rule, while a single cosmetic issue cannot.
        elif quality < 1 and evaluation.findings:
            maximum_deduction = min(
                1.0,
                sum(SEVERITY_DEDUCTION_CAPS[finding.severity] for finding in evaluation.findings),
            )
            severity_limited_quality = max(quality, 1 - maximum_deduction)
            if severity_limited_quality > quality:
                quality = severity_limited_quality
                status = RuleScoreStatus.PARTIAL if quality < 1 else RuleScoreStatus.PASS
                reason = f"{reason} The deduction is capped by the severity of the linked finding(s)."
        # Low-confidence evidence can flag an action but cannot remove all rule points.
        if quality < 1 and evaluation.findings and all(
            finding.confidence == Confidence.LOW for finding in evaluation.findings
        ):
            quality = max(quality, 1 - LOW_CONFIDENCE_MAX_DEDUCTION)
            status = RuleScoreStatus.PARTIAL if quality < 1 else RuleScoreStatus.PASS
            reason = (
                f"{reason} The linked evidence is low confidence, so the deduction is capped at "
                f"{int(LOW_CONFIDENCE_MAX_DEDUCTION * 100)}% of this rule."
            )
        # A single observable issue can be linked by several rules.  The first
        # rule accounts for it; later rules disclose it without deducting twice.
        elif quality < 1 and evaluation.deduction_keys and any(
            key in used_deduction_keys for key in evaluation.deduction_keys
        ):
            quality = 1.0
            status = RuleScoreStatus.PASS
            reason = "The linked issue was already deducted by another rule, so no duplicate deduction was made."

        if quality < 1:
            used_deduction_keys.update(evaluation.deduction_keys)
        return RuleScore(
            rule_id=rule.id,
            title=rule.title,
            max_points=round(rule.maximum_points, ROUNDING_PLACES),
            earned_points=round(rule.maximum_points * quality, ROUNDING_PLACES),
            status=status,
            reason=reason,
            linked_finding_ids=linked_finding_ids,
        )

    @staticmethod
    def _priority_actions(
        weak_rules: list[tuple[float, RuleScore, RuleEvaluation]],
    ) -> list[PriorityAction]:
        """Group equivalent remediations and order them for practical execution."""

        findings_by_recommendation: dict[str, dict[str, object]] = {}
        for _points_lost, _rule_score, evaluation in weak_rules:
            for finding in evaluation.findings:
                group = findings_by_recommendation.setdefault(
                    finding.recommendation,
                    {"findings": {}},
                )
                group_findings = group["findings"]
                assert isinstance(group_findings, dict)
                group_findings.setdefault(finding.id, finding)

        actions: list[PriorityAction] = []
        for recommendation, group in findings_by_recommendation.items():
            group_findings = group["findings"]
            assert isinstance(group_findings, dict)
            findings = list(group_findings.values())
            findings.sort(
                key=lambda finding: (
                    -(finding.impact or 0),
                    finding.effort if finding.effort is not None else 6,
                    finding.title,
                )
            )
            actions.append(
                PriorityAction(
                    title=findings[0].title,
                    recommendation=recommendation,
                    linked_finding_ids=[finding.id for finding in findings],
                    affected_urls=list(dict.fromkeys(finding.affected_url for finding in findings)),
                    frequency=len(findings),
                    impact=max((finding.impact or 0) for finding in findings) or None,
                    effort=min(
                        (finding.effort for finding in findings if finding.effort is not None),
                        default=None,
                    ),
                )
            )

        return sorted(
            actions,
            key=lambda action: (
                -(action.impact or 0),
                action.effort if action.effort is not None else 6,
                -action.frequency,
                action.title,
            ),
        )[:MAX_SUMMARY_ITEMS]
