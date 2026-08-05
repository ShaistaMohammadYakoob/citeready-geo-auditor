"""URL normalization and link-filtering helpers for safe bounded crawling."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


IGNORED_SCHEMES = {"data", "file", "javascript", "mailto", "sms", "tel"}
TRACKING_PARAMETER_PREFIXES = ("utm_",)
TRACKING_PARAMETERS = {"_ga", "_gl", "dclid", "fbclid", "gclid", "mc_cid", "mc_eid"}
IGNORED_EXTENSIONS = {
    ".7z", ".avi", ".bmp", ".csv", ".doc", ".docx", ".eps", ".gif", ".gz",
    ".ico", ".jpeg", ".jpg", ".js", ".m4a", ".mov", ".mp3", ".mp4", ".mpeg",
    ".pdf", ".png", ".ppt", ".pptx", ".rar", ".rss", ".svg", ".tar", ".tif",
    ".tiff", ".txt", ".wav", ".webm", ".webp", ".xls", ".xlsx", ".xml", ".zip",
}

PRIORITY_KEYWORDS = {
    "about": 900,
    "service": 880,
    "solution": 870,
    "product": 860,
    "pricing": 850,
    "price": 850,
    "faq": 840,
    "contact": 830,
    "blog": 700,
    "article": 680,
    "resource": 660,
}


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """Return a canonical crawl URL, or ``None`` for an unsafe/invalid URL.

    Fragments, credentials, default ports, and known tracking parameters are
    removed so equivalent links are not crawled repeatedly.
    """

    candidate = url.strip()
    if not candidate or candidate.startswith("#"):
        return None

    if base_url:
        candidate = urljoin(base_url, candidate)
    elif candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif "://" not in candidate:
        candidate = f"https://{candidate}"

    try:
        parts = urlsplit(candidate)
        scheme = parts.scheme.lower()
        if scheme in IGNORED_SCHEMES or scheme not in {"http", "https"}:
            return None
        if not parts.hostname or parts.username or parts.password:
            return None

        hostname = parts.hostname.lower().rstrip(".")
        port = parts.port
    except ValueError:
        return None

    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"[{hostname}]" if ":" in hostname else hostname
        netloc = f"{host}:{port}"
    else:
        netloc = f"[{hostname}]" if ":" in hostname else hostname

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_parameter(key)
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def is_ignored_link(href: str, base_url: str) -> bool:
    """Return whether a link should never be scheduled for an HTML crawl."""

    raw_link = href.strip()
    if not raw_link or raw_link.startswith("#"):
        return True

    parsed = urlsplit(raw_link)
    if parsed.scheme.lower() in IGNORED_SCHEMES:
        return True

    absolute = urljoin(base_url, raw_link)
    path = urlsplit(absolute).path.lower()
    return any(path.endswith(extension) for extension in IGNORED_EXTENSIONS)


def is_same_domain(candidate_url: str, site_url: str) -> bool:
    """Treat an exact host and its ``www`` mirror as the same audited site."""

    candidate_host = _host_key(candidate_url)
    site_host = _host_key(site_url)
    return bool(candidate_host and site_host and candidate_host == site_host)


def link_priority(url: str, site_url: str) -> int:
    """Rank likely high-value audit pages ahead of arbitrary internal links."""

    if normalize_url(url) == normalize_url(site_url):
        return 1_000

    haystack = f"{urlsplit(url).path} {urlsplit(url).query}".lower()
    return max((score for keyword, score in PRIORITY_KEYWORDS.items() if keyword in haystack), default=100)


def _is_tracking_parameter(key: str) -> bool:
    normalized = key.lower()
    return normalized in TRACKING_PARAMETERS or normalized.startswith(TRACKING_PARAMETER_PREFIXES)


def _host_key(url: str) -> str | None:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.lower().rstrip(".").removeprefix("www.")
