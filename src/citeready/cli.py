"""Small command-line smoke test for the crawler and discoverability engine."""

from __future__ import annotations

import argparse
import sys

from pydantic import ValidationError

from .config import load_crawler_settings
from .crawler import SiteCrawler
from .models import BotAccess, CrawlResult, SitemapAnalysisStatus


CHECK_MARK = "\u2713"
CROSS_MARK = "\u2717"
WARNING_MARK = "\u26a0"


def main() -> int:
    """Run a bounded crawl and print the unscored discoverability summary."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Smoke-test CiteReady's Phase 2 discoverability engine.")
    parser.add_argument("url", help="Public HTTP(S) URL to crawl, for example https://example.com")
    parser.add_argument("--max-pages", type=int, help="Override the configured limit (1-12).")
    parser.add_argument(
        "--show-findings",
        action="store_true",
        help="Print detailed, evidence-backed discoverability findings after the summary.",
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

    for finding in discoverability.findings:
        print(f"\n[{finding.severity.value.upper()}] {finding.title}")
        print(f"Page: {finding.affected_url}")
        for index, evidence in enumerate(finding.evidence):
            label = "Evidence" if index == 0 else "Additional evidence"
            print(f"{label}: {evidence.exact_text}")
        print(f"Why it matters: {finding.why_it_matters}")
        print(f"Recommended action: {finding.recommendation}")
        if finding.copy_paste_fix is not None:
            print("Copy-paste fix:")
            print(finding.copy_paste_fix)


if __name__ == "__main__":
    raise SystemExit(main())
