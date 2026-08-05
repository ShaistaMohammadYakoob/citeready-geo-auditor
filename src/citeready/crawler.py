"""Polite, same-domain, server-rendered HTML crawler."""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

import requests

from .analyzers import AnswerabilityAnalyzer, CitationReadinessAnalyzer, DiscoverabilityEngine, EntityTrustAnalyzer
from .config import CrawlerSettings
from .models import CrawlResult, CrawlWarning, CrawledPage, ResourceFetch
from .parser import parse_html_page
from .scoring import GeoScoringEngine
from .url_utils import is_same_domain, link_priority, normalize_url


HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass(slots=True)
class FetchedResponse:
    """The bounded portion of an HTTP response needed by the parser."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    body: bytes
    redirect_chain: list[str]


class SiteCrawler:
    """Crawl a small, high-value subset of one website without raising on errors."""

    def __init__(self, settings: CrawlerSettings | None = None) -> None:
        self.settings = settings or CrawlerSettings()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
            }
        )

    def crawl(
        self,
        site_url: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> CrawlResult:
        """Return parsed pages and warnings for one normalized website URL.

        Individual request, redirect, HTTP-status, content-type, and parsing
        problems are recorded as warnings so an audit can still be produced.
        """

        normalized_start = normalize_url(site_url)
        if not normalized_start:
            raise ValueError("Enter a valid public HTTP or HTTPS URL.")

        started_at = datetime.now(timezone.utc)
        warnings: list[CrawlWarning] = []
        pages: list[CrawledPage] = []
        queue: list[tuple[int, int, str]] = []
        sequence = itertools.count()
        scheduled_urls: set[str] = set()
        attempted_urls: set[str] = set()
        final_urls: set[str] = set()
        analyzed_url = normalized_start

        self._schedule(queue, sequence, scheduled_urls, normalized_start, normalized_start)
        self._notify_progress(progress_callback, "crawl_started")

        while queue and len(pages) < self.settings.max_pages:
            _, _, candidate_url = heapq.heappop(queue)
            if candidate_url in attempted_urls:
                continue
            if pages and not is_same_domain(candidate_url, analyzed_url):
                continue
            attempted_urls.add(candidate_url)

            fetched = self._fetch(candidate_url, warnings)
            if not fetched:
                continue

            final_url = normalize_url(fetched.final_url)
            if not final_url:
                warnings.append(
                    CrawlWarning(
                        code="invalid_redirect_url",
                        message="The server redirected to an invalid URL; the page was skipped.",
                        url=candidate_url,
                    )
                )
                continue

            if not pages:
                analyzed_url = final_url
                if not is_same_domain(candidate_url, analyzed_url):
                    warnings.append(
                        CrawlWarning(
                            code="initial_redirect_domain_changed",
                            message=(
                                "The supplied URL redirected to a different domain. "
                                "The crawl continues on the final website domain."
                            ),
                            url=final_url,
                        )
                    )
            elif not is_same_domain(final_url, analyzed_url):
                warnings.append(
                    CrawlWarning(
                        code="external_redirect_skipped",
                        message="An internal link redirected outside the audited domain and was skipped.",
                        url=final_url,
                    )
                )
                continue

            if final_url in final_urls:
                warnings.append(
                    CrawlWarning(
                        code="duplicate_redirect_skipped",
                        message="A URL redirected to a page that had already been crawled.",
                        url=candidate_url,
                    )
                )
                continue

            scheduled_urls.add(final_url)
            page = parse_html_page(
                requested_url=fetched.requested_url,
                final_url=final_url,
                status_code=fetched.status_code,
                content_type=fetched.content_type,
                html=self._decode_body(fetched.body, fetched.content_type),
                redirect_chain=fetched.redirect_chain,
            )
            pages.append(page)
            final_urls.add(final_url)

            for link in page.internal_links:
                if is_same_domain(link, analyzed_url):
                    self._schedule(queue, sequence, scheduled_urls, link, analyzed_url)

        if queue and len(pages) == self.settings.max_pages:
            warnings.append(
                CrawlWarning(
                    code="page_limit_reached",
                    message=f"Crawl stopped after the configured limit of {self.settings.max_pages} pages.",
                    url=analyzed_url,
                )
            )

        self._notify_progress(progress_callback, "crawl_completed")

        try:
            discoverability = DiscoverabilityEngine().analyze(
                analyzed_url,
                pages,
                lambda resource_url: self._fetch_text_resource(
                    resource_url,
                    analyzed_url,
                    warnings,
                ),
                progress_callback=progress_callback,
            )
        except Exception as error:  # Keep a partial crawl usable if a later analyzer regresses.
            warnings.append(
                CrawlWarning(
                    code="discoverability_analysis_failed",
                    message=f"Discoverability analysis could not complete: {error}",
                    url=analyzed_url,
                )
            )
            discoverability = None

        try:
            citation_readiness = CitationReadinessAnalyzer().analyze(pages)
            self._notify_progress(progress_callback, "citation_readiness_completed")
        except Exception as error:  # Preserve a useful crawl if citation analysis encounters malformed data.
            warnings.append(
                CrawlWarning(
                    code="citation_readiness_analysis_failed",
                    message=f"Citation Readiness analysis could not complete: {error}",
                    url=analyzed_url,
                )
            )
            citation_readiness = None

        try:
            entity_trust = EntityTrustAnalyzer().analyze(analyzed_url, pages, warnings)
            self._notify_progress(progress_callback, "entity_trust_completed")
        except Exception as error:  # Keep the crawl useful if entity/trust analysis encounters malformed data.
            warnings.append(
                CrawlWarning(
                    code="entity_trust_analysis_failed",
                    message=f"Entity and Trust analysis could not complete: {error}",
                    url=analyzed_url,
                )
            )
            entity_trust = None

        try:
            answerability = AnswerabilityAnalyzer().analyze(pages, entity_trust, analyzed_url)
            self._notify_progress(progress_callback, "answerability_completed")
        except Exception as error:  # Preserve a usable crawl if answerability analysis encounters malformed data.
            warnings.append(
                CrawlWarning(
                    code="answerability_analysis_failed",
                    message=f"AI Answerability analysis could not complete: {error}",
                    url=analyzed_url,
                )
            )
            answerability = None

        crawl_result = CrawlResult(
            requested_url=normalized_start,
            analyzed_url=analyzed_url,
            pages=pages,
            warnings=warnings,
            discoverability=discoverability,
            citation_readiness=citation_readiness,
            entity_trust=entity_trust,
            answerability=answerability,
            max_pages=self.settings.max_pages,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )
        try:
            scored_result = crawl_result.model_copy(
                update={"scoring": GeoScoringEngine().score(crawl_result)}
            )
            self._notify_progress(progress_callback, "scoring_completed")
            return scored_result
        except Exception as error:  # A scoring regression must never hide usable analysis output.
            warnings.append(
                CrawlWarning(
                    code="scoring_analysis_failed",
                    message=f"Transparent GEO scoring could not complete: {error}",
                    url=analyzed_url,
                )
            )
            return crawl_result.model_copy(update={"warnings": warnings})

    @staticmethod
    def _notify_progress(callback: Callable[[str], None] | None, event: str) -> None:
        """Inform optional presentation layers about completed work safely."""

        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            return

    def _schedule(
        self,
        queue: list[tuple[int, int, str]],
        sequence: Iterator[int],
        scheduled_urls: set[str],
        url: str,
        site_url: str,
    ) -> None:
        normalized = normalize_url(url)
        if not normalized or normalized in scheduled_urls:
            return
        scheduled_urls.add(normalized)
        heapq.heappush(queue, (-link_priority(normalized, site_url), next(sequence), normalized))

    def _fetch(self, url: str, warnings: list[CrawlWarning]) -> FetchedResponse | None:
        try:
            response = self.session.get(
                url,
                timeout=(5, self.settings.timeout_seconds),
                allow_redirects=True,
                stream=True,
            )
        except requests.RequestException as error:
            warnings.append(CrawlWarning(code="request_failed", message=str(error), url=url))
            return None

        try:
            final_url = response.url
            redirect_chain = [item.url for item in response.history]
            content_type = response.headers.get("Content-Type")

            if not 200 <= response.status_code < 300:
                warnings.append(
                    CrawlWarning(
                        code="http_status_skipped",
                        message=f"Received HTTP {response.status_code}; the page was skipped.",
                        url=final_url,
                    )
                )
                return None

            declared_length = _content_length(response.headers.get("Content-Length"))
            if declared_length is not None and declared_length > self.settings.max_response_bytes:
                warnings.append(
                    CrawlWarning(
                        code="response_too_large",
                        message=(
                            f"Response exceeds the {self.settings.max_response_bytes:,}-byte safety limit "
                            "and was skipped."
                        ),
                        url=final_url,
                    )
                )
                return None

            body = self._read_bounded_body(response, final_url, warnings)
            if body is None:
                return None
            if not _is_html_response(content_type, body):
                warnings.append(
                    CrawlWarning(
                        code="non_html_skipped",
                        message="The response was not HTML and was skipped.",
                        url=final_url,
                    )
                )
                return None

            return FetchedResponse(
                requested_url=url,
                final_url=final_url,
                status_code=response.status_code,
                content_type=content_type,
                body=body,
                redirect_chain=redirect_chain,
            )
        except requests.RequestException as error:
            warnings.append(CrawlWarning(code="response_read_failed", message=str(error), url=url))
            return None
        finally:
            response.close()

    def _read_bounded_body(
        self,
        response: requests.Response,
        final_url: str,
        warnings: list[CrawlWarning],
    ) -> bytes | None:
        chunks: list[bytes] = []
        bytes_read = 0
        try:
            for chunk in response.iter_content(chunk_size=16_384):
                if not chunk:
                    continue
                bytes_read += len(chunk)
                if bytes_read > self.settings.max_response_bytes:
                    warnings.append(
                        CrawlWarning(
                            code="response_too_large",
                            message=(
                                f"Response exceeded the {self.settings.max_response_bytes:,}-byte safety limit "
                                "while downloading and was skipped."
                            ),
                            url=final_url,
                        )
                    )
                    return None
                chunks.append(chunk)
        except requests.RequestException as error:
            warnings.append(CrawlWarning(code="response_read_failed", message=str(error), url=final_url))
            return None
        return b"".join(chunks)

    def _fetch_text_resource(
        self,
        url: str,
        site_url: str,
        warnings: list[CrawlWarning],
    ) -> ResourceFetch:
        """Fetch a small same-domain text resource for a discoverability analyzer."""

        normalized_url = normalize_url(url)
        if not normalized_url or not is_same_domain(normalized_url, site_url):
            message = "The requested resource is outside the audited domain and was not fetched."
            warnings.append(CrawlWarning(code="resource_external_skipped", message=message, url=url))
            return ResourceFetch(requested_url=url, error=message)
        url = normalized_url

        try:
            response = self.session.get(
                url,
                timeout=(5, self.settings.timeout_seconds),
                allow_redirects=True,
                stream=True,
            )
        except requests.RequestException as error:
            warnings.append(CrawlWarning(code="resource_request_failed", message=str(error), url=url))
            return ResourceFetch(requested_url=url, error=str(error))

        try:
            final_url = normalize_url(response.url)
            redirect_chain = [item.url for item in response.history]
            content_type = response.headers.get("Content-Type")
            if not final_url:
                message = "The resource redirected to an invalid URL."
                warnings.append(CrawlWarning(code="resource_redirect_invalid", message=message, url=url))
                return ResourceFetch(
                    requested_url=url,
                    status_code=response.status_code,
                    content_type=content_type,
                    redirect_chain=redirect_chain,
                    error=message,
                )
            if not is_same_domain(final_url, site_url):
                message = "The resource redirected outside the audited domain."
                warnings.append(
                    CrawlWarning(code="resource_redirect_external", message=message, url=final_url)
                )
                return ResourceFetch(
                    requested_url=url,
                    final_url=final_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    redirect_chain=redirect_chain,
                    error=message,
                )
            if not 200 <= response.status_code < 300:
                return ResourceFetch(
                    requested_url=url,
                    final_url=final_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    redirect_chain=redirect_chain,
                )

            declared_length = _content_length(response.headers.get("Content-Length"))
            if declared_length is not None and declared_length > self.settings.max_response_bytes:
                message = (
                    f"Response exceeds the {self.settings.max_response_bytes:,}-byte safety limit."
                )
                warnings.append(CrawlWarning(code="resource_too_large", message=message, url=final_url))
                return ResourceFetch(
                    requested_url=url,
                    final_url=final_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    redirect_chain=redirect_chain,
                    error=message,
                )

            body, read_error = self._read_text_resource_body(response)
            if body is None:
                message = read_error or "Response could not be read."
                warning_code = (
                    "resource_too_large" if "safety limit" in message else "resource_read_failed"
                )
                warnings.append(CrawlWarning(code=warning_code, message=message, url=final_url))
                return ResourceFetch(
                    requested_url=url,
                    final_url=final_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    redirect_chain=redirect_chain,
                    error=message,
                )
            return ResourceFetch(
                requested_url=url,
                final_url=final_url,
                status_code=response.status_code,
                content_type=content_type,
                text=self._decode_body(body, content_type),
                redirect_chain=redirect_chain,
            )
        except requests.RequestException as error:
            warnings.append(CrawlWarning(code="resource_read_failed", message=str(error), url=url))
            return ResourceFetch(requested_url=url, error=str(error))
        finally:
            response.close()

    def _read_text_resource_body(self, response: requests.Response) -> tuple[bytes | None, str | None]:
        """Read a well-known text resource without relaxing the response-size limit."""

        chunks: list[bytes] = []
        bytes_read = 0
        try:
            for chunk in response.iter_content(chunk_size=16_384):
                if not chunk:
                    continue
                bytes_read += len(chunk)
                if bytes_read > self.settings.max_response_bytes:
                    return (
                        None,
                        (
                            f"Response exceeded the {self.settings.max_response_bytes:,}-byte safety "
                            "limit while downloading."
                        ),
                    )
                chunks.append(chunk)
        except requests.RequestException as error:
            return None, str(error)
        return b"".join(chunks), None

    @staticmethod
    def _decode_body(body: bytes, content_type: str | None) -> str:
        charset = _charset_from_content_type(content_type) or "utf-8"
        try:
            return body.decode(charset, errors="replace")
        except LookupError:
            return body.decode("utf-8", errors="replace")


def _content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _is_html_response(content_type: str | None, body: bytes) -> bool:
    if content_type and any(content_type.lower().startswith(kind) for kind in HTML_CONTENT_TYPES):
        return True
    sample = body[:512].lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html")


def _charset_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    for segment in content_type.split(";")[1:]:
        name, separator, value = segment.strip().partition("=")
        if separator and name.lower() == "charset":
            return value.strip(' "')
    return None
