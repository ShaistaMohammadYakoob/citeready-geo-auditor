"""Small command-line smoke test for the Phase 1 crawler."""

from __future__ import annotations

import argparse
import sys

from pydantic import ValidationError

from .config import load_crawler_settings
from .crawler import SiteCrawler


def main() -> int:
    """Run a bounded crawl and print an operator-friendly summary."""

    parser = argparse.ArgumentParser(description="Smoke-test CiteReady's Phase 1 crawler.")
    parser.add_argument("url", help="Public HTTP(S) URL to crawl, for example https://example.com")
    parser.add_argument("--max-pages", type=int, help="Override the configured limit (1-12).")
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

    print(f"Requested URL: {result.requested_url}")
    print(f"Analyzed URL:  {result.analyzed_url}")
    print(f"Pages crawled: {len(result.pages)}/{result.max_pages}")
    for page in result.pages:
        label = page.title or "(untitled page)"
        print(f"  [{page.status_code}] {label} — {page.url}")

    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            location = f" ({warning.url})" if warning.url else ""
            print(f"  - [{warning.code}] {warning.message}{location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
