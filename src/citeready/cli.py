"""Small command-line smoke test for the crawler and discoverability engine."""

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


def main() -> int:
    """Run a bounded crawl and print the unscored discoverability summary."""

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
    """Print the shared finding contract in a business-readable CLI form."""

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


if __name__ == "__main__":
    raise SystemExit(main())
