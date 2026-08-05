"""HTML-to-model extraction for server-rendered pages."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment

from .models import ContentBlock, CrawledPage, FreshnessSignal, Heading
from .url_utils import is_ignored_link, is_same_domain, normalize_url


WHITESPACE_PATTERN = re.compile(r"\s+")


def parse_html_page(
    *,
    requested_url: str,
    final_url: str,
    status_code: int,
    content_type: str | None,
    html: str,
    redirect_chain: list[str] | None = None,
) -> CrawledPage:
    """Extract audit-relevant page information without failing on bad markup."""

    parse_warnings: list[str] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as error:  # BeautifulSoup errors are uncommon but recoverable.
        parse_warnings.append(f"HTML parsing failed: {error}")
        return CrawledPage(
            requested_url=requested_url,
            url=final_url,
            status_code=status_code,
            redirect_chain=redirect_chain or [],
            content_type=content_type,
            parse_warnings=parse_warnings,
            fetched_at=datetime.now(timezone.utc),
        )

    title = _text_or_none(soup.title)
    meta_description = _meta_description(soup)
    headings = _extract_headings(soup)
    canonical_url = _canonical_url(soup, final_url)
    robots_meta = _robots_meta(soup)
    json_ld = _json_ld(soup, parse_warnings)
    internal_links, external_links = _extract_links(soup, final_url)
    content_soup = _content_soup(soup)
    content_blocks = _extract_content_blocks(content_soup, final_url)
    text_content = _visible_text(content_soup)
    freshness_signals = _extract_freshness_signals(soup, content_soup, json_ld)

    return CrawledPage(
        requested_url=requested_url,
        url=final_url,
        status_code=status_code,
        redirect_chain=redirect_chain or [],
        content_type=content_type,
        title=title,
        meta_description=meta_description,
        headings=headings,
        content_blocks=content_blocks,
        text_content=text_content,
        canonical_url=canonical_url,
        robots_meta=robots_meta,
        json_ld=json_ld,
        internal_links=internal_links,
        external_links=external_links,
        freshness_signals=freshness_signals,
        parse_warnings=parse_warnings,
        fetched_at=datetime.now(timezone.utc),
    )


def _text_or_none(element: Any) -> str | None:
    if not element:
        return None
    text = _clean_text(element.get_text(" ", strip=True))
    return text or None


def _meta_description(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    if not meta:
        return None
    content = meta.get("content")
    return _clean_text(content) if content else None


def _extract_headings(soup: BeautifulSoup) -> list[Heading]:
    headings: list[Heading] = []
    for element in soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE)):
        text = _clean_text(element.get_text(" ", strip=True))
        if text:
            headings.append(Heading(level=int(element.name[1]), text=text))
    return headings


def _canonical_url(soup: BeautifulSoup, page_url: str) -> str | None:
    for link in soup.find_all("link", href=True):
        relation = link.get("rel", [])
        rel_values = relation.split() if isinstance(relation, str) else relation
        if any(str(value).lower() == "canonical" for value in rel_values):
            return normalize_url(str(link["href"]), base_url=page_url)
    return None


def _robots_meta(soup: BeautifulSoup) -> dict[str, str]:
    directives: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        name = str(meta.get("name", "")).strip().lower()
        content = str(meta.get("content", "")).strip()
        if name and content and (name == "robots" or name.endswith("bot")):
            directives[name] = content
    return directives


def _json_ld(soup: BeautifulSoup, warnings: list[str]) -> list[Any]:
    entries: list[Any] = []
    for index, script in enumerate(soup.find_all("script"), start=1):
        script_type = str(script.get("type", "")).lower()
        if "application/ld+json" not in script_type:
            continue
        raw_json = script.string or script.get_text()
        if not raw_json or not raw_json.strip():
            warnings.append(f"JSON-LD script {index} was empty.")
            continue
        try:
            entries.append(json.loads(raw_json.strip()))
        except json.JSONDecodeError as error:
            warnings.append(f"JSON-LD script {index} could not be parsed: {error.msg}.")
    return entries


def _extract_links(soup: BeautifulSoup, page_url: str) -> tuple[list[str], list[str]]:
    internal_links: set[str] = set()
    external_links: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if is_ignored_link(href, page_url):
            continue
        absolute_url = normalize_url(href, base_url=page_url)
        if not absolute_url:
            continue
        if is_same_domain(absolute_url, page_url):
            internal_links.add(absolute_url)
        else:
            external_links.add(absolute_url)

    return sorted(internal_links), sorted(external_links)


def _content_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """Return a copy with non-visible and non-content elements removed."""

    content_soup = BeautifulSoup(str(soup), "html.parser")
    for element in content_soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        element.decompose()
    for comment in content_soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    return content_soup


def _extract_content_blocks(soup: BeautifulSoup, page_url: str) -> list[ContentBlock]:
    """Preserve paragraphs, headings, lists, and tables for local structural checks."""

    blocks: list[ContentBlock] = []
    root = soup.body or soup
    for element in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        text = _clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        tag_name = str(element.name).lower()
        kind = "heading" if tag_name.startswith("h") else "paragraph"
        if tag_name == "li":
            kind = "list_item"
        elif tag_name == "table":
            kind = "table"
        heading_level = int(tag_name[1]) if kind == "heading" else None
        blocks.append(
            ContentBlock(
                kind=kind,
                text=text,
                heading_level=heading_level,
                links=_element_links(element, page_url),
            )
        )
    return blocks


def _element_links(element: Any, page_url: str) -> list[str]:
    links: set[str] = set()
    for anchor in element.find_all("a", href=True):
        href = str(anchor["href"])
        if is_ignored_link(href, page_url):
            continue
        normalized = normalize_url(href, base_url=page_url)
        if normalized:
            links.add(normalized)
    return sorted(links)


def _extract_freshness_signals(
    soup: BeautifulSoup,
    content_soup: BeautifulSoup,
    json_ld: list[Any],
) -> list[FreshnessSignal]:
    """Collect explicit date signals without making a recency judgment."""

    signals: list[FreshnessSignal] = []
    seen: set[tuple[str, str, str]] = set()

    def add(value: str, source_type: str, evidence: str) -> None:
        normalized_value = _clean_text(value)
        key = (normalized_value, source_type, evidence)
        if normalized_value and key not in seen:
            seen.add(key)
            signals.append(
                FreshnessSignal(
                    value=normalized_value,
                    source_type=source_type,
                    evidence=evidence,
                )
            )

    for element in content_soup.find_all("time"):
        value = str(element.get("datetime") or element.get_text(" ", strip=True))
        add(value, "HTML time element", str(element))

    date_meta_names = {
        "article:published_time",
        "article:modified_time",
        "date",
        "datecreated",
        "datemodified",
        "datepublished",
        "last-modified",
        "last_updated",
        "updated",
    }
    for meta in soup.find_all("meta"):
        name = str(meta.get("name") or meta.get("property") or "").strip().lower()
        content = str(meta.get("content") or "").strip()
        if name in date_meta_names and content:
            add(content, f"meta {name}", str(meta))

    for key, value in _json_items(json_ld):
        normalized_key = key.lower().replace("_", "")
        if normalized_key in {"datepublished", "datemodified", "datecreated", "copyrightyear"}:
            add(str(value), f"JSON-LD {key}", f"{key}: {value}")

    visible_text = content_soup.get_text(" ", strip=True)
    for match in re.finditer(r"(?:©|copyright)\s*(\d{4}(?:\s*[-–]\s*\d{4})?)", visible_text, re.I):
        add(match.group(1), "copyright notice", match.group(0))
    return signals


def _json_items(value: Any) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, nested_value in value.items():
            items.append((str(key), nested_value))
            items.extend(_json_items(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            items.extend(_json_items(nested_value))
    return items


def _visible_text(content_soup: BeautifulSoup) -> str:
    """Return normalized user-visible text from an already-cleaned document."""

    return _clean_text(content_soup.get_text(" ", strip=True))


def _clean_text(value: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", value).strip()
