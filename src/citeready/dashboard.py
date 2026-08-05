"""Pure, presentation-only helpers for the Streamlit business report."""

from __future__ import annotations

import ipaddress
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

import requests

from .models import (
    AuditCategory,
    CategoryScore,
    CrawlResult,
    DiscoverabilityFinding,
    PriorityAction,
)
from .url_utils import normalize_url


PRIMARY_ACTION_LIMIT = 5
MAX_EVIDENCE_CHARACTERS = 320


@dataclass(frozen=True, slots=True)
class CategoryCard:
    """Business-readable values for one category score card."""

    title: str
    earned_points: float
    maximum_points: float
    percentage: float
    status_label: str


@dataclass(frozen=True, slots=True)
class ActionCard:
    """A deduplicated remediation action enriched from linked findings."""

    title: str
    category: str
    why_it_matters: str
    affected_urls: tuple[str, ...]
    impact: int | None
    effort: int | None
    frequency: int
    priority_score: int
    recommendation: str
    copy_paste_fix: str | None


def dashboard_score_label(percentage: float) -> str:
    """Return the Phase 7 business-facing label for a 0–100 score."""

    if percentage >= 90:
        return "Excellent"
    if percentage >= 75:
        return "Good"
    if percentage >= 60:
        return "Needs Improvement"
    return "Poor"


def category_card(score: CategoryScore) -> CategoryCard:
    """Format a category without making any scoring decision."""

    return CategoryCard(
        title=score.category.value,
        earned_points=score.earned_points,
        maximum_points=score.maximum_points,
        percentage=score.percentage,
        status_label=dashboard_score_label(score.percentage),
    )


def all_findings(result: CrawlResult) -> list[DiscoverabilityFinding]:
    """Return the existing shared findings in their four user-facing categories."""

    findings: list[DiscoverabilityFinding] = []
    for analysis in (
        result.discoverability,
        result.citation_readiness,
        result.entity_trust,
        result.answerability,
    ):
        if analysis:
            findings.extend(analysis.findings)
    return findings


def findings_by_category(result: CrawlResult) -> dict[AuditCategory, list[DiscoverabilityFinding]]:
    """Group findings in the stable dashboard category order."""

    groups = {category: [] for category in AuditCategory}
    for finding in all_findings(result):
        groups[finding.category].append(finding)
    return groups


def action_cards(result: CrawlResult) -> list[ActionCard]:
    """Enrich the scoring engine's already-deduplicated action plan for display."""

    if not result.scoring:
        return []
    finding_map = {finding.id: finding for finding in all_findings(result)}
    actions_by_recommendation: dict[str, list[PriorityAction]] = defaultdict(list)
    for action in result.scoring.highest_priority_actions:
        actions_by_recommendation[action.recommendation].append(action)

    cards: list[ActionCard] = []
    for grouped_actions in actions_by_recommendation.values():
        cards.append(_action_card(_merge_actions(grouped_actions), finding_map))
    return sorted(
        cards,
        key=lambda card: (
            -(card.impact or 0),
            card.effort if card.effort is not None else 6,
            -len(card.affected_urls),
            card.title,
        ),
    )


def _merge_actions(actions: list[PriorityAction]) -> PriorityAction:
    """Defensively merge equivalent actions when restoring older report state."""

    ranked_actions = sorted(
        actions,
        key=lambda action: (
            -(action.impact or 0),
            action.effort if action.effort is not None else 6,
            action.title,
        ),
    )
    primary = ranked_actions[0]
    linked_finding_ids = list(
        dict.fromkeys(finding_id for action in ranked_actions for finding_id in action.linked_finding_ids)
    )
    affected_urls = list(
        dict.fromkeys(url for action in ranked_actions for url in action.affected_urls)
    )
    return PriorityAction(
        title=primary.title,
        recommendation=primary.recommendation,
        linked_finding_ids=linked_finding_ids,
        affected_urls=affected_urls,
        frequency=max(
            sum(action.frequency for action in ranked_actions),
            len(linked_finding_ids),
            len(affected_urls),
        ),
        impact=max((action.impact or 0) for action in ranked_actions) or None,
        effort=min(
            (action.effort for action in ranked_actions if action.effort is not None),
            default=None,
        ),
    )


def _action_card(
    action: PriorityAction,
    finding_map: dict[str, DiscoverabilityFinding],
) -> ActionCard:
    linked_findings = [
        finding_map[finding_id]
        for finding_id in action.linked_finding_ids
        if finding_id in finding_map
    ]
    categories = tuple(dict.fromkeys(finding.category.value for finding in linked_findings))
    affected_urls = tuple(
        dict.fromkeys(
            (*action.affected_urls, *(finding.affected_url for finding in linked_findings))
        )
    )
    primary_finding = linked_findings[0] if linked_findings else None
    impact = action.impact if action.impact is not None else (primary_finding.impact if primary_finding else None)
    effort = action.effort if action.effort is not None else (primary_finding.effort if primary_finding else None)
    frequency = max(action.frequency, len(linked_findings), len(affected_urls))
    return ActionCard(
        title=action.title,
        category=", ".join(categories) if categories else "General site improvement",
        why_it_matters=(
            primary_finding.why_it_matters
            if primary_finding
            else "This action addresses an evidence-backed GEO visibility weakness."
        ),
        affected_urls=affected_urls,
        impact=impact,
        effort=effort,
        frequency=frequency,
        priority_score=action_priority_score(impact, effort, frequency),
        recommendation=action.recommendation,
        copy_paste_fix=next(
            (finding.copy_paste_fix for finding in linked_findings if finding.copy_paste_fix),
            None,
        ),
    )


def action_priority_score(impact: int | None, effort: int | None, frequency: int) -> int:
    """Show a transparent action-priority indicator; it never changes GEO points.

    Impact contributes up to 60 points, low effort up to 25, and repeated
    affected pages up to 15. Dashboard sorting remains the requested explicit
    impact, effort, then frequency order.
    """

    impact_points = ((impact or 0) / 5) * 60
    effort_points = ((6 - effort) / 5) * 25 if effort is not None else 0
    frequency_points = (min(max(frequency, 0), 5) / 5) * 15
    return round(impact_points + effort_points + frequency_points)


def page_inventory(result: CrawlResult) -> list[dict[str, Any]]:
    """Build a compact page-level inventory without exposing internal IDs."""

    finding_counts: dict[str, int] = defaultdict(int)
    for finding in all_findings(result):
        finding_counts[finding.affected_url] += 1
    canonical_states = {}
    if result.discoverability:
        canonical_states = {
            item.page_url: item.state.value.replace("_", " ").title()
            for item in result.discoverability.canonical.pages
        }

    inventory = []
    for page in result.pages:
        robots_values = " ".join(page.robots_meta.values()).lower()
        inventory.append(
            {
                "URL": page.url,
                "Status": page.status_code,
                "Title": page.title or "—",
                "Word count": len(page.text_content.split()),
                "Canonical": canonical_states.get(page.url, "Not analyzed"),
                "Indexability": "Noindex" if "noindex" in robots_values else "Indexable",
                "Findings": finding_counts[page.url],
            }
        )
    return inventory


def concise_evidence(finding: DiscoverabilityFinding) -> list[str]:
    """Return bounded evidence excerpts while preserving full evidence in models."""

    excerpts = []
    for evidence in finding.evidence[:3]:
        text = evidence.exact_text.strip()
        if len(text) > MAX_EVIDENCE_CHARACTERS:
            text = f"{text[:MAX_EVIDENCE_CHARACTERS].rstrip()}…"
        excerpts.append(text)
    return excerpts


def validate_dashboard_url(value: str) -> tuple[str | None, str | None]:
    """Validate a public HTTP(S) target before an audit starts."""

    normalized = normalize_url(value)
    if not normalized:
        return None, "Enter a valid public HTTP or HTTPS website URL."
    host = urlsplit(normalized).hostname
    if not host or host.lower() == "localhost":
        return None, "Enter a public website URL rather than a local address."
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return normalized, None
    if not address.is_global:
        return None, "Enter a public website URL rather than a private network address."
    return normalized, None


def safe_error_message(error: Exception) -> str:
    """Translate expected network failures into concise business-facing help."""

    if isinstance(error, requests.exceptions.SSLError):
        return "The website's SSL certificate could not be verified. Check the URL or try again later."
    if isinstance(error, requests.exceptions.Timeout):
        return "The website took too long to respond. Try again later or audit fewer pages."
    if isinstance(error, requests.exceptions.ConnectionError):
        return "The website could not be reached. Check the URL and confirm that it is publicly available."
    if isinstance(error, ValueError):
        return "Enter a valid public HTTP or HTTPS website URL."
    return "The audit could not be completed. Please try again shortly."


def serialize_report_state(result: CrawlResult) -> str:
    """Serialize a completed report safely for Streamlit session state or caching."""

    return result.model_dump_json()


def deserialize_report_state(payload: str) -> CrawlResult:
    """Restore a completed report serialized by :func:`serialize_report_state`."""

    return CrawlResult.model_validate_json(payload)


def action_card_dict(card: ActionCard) -> dict[str, Any]:
    """Provide a serializable shape for table and chart rendering."""

    return asdict(card)
