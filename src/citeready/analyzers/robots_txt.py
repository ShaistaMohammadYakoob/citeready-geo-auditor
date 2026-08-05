"""robots.txt availability and bot-access analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from ..models import (
    BotAccess,
    BotAccessResult,
    DiscoverabilityFinding,
    Evidence,
    ResourceFetch,
    RobotsTxtAnalysis,
    Severity,
)
from .base import TextResourceFetcher, is_successful, resource_evidence


AUDITED_BOTS = ("GPTBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Googlebot")


@dataclass(frozen=True, slots=True)
class RobotsGroup:
    """One parsed user-agent group from a robots.txt document."""

    user_agents: tuple[str, ...]
    rules: tuple[tuple[str, str], ...]


class RobotsTxtAnalyzer:
    """Inspect robots.txt without inferring anything when the file is unavailable."""

    def analyze(self, site_url: str, fetch: TextResourceFetcher) -> RobotsTxtAnalysis:
        """Return effective root-path access for the GEO-relevant bot set."""

        robots_url = urljoin(site_url, "/robots.txt")
        resource = fetch(robots_url)
        if not is_successful(resource):
            return RobotsTxtAnalysis(
                url=robots_url,
                found=False,
                status_code=resource.status_code,
                bot_access=[self._unknown_bot(bot, resource) for bot in AUDITED_BOTS],
                findings=[self._unavailable_finding(robots_url, resource)],
            )

        groups, sitemap_urls = _parse_robots(resource.text or "", robots_url)
        bot_access = [self._evaluate_bot(bot, groups, resource) for bot in AUDITED_BOTS]
        findings = [
            self._blocked_bot_finding(result, robots_url)
            for result in bot_access
            if result.access == BotAccess.BLOCKED
        ]
        return RobotsTxtAnalysis(
            url=robots_url,
            found=True,
            status_code=resource.status_code,
            bot_access=bot_access,
            sitemap_urls=sitemap_urls,
            findings=findings,
        )

    @staticmethod
    def _unknown_bot(bot_name: str, resource: ResourceFetch) -> BotAccessResult:
        return BotAccessResult(
            bot_name=bot_name,
            access=BotAccess.UNKNOWN,
            evidence=[resource_evidence(resource, "robots.txt")],
        )

    def _evaluate_bot(
        self,
        bot_name: str,
        groups: list[RobotsGroup],
        resource: ResourceFetch,
    ) -> BotAccessResult:
        matching_groups = _matching_groups(bot_name, groups)
        rules = [rule for group in matching_groups for rule in group.rules]
        matching_rules = [rule for rule in rules if _matches_path(rule[1], "/")]

        if not matching_rules:
            evidence_text = "No matching Allow or Disallow directive applies to /."
            return BotAccessResult(
                bot_name=bot_name,
                access=BotAccess.ALLOWED,
                directives=[f"{name.title()}: {path}" for name, path in rules],
                evidence=[
                    Evidence(
                        page_url=resource.final_url or resource.requested_url,
                        exact_text=evidence_text,
                        source_type="robots.txt",
                    )
                ],
            )

        longest_match = max(len(path.rstrip("$")) for _, path in matching_rules)
        strongest_rules = [
            rule for rule in matching_rules if len(rule[1].rstrip("$")) == longest_match
        ]
        is_allowed = any(name == "allow" for name, _ in strongest_rules)
        selected = [f"{name.title()}: {path}" for name, path in strongest_rules]
        return BotAccessResult(
            bot_name=bot_name,
            access=BotAccess.ALLOWED if is_allowed else BotAccess.BLOCKED,
            is_explicit_rule=True,
            directives=[f"{name.title()}: {path}" for name, path in rules],
            evidence=[
                Evidence(
                    page_url=resource.final_url or resource.requested_url,
                    exact_text="; ".join(selected),
                    source_type="robots.txt",
                )
            ],
        )

    @staticmethod
    def _unavailable_finding(robots_url: str, resource: ResourceFetch) -> DiscoverabilityFinding:
        missing = resource.status_code == 404 and resource.error is None
        return DiscoverabilityFinding(
            title="robots.txt is missing" if missing else "robots.txt could not be retrieved",
            severity=Severity.MEDIUM,
            evidence=[resource_evidence(resource, "robots.txt")],
            affected_url=robots_url,
            why_it_matters=(
                "A robots.txt file is the standard place to publish crawler guidance and a sitemap "
                "location. Without a retrievable file, bot-specific access cannot be verified."
            ),
            recommended_fix="Publish a valid robots.txt file at the site root and include the sitemap URL.",
            copy_paste_fix=(
                "User-agent: *\nAllow: /\n\n"
                f"Sitemap: {urljoin(robots_url, '/sitemap.xml')}"
            ),
        )

    @staticmethod
    def _blocked_bot_finding(
        access_result: BotAccessResult,
        robots_url: str,
    ) -> DiscoverabilityFinding:
        bot_name = access_result.bot_name
        return DiscoverabilityFinding(
            title=f"{bot_name} is blocked by robots.txt",
            severity=Severity.MEDIUM,
            evidence=access_result.evidence,
            affected_url=robots_url,
            why_it_matters=(
                f"{bot_name} is instructed not to crawl the site root, which can prevent it from "
                "discovering eligible content."
            ),
            recommended_fix=(
                f"Remove or narrow the site-wide Disallow directive for {bot_name} if this bot should "
                "be able to discover your public pages."
            ),
            copy_paste_fix=f"User-agent: {bot_name}\nAllow: /",
        )


def _parse_robots(text: str, robots_url: str) -> tuple[list[RobotsGroup], list[str]]:
    """Parse the relevant RFC-style robots directives while tolerating bad lines."""

    groups: list[RobotsGroup] = []
    current_agents: list[str] = []
    current_rules: list[tuple[str, str]] = []
    sitemap_urls: list[str] = []

    def finish_group() -> None:
        if current_agents:
            groups.append(RobotsGroup(tuple(current_agents), tuple(current_rules)))

    for raw_line in text.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line or ":" not in line:
            continue
        directive, value = (part.strip() for part in line.split(":", maxsplit=1))
        directive = directive.lower()
        if directive == "user-agent":
            if current_rules:
                finish_group()
                current_agents = []
                current_rules = []
            if value:
                current_agents.append(value.lower())
        elif directive in {"allow", "disallow"} and current_agents:
            current_rules.append((directive, value))
        elif directive == "sitemap" and value:
            sitemap_url = urljoin(robots_url, value)
            if sitemap_url not in sitemap_urls:
                sitemap_urls.append(sitemap_url)
    finish_group()
    return groups, sitemap_urls


def _matching_groups(bot_name: str, groups: list[RobotsGroup]) -> list[RobotsGroup]:
    normalized_bot = bot_name.lower()
    exact_groups = [
        group for group in groups if normalized_bot in {agent.lower() for agent in group.user_agents}
    ]
    return exact_groups or [group for group in groups if "*" in group.user_agents]


def _matches_path(pattern: str, path: str) -> bool:
    if not pattern:
        return False
    anchored = pattern.endswith("$")
    token = pattern[:-1] if anchored else pattern
    expression = re.escape(token).replace(r"\*", ".*")
    expression = f"^{expression}" + ("$" if anchored else "")
    return re.match(expression, path) is not None
