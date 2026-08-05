"""Command-line smoke test for CiteReady's deterministic GEO analyses."""

from __future__ import annotations

import argparse
import re
import sys

from pydantic import ValidationError

from .config import load_crawler_settings
from .crawler import SiteCrawler
from .models import (
    BotAccess,
    CrawlResult,
    DiscoverabilityFinding,
    Evidence,
    SitemapAnalysisStatus,
)


CHECK_MARK = "\u2713"
CROSS_MARK = "\u2717"
WARNING_MARK = "\u26a0"
MAX_EVIDENCE_CHARACTERS = 250
MAX_DISPLAYED_EXAMPLES = 5
ENTITY_FINDING_GROUPS = (
    "Entity identity",
    "Structured data",
    "Contact and organization pages",
    "Author signals",
    "Trust signals",
    "Social/knowledge graph signals",
)


def main() -> int:
    """Run a bounded crawl and print the requested deterministic analysis views."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Smoke-test CiteReady's deterministic GEO analyzers.")
    parser.add_argument("url", help="Public HTTP(S) URL to crawl, for example https://example.com")
    parser.add_argument("--max-pages", type=int, help="Override the configured limit (1-12).")
    parser.add_argument(
        "--show-findings",
        action="store_true",
        help="Print detailed, evidence-backed discoverability findings after the summary.",
    )
    parser.add_argument(
        "--show-citation-findings",
        action="store_true",
        help="Print detailed, evidence-backed Citation Readiness findings after the summary.",
    )
    parser.add_argument(
        "--show-entity-findings",
        action="store_true",
        help="Print detailed, evidence-backed Entity and Trust findings after the summary.",
    )
    parser.add_argument(
        "--show-answerability",
        action="store_true",
        help="Print deterministic AI Answerability results after the summary.",
    )
    parser.add_argument(
        "--show-score",
        action="store_true",
        help="Print the transparent, rule-by-rule GEO score after the summary.",
    )
    arguments = parser.parse_args()

    try:
        settings = load_crawler_settings()
        if arguments.max_pages is not None:
            settings = type(settings).model_validate(
                {**settings.model_dump(), "max_pages": arguments.max_pages}
            )
        result = SiteCrawler(settings).crawl(arguments.url)
    except (ValidationError, ValueError) as error:
        print(f"Crawler configuration error: {error}", file=sys.stderr)
        return 2

    _print_discoverability_report(result)
    if arguments.show_findings:
        _print_findings(result)
    if arguments.show_citation_findings:
        _print_citation_findings(result)
    if arguments.show_entity_findings:
        _print_entity_findings(result)
    if arguments.show_answerability:
        _print_answerability(result)
    if arguments.show_score:
        _print_score(result)
    if result.warnings:
        print("\nWarnings")
        for warning in result.warnings:
            location = f" ({warning.url})" if warning.url else ""
            print(f"- [{warning.code}] {warning.message}{location}")
    return 0


def _print_discoverability_report(result: CrawlResult) -> None:
    """Print the concise, unscored Phase 2 smoke-test summary."""

    print("==============================")
    print("DISCOVERABILITY REPORT")
    print("==============================")
    discoverability = result.discoverability
    if discoverability is None:
        print("Discoverability analysis was unavailable. See warnings below.")
        return

    robots = discoverability.robots_txt
    print("\nRobots.txt")
    print(f"{CHECK_MARK} Found" if robots.found else f"{CROSS_MARK} Missing")
    for bot in robots.bot_access:
        marker = (
            CHECK_MARK
            if bot.access == BotAccess.ALLOWED
            else CROSS_MARK
            if bot.access == BotAccess.BLOCKED
            else "?"
        )
        print(f"{marker} {bot.bot_name} {bot.access.value}")

    sitemap = discoverability.sitemap
    print("\nSitemap")
    if sitemap.status == SitemapAnalysisStatus.PARTIAL:
        print(f"{WARNING_MARK} Present but only partially analyzed")
        print(f"Parsed URLs: {sitemap.parsed_url_count}")
        print(f"Parsed files: {len(sitemap.successfully_parsed_sitemap_files)}")
        print(f"Skipped files: {len(sitemap.skipped_sitemap_files)}")
        print("URL count may be incomplete")
    elif sitemap.status == SitemapAnalysisStatus.COMPLETE:
        print(f"{CHECK_MARK} Present")
        print(f"{CHECK_MARK} {sitemap.parsed_url_count} URL{'s' if sitemap.parsed_url_count != 1 else ''}")
    elif sitemap.status == SitemapAnalysisStatus.INVALID:
        print(f"{WARNING_MARK} Present but invalid")
    else:
        print(f"{CROSS_MARK} Missing or unavailable")

    canonical = discoverability.canonical
    print("\nCanonical")
    if canonical.missing_page_urls:
        print(f"{WARNING_MARK} Missing on {len(canonical.missing_page_urls)} page(s)")
    elif canonical.external_canonical_page_urls:
        print(f"{WARNING_MARK} External on {len(canonical.external_canonical_page_urls)} page(s)")
    else:
        print(f"{CHECK_MARK} Present on all crawled pages")

    meta_robots = discoverability.meta_robots
    print("\nMeta Robots")
    if meta_robots.noindex_pages:
        print(f"{WARNING_MARK} noindex on {len(meta_robots.noindex_pages)} page(s)")
    else:
        print(f"{CHECK_MARK} No noindex pages")

    llms_txt = discoverability.llms_txt
    print("\nLLMS.txt")
    print(f"{CHECK_MARK} Found" if llms_txt.found else f"{CROSS_MARK} Missing")


def _print_findings(result: CrawlResult) -> None:
    """Print the shared finding contract in a terminal-readable CLI form."""

    discoverability = result.discoverability
    if discoverability is None:
        return

    print("\nDetailed findings")
    if not discoverability.findings:
        print("No actionable discoverability findings were detected.")
        return

    _print_finding_details(discoverability.findings)


def _print_citation_findings(result: CrawlResult) -> None:
    """Print detailed, deterministic Citation Readiness findings."""

    citation_readiness = result.citation_readiness
    if citation_readiness is None:
        return

    print("\nCitation Readiness findings")
    if not citation_readiness.findings:
        print("No actionable Citation Readiness findings were detected.")
        return

    _print_finding_details(citation_readiness.findings)


def _print_entity_findings(result: CrawlResult) -> None:
    """Print detailed Entity and Trust findings in their user-facing analysis groups."""

    entity_trust = result.entity_trust
    if entity_trust is None:
        return

    print("\nEntity and Trust findings")
    if not entity_trust.findings:
        print("No actionable Entity and Trust findings were detected.")
        return

    grouped_findings: dict[str, list[DiscoverabilityFinding]] = {}
    for finding in entity_trust.findings:
        grouped_findings.setdefault(_entity_finding_group(finding), []).append(finding)
    for group in ENTITY_FINDING_GROUPS:
        findings = grouped_findings.get(group)
        if not findings:
            continue
        print(f"\n{group}")
        print("=" * len(group))
        _print_finding_details(findings)


def _print_answerability(result: CrawlResult) -> None:
    """Print Phase 5 question classifications with their exact crawled support."""

    analysis = result.answerability
    if analysis is None:
        return

    print("\nAI Answerability")
    if analysis.primary_entity.entity_name:
        print(
            f"Primary entity: {analysis.primary_entity.entity_name} "
            f"({analysis.primary_entity.confidence.value} confidence)"
        )
    for answer in analysis.results:
        print(f"\n{answer.question.label}")
        print(f"Status: {answer.status.value}")
        print(f"Confidence: {answer.confidence.value}")
        if answer.answer_excerpt:
            print(f"Answer: {_truncate_evidence(answer.answer_excerpt)}")
        if answer.supporting_urls:
            source_label = "Source" if len(answer.supporting_urls) == 1 else "Sources"
            print(f"{source_label}: {', '.join(answer.supporting_urls)}")
        if answer.evidence:
            evidence = answer.evidence[0]
            if evidence.answer_reason:
                print(f"Why this answers the question: {evidence.answer_reason}")
            if evidence.entity_relevance_reason:
                print(f"Entity relevance: {evidence.entity_relevance_reason}")
        if answer.conflicting_excerpt:
            print(f"Conflicting answer: {_truncate_evidence(answer.conflicting_excerpt)}")
        print(f"Reason: {answer.explanation}")
        print(f"Recommended action: {answer.recommendation}")

    summary = analysis.summary
    print("\nSummary:")
    print(f"Clearly answered: {summary.clearly_answered}")
    print(f"Partially answered: {summary.partially_answered}")
    print(f"Not answered: {summary.not_answered}")
    print(f"Conflicting answer: {summary.conflicting_answer}")
    print(f"Not applicable: {summary.not_applicable}")


def _print_score(result: CrawlResult) -> None:
    """Print every configured scoring rule so the GEO score is never opaque."""

    score = result.scoring
    if score is None:
        print("\nOverall GEO Score")
        print("Transparent scoring was unavailable. See warnings below.")
        return

    print("\nOverall GEO Score")
    print(f"\n{_format_points(score.overall_points)}/100 — {_score_label(score.overall_percentage)}")
    for category in score.category_scores:
        print(f"\n{category.category.value}")
        print(f"{_format_points(category.earned_points)}/{_format_points(category.maximum_points)}")
        print(f"{_format_points(category.percentage)}%")
        for rule in category.rule_breakdown:
            print(
                f"  {rule.title}: {_format_points(rule.earned_points)}/"
                f"{_format_points(rule.max_points)} ({rule.status.value})"
            )
            print(f"    {rule.reason}")

    print("\nWhy")
    if score.top_strengths:
        for strength in score.top_strengths:
            print(f"+ {strength}")
    if score.top_weaknesses:
        for weakness in score.top_weaknesses:
            print(f"- {weakness}")
    if not score.top_strengths and not score.top_weaknesses:
        print("No rule outcomes were available.")

    print("\nPriority actions")
    if not score.highest_priority_actions:
        print("No evidence-backed remediation actions were selected.")
        return
    for index, action in enumerate(score.highest_priority_actions, start=1):
        print(f"{index}. {action.title}")
        print(f"   Recommended action: {action.recommendation}")
        if action.affected_urls:
            print("   Affected pages:")
            for page_url in action.affected_urls:
                print(f"   - {page_url}")
        if action.impact is not None:
            print(f"   Estimated impact: {_impact_label(action.impact)}")
        if action.effort is not None:
            print(f"   Estimated effort: {_effort_label(action.effort)}")


def _format_points(points: float) -> str:
    """Avoid visual noise for whole-number rule and category scores."""

    return str(int(points)) if float(points).is_integer() else f"{points:.2f}".rstrip("0").rstrip(".")


def _score_label(percentage: float) -> str:
    """Use a stable, presentation-only label for the overall percentage."""

    if percentage >= 85:
        return "Excellent"
    if percentage >= 70:
        return "Good"
    if percentage >= 50:
        return "Needs Improvement"
    return "Poor"


def _impact_label(value: int) -> str:
    return "High" if value >= 4 else "Medium" if value >= 3 else "Low"


def _effort_label(value: int) -> str:
    return "High" if value >= 4 else "Medium" if value >= 3 else "Low"


def _print_finding_details(findings: list[DiscoverabilityFinding]) -> None:
    """Print shared findings by page while retaining all source data in memory."""

    findings_by_page: dict[str, list[DiscoverabilityFinding]] = {}
    for finding in findings:
        findings_by_page.setdefault(finding.affected_url, []).append(finding)

    for page_url, page_findings in findings_by_page.items():
        print(f"\nPage: {page_url}")
        print("-" * min(72, len(page_url) + 6))
        for finding in page_findings:
            _print_one_finding(finding)


def _print_one_finding(finding: DiscoverabilityFinding) -> None:
    """Render one finding with small, finding-specific evidence summaries."""

    print(f"\n[{finding.severity.value.upper()}] {finding.title}")
    print(f"Confidence: {finding.confidence.value}")
    if finding.title == "Page has multiple H1 headings":
        _print_h1_summary(finding)
    elif finding.title == "Opening does not clearly state what the page is about":
        _print_opening_summary(finding)
    elif finding.title.startswith("Potentially unsupported claims"):
        _print_evidence(finding.evidence, max_examples=MAX_DISPLAYED_EXAMPLES)
    elif finding.title == "Question headings do not have visible answers":
        _print_evidence(finding.evidence, max_examples=MAX_DISPLAYED_EXAMPLES)
    elif finding.title == "Potential official profiles are missing from organization sameAs":
        _print_evidence(finding.evidence, max_examples=MAX_DISPLAYED_EXAMPLES)
    elif finding.title.startswith("Multiple potential ") and finding.title.endswith(" profiles detected"):
        _print_profile_candidates(finding.evidence)
    else:
        _print_evidence(finding.evidence)

    print(f"Why it matters: {finding.why_it_matters}")
    print(f"Recommended action: {finding.recommendation}")
    if finding.impact is not None:
        print(f"Impact: {finding.impact}/5")
    if finding.effort is not None:
        print(f"Effort: {finding.effort}/5")
    if finding.copy_paste_fix is not None:
        print("Copy-paste fix:")
        print(finding.copy_paste_fix)


def _print_h1_summary(finding: DiscoverabilityFinding) -> None:
    """Summarize multiple-H1 evidence without dumping every detected heading."""

    h1_headings = _h1_headings(finding)
    print(f"Detected H1 count: {len(h1_headings)}")
    print("First five headings:")
    for heading in h1_headings[:MAX_DISPLAYED_EXAMPLES]:
        print(f"- {heading}")
    print(f"Remaining count: {max(0, len(h1_headings) - MAX_DISPLAYED_EXAMPLES)}")


def _h1_headings(finding: DiscoverabilityFinding) -> list[str]:
    headings: list[str] = []
    for evidence in finding.evidence:
        headings.extend(match.strip() for match in re.findall(r"(?:^|;\s*)H1:\s*([^;]+)", evidence.exact_text))
    return headings


def _print_opening_summary(finding: DiscoverabilityFinding) -> None:
    """Display a readable opening assessment instead of a raw content dump."""

    evidence = finding.evidence[0] if finding.evidence else None
    if evidence is None:
        return
    print(f"Opening excerpt: {_truncate_evidence(evidence.exact_text)}")
    if evidence.context:
        print(f"Reason: {evidence.context}")


def _print_evidence(
    evidence_items: list[Evidence],
    *,
    max_examples: int | None = None,
) -> None:
    """Print bounded evidence excerpts while leaving the full models untouched."""

    displayed_items = evidence_items if max_examples is None else evidence_items[:max_examples]
    for index, evidence in enumerate(displayed_items):
        label = "Evidence" if index == 0 else "Additional evidence"
        print(f"{label}: {_truncate_evidence(evidence.exact_text)}")
        if evidence.context:
            print(f"  Context: {evidence.context}")
    omitted_count = len(evidence_items) - len(displayed_items)
    if omitted_count:
        print(f"(+{omitted_count} additional matches)")


def _truncate_evidence(text: str) -> str:
    """Keep terminal evidence to a readable length without mutating stored evidence."""

    if len(text) <= MAX_EVIDENCE_CHARACTERS:
        return text
    additional_characters = len(text) - MAX_EVIDENCE_CHARACTERS
    excerpt = text[:MAX_EVIDENCE_CHARACTERS].rstrip()
    return f"{excerpt}...\n  (+{additional_characters} additional characters retained)"


def _print_profile_candidates(evidence_items: list[Evidence]) -> None:
    """Render distinct same-platform candidates as a compact verification list."""

    print("Potential profiles:")
    for evidence in evidence_items[:MAX_DISPLAYED_EXAMPLES]:
        print(f"- {_truncate_evidence(evidence.exact_text)}")
        if evidence.context:
            print(f"  Context: {evidence.context}")
    omitted_count = len(evidence_items) - min(len(evidence_items), MAX_DISPLAYED_EXAMPLES)
    if omitted_count:
        print(f"(+{omitted_count} additional matches)")


def _entity_finding_group(finding: DiscoverabilityFinding) -> str:
    """Map the finite Phase 4 finding set to readable CLI sections."""

    title = finding.title
    if title == "Entity Consistency Risk":
        return "Entity identity"
    if "structured data" in title.lower() or "JSON-LD" in title:
        return "Structured data"
    if any(term in title for term in ("About", "Contact", "organization contact")):
        return "Contact and organization pages"
    if "Editorial" in title or "editorial" in title:
        return "Author signals"
    if "policy" in title.lower():
        return "Trust signals"
    if "profile" in title.lower() or "sameAs" in title:
        return "Social/knowledge graph signals"
    return "Trust signals"


if __name__ == "__main__":
    raise SystemExit(main())
