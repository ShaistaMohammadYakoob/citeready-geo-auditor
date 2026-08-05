"""Sitemap discovery, validation, and completeness-aware URL counting."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin
from xml.etree import ElementTree

from ..models import (
    DiscoverabilityFinding,
    Evidence,
    SitemapAnalysis,
    SitemapAnalysisStatus,
    SitemapDocument,
    Severity,
    SkippedSitemapFile,
)
from ..url_utils import is_same_domain, normalize_url
from .base import TextResourceFetcher, is_successful


MAX_SITEMAP_DOCUMENTS = 5


@dataclass(slots=True)
class ParsedSitemap:
    """Internal parse output that keeps public result models focused."""

    document: SitemapDocument
    page_urls: set[str]
    child_sitemaps: set[str]
    error: str | None = None


class SitemapAnalyzer:
    """Inspect a bounded set of same-domain sitemap documents safely."""

    def analyze(
        self,
        site_url: str,
        fetch: TextResourceFetcher,
        declared_sitemap_urls: list[str] | None = None,
    ) -> SitemapAnalysis:
        """Return a URL count only when every required sitemap file was parsed."""

        fallback_url = urljoin(site_url, "/sitemap.xml")
        declared_urls = _unique_urls(declared_sitemap_urls or [])
        queue: deque[str] = deque()
        discovered_files: list[str] = []
        required_for_complete: dict[str, bool] = {}
        documents: list[SitemapDocument] = []
        parsed_files: list[str] = []
        skipped_files: list[SkippedSitemapFile] = []
        findings: list[DiscoverabilityFinding] = []
        parsed_page_urls: set[str] = set()
        invalid_document_found = False

        def schedule(url: str, *, required: bool) -> None:
            normalized = normalize_url(url)
            if not normalized:
                return
            if normalized in required_for_complete:
                required_for_complete[normalized] = required_for_complete[normalized] or required
                return

            required_for_complete[normalized] = required
            discovered_files.append(normalized)
            if not is_same_domain(normalized, site_url):
                if required:
                    skipped_files.append(
                        SkippedSitemapFile(
                            url=normalized,
                            reason="Skipped because it is outside the audited domain.",
                        )
                    )
                return
            queue.append(normalized)

        # `/sitemap.xml` is a fallback when robots.txt declares another sitemap.
        schedule(fallback_url, required=not declared_urls)
        for sitemap_url in declared_urls:
            schedule(sitemap_url, required=True)

        while queue:
            sitemap_url = queue.popleft()
            if len(documents) >= MAX_SITEMAP_DOCUMENTS:
                if required_for_complete[sitemap_url]:
                    skipped_files.append(
                        SkippedSitemapFile(
                            url=sitemap_url,
                            reason=(
                                f"Skipped after reaching the {MAX_SITEMAP_DOCUMENTS}-file sitemap "
                                "analysis limit."
                            ),
                        )
                    )
                continue

            resource = fetch(sitemap_url)
            if not is_successful(resource):
                documents.append(
                    SitemapDocument(
                        url=sitemap_url,
                        status_code=resource.status_code,
                        error=resource.error or _http_error(resource.status_code),
                    )
                )
                if required_for_complete[sitemap_url]:
                    skipped_files.append(
                        SkippedSitemapFile(
                            url=sitemap_url,
                            reason=_fetch_failure_reason(resource),
                            status_code=resource.status_code,
                        )
                    )
                continue

            parsed = self._parse_document(resource.text or "", sitemap_url, resource.status_code)
            documents.append(parsed.document)
            if parsed.error:
                invalid_document_found = True
                findings.append(self._invalid_sitemap_finding(sitemap_url, parsed.error))
                if required_for_complete[sitemap_url]:
                    skipped_files.append(
                        SkippedSitemapFile(
                            url=sitemap_url,
                            reason=f"Skipped because the sitemap is invalid: {parsed.error}",
                            status_code=resource.status_code,
                        )
                    )
                continue

            parsed_files.append(sitemap_url)
            parsed_page_urls.update(parsed.page_urls)
            for child_url in sorted(parsed.child_sitemaps):
                schedule(child_url, required=True)

        status = _analysis_status(parsed_files, skipped_files, invalid_document_found)
        if status == SitemapAnalysisStatus.PARTIAL:
            findings.append(self._partial_finding(skipped_files))
        elif status == SitemapAnalysisStatus.UNAVAILABLE:
            findings.append(self._unavailable_finding(fallback_url, documents))
        elif status == SitemapAnalysisStatus.COMPLETE and not parsed_page_urls:
            parsed_url_file = next((document.url for document in documents if document.parsed), fallback_url)
            findings.append(
                DiscoverabilityFinding(
                    title="Sitemap contains no page URLs",
                    severity=Severity.LOW,
                    evidence=[
                        Evidence(
                            page_url=parsed_url_file,
                            exact_text="No <url><loc> entries were found in the parsed sitemap documents.",
                            source_type="sitemap.xml",
                        )
                    ],
                    affected_url=parsed_url_file,
                    why_it_matters=(
                        "An empty sitemap does not give search or answer engines additional URLs to discover."
                    ),
                    recommendation="Add canonical, indexable page URLs to the sitemap and submit the updated file.",
                    copy_paste_fix=None,
                )
            )

        return SitemapAnalysis(
            status=status,
            found=bool(parsed_files),
            discovered_sitemap_files=discovered_files,
            successfully_parsed_sitemap_files=parsed_files,
            skipped_sitemap_files=skipped_files,
            parsed_url_count=len(parsed_page_urls),
            url_count_is_complete=status == SitemapAnalysisStatus.COMPLETE,
            documents=documents,
            findings=findings,
        )

    def _parse_document(
        self,
        text: str,
        sitemap_url: str,
        status_code: int | None,
    ) -> ParsedSitemap:
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as error:
            message = f"Invalid XML: {error}"
            return ParsedSitemap(
                document=SitemapDocument(url=sitemap_url, status_code=status_code, error=message),
                page_urls=set(),
                child_sitemaps=set(),
                error=message,
            )

        root_name = _local_name(root.tag)
        if root_name == "urlset":
            page_urls = _loc_values(root, sitemap_url)
            return ParsedSitemap(
                document=SitemapDocument(
                    url=sitemap_url,
                    status_code=status_code,
                    url_count=len(page_urls),
                    parsed=True,
                ),
                page_urls=page_urls,
                child_sitemaps=set(),
            )
        if root_name == "sitemapindex":
            child_sitemaps = _loc_values(root, sitemap_url)
            return ParsedSitemap(
                document=SitemapDocument(
                    url=sitemap_url,
                    status_code=status_code,
                    is_index=True,
                    url_count=len(child_sitemaps),
                    parsed=True,
                ),
                page_urls=set(),
                child_sitemaps=child_sitemaps,
            )
        message = f"Expected <urlset> or <sitemapindex>, found <{root_name}>."
        return ParsedSitemap(
            document=SitemapDocument(url=sitemap_url, status_code=status_code, error=message),
            page_urls=set(),
            child_sitemaps=set(),
            error=message,
        )

    @staticmethod
    def _invalid_sitemap_finding(sitemap_url: str, error: str) -> DiscoverabilityFinding:
        return DiscoverabilityFinding(
            title="Sitemap XML is malformed or unsupported",
            severity=Severity.MEDIUM,
            evidence=[Evidence(page_url=sitemap_url, exact_text=error, source_type="sitemap.xml")],
            affected_url=sitemap_url,
            why_it_matters=(
                "Search and answer engines may be unable to read malformed sitemap XML and miss pages "
                "that depend on it for discovery."
            ),
            recommendation="Publish valid XML using a <urlset> or <sitemapindex> root element.",
            copy_paste_fix=None,
        )

    @staticmethod
    def _partial_finding(skipped_files: list[SkippedSitemapFile]) -> DiscoverabilityFinding:
        evidence = [
            Evidence(page_url=file.url, exact_text=file.reason, source_type="sitemap.xml")
            for file in skipped_files
        ]
        return DiscoverabilityFinding(
            title="Sitemap URL count is incomplete",
            severity=Severity.MEDIUM,
            evidence=evidence,
            affected_url=skipped_files[0].url,
            why_it_matters=(
                "One or more sitemap files could not be parsed, so the reported URL count covers only "
                "the successfully parsed files."
            ),
            recommendation=(
                "Reduce individual sitemap file sizes, split large partitions, or increase the configured "
                "limit only after reviewing the memory and network impact."
            ),
            copy_paste_fix=None,
        )

    @staticmethod
    def _unavailable_finding(
        fallback_url: str,
        documents: list[SitemapDocument],
    ) -> DiscoverabilityFinding:
        status = next((document.status_code for document in documents if document.status_code), None)
        missing = status == 404
        exact_text = f"HTTP {status}" if status else "No valid sitemap document could be retrieved."
        return DiscoverabilityFinding(
            title="Sitemap XML is missing" if missing else "Sitemap XML could not be retrieved",
            severity=Severity.MEDIUM,
            evidence=[Evidence(page_url=fallback_url, exact_text=exact_text, source_type="sitemap.xml")],
            affected_url=fallback_url,
            why_it_matters=(
                "A sitemap helps crawlers discover important pages, especially pages that have limited "
                "internal linking."
            ),
            recommendation="Generate and publish a valid sitemap at /sitemap.xml or declare its location in robots.txt.",
            copy_paste_fix=None,
        )


def _analysis_status(
    parsed_files: list[str],
    skipped_files: list[SkippedSitemapFile],
    invalid_document_found: bool,
) -> SitemapAnalysisStatus:
    if parsed_files and skipped_files:
        return SitemapAnalysisStatus.PARTIAL
    if invalid_document_found:
        return SitemapAnalysisStatus.INVALID
    if parsed_files:
        return SitemapAnalysisStatus.COMPLETE
    if any(
        (file.status_code is not None and 200 <= file.status_code < 300)
        or "analysis limit" in file.reason
        or "outside the audited domain" in file.reason
        for file in skipped_files
    ):
        return SitemapAnalysisStatus.PARTIAL
    return SitemapAnalysisStatus.UNAVAILABLE


def _loc_values(root: ElementTree.Element, sitemap_url: str) -> set[str]:
    urls: set[str] = set()
    for element in root.iter():
        if _local_name(element.tag) != "loc" or not element.text:
            continue
        normalized = normalize_url(element.text.strip(), base_url=sitemap_url)
        if normalized:
            urls.add(normalized)
    return urls


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1].lower()


def _unique_urls(urls: list[str]) -> list[str]:
    unique: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized and normalized not in unique:
            unique.append(normalized)
    return unique


def _fetch_failure_reason(resource: object) -> str:
    error = getattr(resource, "error", None)
    if error:
        return f"Skipped because the resource could not be read: {error}"
    status_code = getattr(resource, "status_code", None)
    return f"Skipped because the server returned HTTP {status_code}."


def _http_error(status_code: int | None) -> str | None:
    return f"HTTP {status_code}" if status_code is not None else None
