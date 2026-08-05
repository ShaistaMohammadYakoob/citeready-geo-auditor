"""Environment-backed crawler settings."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


class CrawlerSettings(BaseModel):
    """Limits that keep a single audit polite and bounded."""

    model_config = ConfigDict(frozen=True)

    max_pages: int = Field(default=12, ge=1, le=12)
    timeout_seconds: float = Field(default=12.0, ge=1.0, le=60.0)
    max_response_bytes: int = Field(default=2_000_000, ge=50_000, le=10_000_000)
    user_agent: str = "CiteReady-GEO-Auditor/0.1 (+https://example.com/citeready)"


def load_crawler_settings() -> CrawlerSettings:
    """Load optional local settings without requiring a `.env` file."""

    load_dotenv()
    values: dict[str, object] = {}

    if value := os.getenv("CRAWL_MAX_PAGES"):
        values["max_pages"] = value
    if value := os.getenv("CRAWL_TIMEOUT_SECONDS"):
        values["timeout_seconds"] = value
    if value := os.getenv("CRAWL_MAX_RESPONSE_BYTES"):
        values["max_response_bytes"] = value
    if value := os.getenv("CRAWL_USER_AGENT"):
        values["user_agent"] = value

    return CrawlerSettings.model_validate(values)
