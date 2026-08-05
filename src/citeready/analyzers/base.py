"""Small shared interfaces and helpers for discoverability analyzers."""

from __future__ import annotations

from collections.abc import Callable

from ..models import Evidence, ResourceFetch


TextResourceFetcher = Callable[[str], ResourceFetch]


def resource_evidence(resource: ResourceFetch, source_type: str) -> Evidence:
    """Create concise, factual evidence for a fetched well-known resource."""

    if resource.error:
        exact_text = f"Request error: {resource.error}"
    elif resource.status_code is not None:
        exact_text = f"HTTP {resource.status_code}"
    else:
        exact_text = "No HTTP response was received."
    return Evidence(
        page_url=resource.final_url or resource.requested_url,
        exact_text=exact_text,
        source_type=source_type,
    )


def is_successful(resource: ResourceFetch) -> bool:
    """Return whether a fetch completed with a successful HTTP status."""

    return resource.error is None and resource.status_code is not None and 200 <= resource.status_code < 300
