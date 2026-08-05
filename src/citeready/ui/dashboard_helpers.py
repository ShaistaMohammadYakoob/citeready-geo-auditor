"""Business-facing report transformations used by the refined dashboard."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import MutableMapping

from ..dashboard import ActionCard, action_cards, category_card, page_inventory
from ..models import AuditCategory, CrawlResult, DiscoverabilityFinding, Severity


def initialise_theme_state(state: MutableMapping[str, object]) -> str:
    """Keep a stable light fallback when browser system-theme detection is unavailable."""

    state.setdefault("theme_mode", "light")
    return str(state["theme_mode"])


def set_theme_mode(state: MutableMapping[str, object], is_dark: bool) -> str:
    """Persist the explicit UI choice without touching the completed audit result."""

    mode = "dark" if is_dark else "light"
    state["theme_mode"] = mode
    return mode


def report_header_sentence(result: CrawlResult) -> str:
    """Create a deterministic one-sentence audit interpretation from category scores."""

    if not result.scoring or not result.scoring.category_scores:
        return "Audit data is incomplete, so review the limitations before relying on conclusions."
    lowest = min(result.scoring.category_scores, key=lambda score: score.percentage)
    highest = max(result.scoring.category_scores, key=lambda score: score.percentage)
    if lowest.percentage >= 75:
        return "Strong foundation across the audit, with clear evidence to maintain."
    if highest.category == lowest.category:
        return f"{lowest.category.value} needs attention before the site has a reliable GEO foundation."
    return f"Good foundation in {highest.category.value}, but {lowest.category.value} needs attention."


def category_summaries(result: CrawlResult) -> list[dict[str, object]]:
    """Return small stable card payloads for the score panel and category tabs."""

    if not result.scoring:
        return []
    return [
        {
            "category": item.category,
            "title": item.category.value,
            "earned_points": item.earned_points,
            "maximum_points": item.maximum_points,
            "percentage": item.percentage,
            "status": category_card(item).status_label,
            "interpretation": category_interpretation(item.percentage),
            "rule_breakdown": item.rule_breakdown,
        }
        for item in result.scoring.category_scores
    ]


def category_interpretation(percentage: float) -> str:
    """Explain the score band without adding or changing score calculations."""

    if percentage >= 90:
        return "This area is a clear strength in the audited pages."
    if percentage >= 75:
        return "This area has a solid foundation with focused opportunities to improve."
    if percentage >= 60:
        return "This area is partly working but needs targeted attention."
    return "This area has material gaps that can limit AI visibility."


def findings_by_severity(findings: list[DiscoverabilityFinding]) -> dict[Severity, list[DiscoverabilityFinding]]:
    """Group existing findings in a predictable urgency order."""

    groups = {severity: [] for severity in Severity}
    for finding in findings:
        groups[finding.severity].append(finding)
    return groups


def category_findings(result: CrawlResult) -> dict[AuditCategory, list[DiscoverabilityFinding]]:
    """Expose the existing shared findings in the dashboard's four tabs."""

    groups = {category: [] for category in AuditCategory}
    for analysis in (
        result.discoverability,
        result.citation_readiness,
        result.entity_trust,
        result.answerability,
    ):
        if analysis:
            for finding in analysis.findings:
                groups[finding.category].append(finding)
    return groups


def action_cards_for_report(result: CrawlResult) -> list[ActionCard]:
    """Use the scoring engine action plan, retaining its deduplication and order."""

    return action_cards(result)


def inventory_filters(result: CrawlResult) -> dict[str, list[dict[str, object]]]:
    """Create inventory filter views without exposing internal finding identifiers."""

    rows = page_inventory(result)
    severe_urls = {
        finding.affected_url
        for findings in category_findings(result).values()
        for finding in findings
        if finding.severity in {Severity.CRITICAL, Severity.HIGH}
    }
    return {
        "All pages": rows,
        "Critical/high findings": [row for row in rows if row["URL"] in severe_urls],
        "Missing canonicals": [row for row in rows if row["Canonical"] == "Missing"],
        "Non-indexable": [row for row in rows if row["Indexability"] == "Noindex"],
    }


def safe_html(value: str) -> str:
    """Escape content before it is interpolated into a custom HTML component."""

    return escape(value, quote=True)
