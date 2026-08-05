"""HTML-to-model extraction for server-rendered pages."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment

from .models import CallToActionSignal, ContentBlock, CrawledPage, ExternalLinkSignal, FreshnessSignal, Heading
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
    open_graph = _open_graph(soup)
    headings = _extract_headings(soup)
    canonical_url = _canonical_url(soup, final_url)
    robots_meta = _robots_meta(soup)
    json_ld = _json_ld(soup, parse_warnings)
    internal_links, external_links = _extract_links(soup, final_url)
    external_link_signals = _external_link_signals(soup, final_url)
    content_soup = _content_soup(soup)
    content_blocks = _extract_content_blocks(content_soup, final_url)
    text_content = _visible_text(content_soup)
    footer_text = _footer_text(content_soup)
    visible_addresses = _visible_addresses(content_soup)
    image_alt_text = _image_alt_text(content_soup)
    has_contact_form = _has_contact_form(content_soup, final_url)
    author_links = _author_links(soup, final_url)
    call_to_action_signals = _call_to_action_signals(content_soup, final_url)
    call_to_action_labels = [signal.label for signal in call_to_action_signals]
    freshness_signals = _extract_freshness_signals(soup, content_soup, json_ld)

    return CrawledPage(
        requested_url=requested_url,
        url=final_url,
        status_code=status_code,
        redirect_chain=redirect_chain or [],
        content_type=content_type,
        title=title,
        meta_description=meta_description,
        open_graph=open_graph,
        headings=headings,
        content_blocks=content_blocks,
        text_content=text_content,
        footer_text=footer_text,
        visible_addresses=visible_addresses,
        image_alt_text=image_alt_text,
        has_contact_form=has_contact_form,
        author_links=author_links,
        call_to_action_labels=call_to_action_labels,
        call_to_action_signals=call_to_action_signals,
        canonical_url=canonical_url,
        robots_meta=robots_meta,
        json_ld=json_ld,
        internal_links=internal_links,
        external_links=external_links,
        external_link_signals=external_link_signals,
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


def _open_graph(soup: BeautifulSoup) -> dict[str, str]:
    """Return published Open Graph metadata without inferring missing values."""

    values: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        property_name = str(meta.get("property") or "").strip().lower()
        content = str(meta.get("content") or "").strip()
        if property_name.startswith("og:") and content and property_name not in values:
            values[property_name] = _clean_text(content)
    return values


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


def _external_link_signals(soup: BeautifulSoup, page_url: str) -> list[ExternalLinkSignal]:
    """Keep published link context for conservative entity-profile checks."""

    signals: list[ExternalLinkSignal] = []
    seen: set[tuple[str, str, tuple[str, ...], str | None, str | None, bool]] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        if is_ignored_link(href, page_url):
            continue
        url = normalize_url(href, base_url=page_url)
        if not url or is_same_domain(url, page_url):
            continue
        relation = anchor.get("rel", [])
        rel_values = relation.split() if isinstance(relation, str) else relation
        normalized_rel = sorted({str(value).lower() for value in rel_values if str(value).strip()})
        aria_label = _clean_text(str(anchor.get("aria-label") or "")) or None
        anchor_text = _clean_text(anchor.get_text(" ", strip=True))
        location, in_social_area = _link_location(anchor)
        key = (url, anchor_text, tuple(normalized_rel), aria_label, location, in_social_area)
        if key in seen:
            continue
        seen.add(key)
        signals.append(
            ExternalLinkSignal(
                url=url,
                anchor_text=anchor_text,
                rel_values=normalized_rel,
                aria_label=aria_label,
                location=location,
                in_social_area=in_social_area,
            )
        )
    return signals


def _link_location(anchor: Any) -> tuple[str | None, bool]:
    """Identify header/footer social-link regions without inferring link ownership."""

    ancestors = [anchor, *anchor.parents]
    location: str | None = None
    in_social_area = False
    for element in ancestors:
        if not getattr(element, "name", None):
            continue
        name = str(element.name).lower()
        if name in {"header", "footer"} and location is None:
            location = name
        attributes = " ".join(
            [
                str(element.get("id") or ""),
                " ".join(str(value) for value in element.get("class", [])),
                str(element.get("aria-label") or ""),
            ]
        ).lower()
        if "social" in attributes:
            in_social_area = True
    return location, in_social_area


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


def _footer_text(soup: BeautifulSoup) -> str:
    """Extract footer wording used for explicit copyright/entity checks."""

    return _clean_text(" ".join(footer.get_text(" ", strip=True) for footer in soup.find_all("footer")))


def _visible_addresses(soup: BeautifulSoup) -> list[str]:
    """Collect only explicitly marked-up visible postal addresses."""

    return _deduplicated_text(address.get_text(" ", strip=True) for address in soup.find_all("address"))


def _image_alt_text(soup: BeautifulSoup) -> list[str]:
    """Retain published image alt labels for conservative logo-signal detection."""

    return _deduplicated_text(str(image.get("alt") or "") for image in soup.find_all("img"))


def _has_contact_form(soup: BeautifulSoup, page_url: str) -> bool:
    """Detect a likely public contact form without treating every form as one."""

    for form in soup.find_all("form"):
        form_context = " ".join(
            [
                str(form.get("id") or ""),
                " ".join(str(value) for value in form.get("class", [])),
                str(form.get("action") or ""),
                form.get_text(" ", strip=True),
            ]
        ).lower()
        input_context = " ".join(
            str(element.get("name") or element.get("type") or "")
            for element in form.find_all(["input", "textarea", "select"])
        ).lower()
        if "contact" in form_context or "support" in form_context:
            return True
        if "contact" in page_url.lower() and ("email" in input_context or "message" in input_context):
            return True
    return False


def _author_links(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Collect explicit author-profile links for editorial attribution checks."""

    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        relation = anchor.get("rel", [])
        rel_values = relation.split() if isinstance(relation, str) else relation
        attributes = " ".join(
            [
                " ".join(str(value) for value in rel_values),
                str(anchor.get("class") or ""),
                str(anchor.get("id") or ""),
                str(anchor.get("href") or ""),
            ]
        ).lower()
        if "author" not in attributes:
            continue
        normalized = normalize_url(str(anchor["href"]), base_url=page_url)
        if normalized:
            links.append(normalized)
    return sorted(set(links))


def _call_to_action_signals(soup: BeautifulSoup, page_url: str) -> list[CallToActionSignal]:
    """Retain CTA labels and basic document placement without inferring visual design."""

    signals: list[CallToActionSignal] = []
    seen: set[tuple[str, str | None, str, str | None]] = set()
    for element in soup.find_all(["a", "button"]):
        text = _clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        target_url = None
        if element.name == "a" and element.get("href"):
            target_url = normalize_url(str(element.get("href")), base_url=page_url)
        location = _element_location(element)
        key = (text, target_url, str(element.name), location)
        if key in seen:
            continue
        seen.add(key)
        signals.append(
            CallToActionSignal(
                label=text,
                target_url=target_url,
                element_type=str(element.name),
                location=location,
                near_primary_heading=location in {None, "main"} and element.find_previous("h1") is not None,
            )
        )
    return signals


def _element_location(element: Any) -> str | None:
    for ancestor in [element, *element.parents]:
        name = str(getattr(ancestor, "name", "") or "").lower()
        if name in {"footer", "header", "nav", "main", "aside"}:
            return name
    return None


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


def _deduplicated_text(values: Iterable[str]) -> list[str]:
    """Normalize a short iterable of extracted text while preserving its order."""

    result: list[str] = []
    for value in values:
        text = _clean_text(str(value))
        if text and text not in result:
            result.append(text)
    return result
