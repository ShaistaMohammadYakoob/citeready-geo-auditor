"""Offline coverage for deterministic Phase 4 Entity and Trust analysis."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from citeready.analyzers.entity_trust import EntityTrustAnalyzer
from citeready.cli import _print_entity_findings, main
from citeready.config import CrawlerSettings
from citeready.models import CrawlResult, CrawledPage, ExternalLinkSignal, FreshnessSignal, Heading
from citeready.parser import parse_html_page


SITE_URL = "https://acme.example/"
NOW = datetime.now(timezone.utc)


def words(count: int) -> str:
    return " ".join(f"word{index}" for index in range(count))


def organization_json(
    *,
    name: str = "Acme, Inc.",
    url: str = SITE_URL,
    same_as: list[str] | None = None,
) -> dict[str, object]:
    data: dict[str, object] = {"@context": "https://schema.org", "@type": "Organization", "name": name, "url": url}
    if same_as is not None:
        data["sameAs"] = same_as
    return data


def page(
    *,
    url: str = SITE_URL,
    title: str = "Acme",
    h1: str = "Acme",
    text: str = "Acme provides analytics for teams.",
    json_ld: list[object] | None = None,
    internal_links: list[str] | None = None,
    external_links: list[str] | None = None,
    external_link_signals: list[ExternalLinkSignal] | None = None,
    open_graph: dict[str, str] | None = None,
    footer_text: str = "",
    visible_addresses: list[str] | None = None,
    image_alt_text: list[str] | None = None,
    has_contact_form: bool = False,
    author_links: list[str] | None = None,
    freshness_signals: list[FreshnessSignal] | None = None,
) -> CrawledPage:
    return CrawledPage(
        requested_url=url,
        url=url,
        status_code=200,
        title=title,
        open_graph=open_graph or {},
        headings=[Heading(level=1, text=h1)],
        text_content=text,
        footer_text=footer_text,
        visible_addresses=visible_addresses or [],
        image_alt_text=image_alt_text or [],
        has_contact_form=has_contact_form,
        author_links=author_links or [],
        json_ld=json_ld or [],
        internal_links=internal_links or [],
        external_links=external_links or [],
        external_link_signals=external_link_signals or [],
        freshness_signals=freshness_signals or [],
        fetched_at=NOW,
    )


class EntityTrustAnalyzerTests(unittest.TestCase):
    """Test each required Phase 4 signal entirely from local page fixtures."""

    def setUp(self) -> None:
        self.analyzer = EntityTrustAnalyzer()

    def analyze(self, pages: list[CrawledPage]):
        return self.analyzer.analyze(SITE_URL, pages)

    def titles(self, pages: list[CrawledPage]) -> list[str]:
        return [finding.title for finding in self.analyze(pages).findings]

    def test_valid_organization_json_ld_is_extracted(self) -> None:
        result = self.analyze([page(json_ld=[organization_json(same_as=["https://www.linkedin.com/company/acme/"])])])

        self.assertEqual(result.organization_data[0].name, "Acme, Inc.")
        self.assertEqual(result.organization_data[0].url, SITE_URL)
        self.assertIn("https://www.linkedin.com/company/acme/", result.organization_data[0].same_as)
        self.assertNotIn("Organization-like structured data was not detected", [item.title for item in result.findings])

    def test_missing_organization_json_ld_is_flagged(self) -> None:
        self.assertIn("Organization-like structured data was not detected", self.titles([page()]))

    def test_malformed_json_ld_is_flagged_from_parser_evidence(self) -> None:
        parsed = parse_html_page(
            requested_url=SITE_URL,
            final_url=SITE_URL,
            status_code=200,
            content_type="text/html",
            html='<html><head><script type="application/ld+json">{"@type":</script></head><body><h1>Acme</h1></body></html>',
        )
        finding = next(item for item in self.analyze([parsed]).findings if item.title.startswith("Malformed JSON-LD"))

        self.assertIn("could not be parsed", finding.evidence[0].exact_text)

    def test_equivalent_company_names_are_not_flagged(self) -> None:
        equivalent = page(
            title="Acme, Inc.",
            h1="Acme LLC",
            open_graph={"og:site_name": "ACME Ltd."},
            json_ld=[organization_json(name="Acme Corporation", same_as=[])],
            footer_text="Copyright 2026 Acme Co.",
        )

        self.assertNotIn("Entity Consistency Risk", self.titles([equivalent]))

    def test_conflicting_company_names_are_flagged(self) -> None:
        conflicting = page(
            title="Beta Systems",
            h1="Beta Systems",
            open_graph={"og:site_name": "Beta Systems"},
            json_ld=[organization_json(name="Acme Analytics", same_as=[])],
        )
        finding = next(item for item in self.analyze([conflicting]).findings if item.title == "Entity Consistency Risk")

        self.assertIn("Source A", finding.evidence[0].exact_text)
        self.assertIn("Source B", finding.evidence[1].exact_text)

    def test_about_page_is_detected(self) -> None:
        about_url = "https://acme.example/about"
        result = self.analyze(
            [
                page(internal_links=[about_url]),
                page(url=about_url, title="About Acme", h1="About Acme", text=words(50)),
            ]
        )

        about = next(item for item in result.company_pages if item.page_type == "about")
        self.assertTrue(about.available)
        self.assertTrue(about.has_meaningful_text)

    def test_missing_about_page_is_flagged(self) -> None:
        self.assertIn("No About page was detected", self.titles([page()]))

    def test_contact_page_and_contact_form_are_detected(self) -> None:
        contact_url = "https://acme.example/contact"
        result = self.analyze(
            [
                page(internal_links=[contact_url]),
                page(
                    url=contact_url,
                    title="Contact Acme",
                    h1="Contact Acme",
                    text=words(50),
                    has_contact_form=True,
                ),
            ]
        )

        self.assertTrue(any(item.page_type == "contact" and item.available for item in result.company_pages))
        self.assertTrue(any(item.detail_type == "contact form" for item in result.contact_details))

    def test_conflicting_public_contact_details_are_flagged_without_exposure(self) -> None:
        contact_url = "https://acme.example/contact"
        finding = next(
            item
            for item in self.analyze(
                [
                    page(text="Email support@acme.example", internal_links=[contact_url]),
                    page(url=contact_url, title="Contact", h1="Contact", text="Email sales@acme.example"),
                ]
            ).findings
            if item.title == "Public organization contact details may be inconsistent"
        )

        rendered_evidence = " ".join(item.exact_text for item in finding.evidence)
        self.assertIn("s***@acme.example", rendered_evidence)
        self.assertNotIn("support@acme.example", rendered_evidence)

    def test_article_with_author_and_date_is_recorded(self) -> None:
        article_url = "https://acme.example/blog/entity-guide"
        article = page(
            url=article_url,
            title="Entity guide",
            h1="Entity guide",
            text=words(320),
            json_ld=[
                {
                    "@type": "Article",
                    "author": {"@type": "Person", "name": "Jane Doe", "jobTitle": "Editor"},
                }
            ],
            freshness_signals=[FreshnessSignal(value="2026-01-02", source_type="meta datePublished", evidence="datePublished")],
        )
        result = self.analyze([page(), article])
        signal = next(item for item in result.editorial_signals if item.page_url == article_url)

        self.assertIn("Jane Doe", signal.author_names)
        self.assertIn("2026-01-02", signal.publication_dates)
        self.assertNotIn("Substantial editorial page has no attributable author", [item.title for item in result.findings])

    def test_substantial_editorial_page_without_author_is_flagged(self) -> None:
        article = page(url="https://acme.example/guides/entity", text=words(320), json_ld=[{"@type": "Article"}])

        self.assertIn("Substantial editorial page has no attributable author", self.titles([page(), article]))

    def test_visible_social_profile_matching_same_as_is_not_flagged(self) -> None:
        linkedin = "https://www.linkedin.com/company/acme/"
        result = self.analyze([page(external_links=[linkedin], json_ld=[organization_json(same_as=[linkedin])])])

        self.assertEqual(len(result.social_profiles), 2)
        self.assertNotIn("Potential official profiles are missing from organization sameAs", [item.title for item in result.findings])

    def test_visible_social_profile_missing_from_same_as_is_flagged(self) -> None:
        linkedin = "https://www.linkedin.com/company/acme/"

        self.assertIn(
            "Potential official profiles are missing from organization sameAs",
            self.titles([page(external_links=[linkedin], json_ld=[organization_json(same_as=[])])]),
        )

    def test_trust_policy_pages_are_detected(self) -> None:
        privacy = "https://acme.example/privacy"
        terms = "https://acme.example/terms"
        result = self.analyze(
            [
                page(internal_links=[privacy, terms]),
                page(url=privacy, title="Privacy Policy", h1="Privacy Policy"),
                page(url=terms, title="Terms of Service", h1="Terms of Service"),
            ]
        )

        self.assertEqual({item.policy_type for item in result.trust_policy_pages}, {"Privacy Policy", "Terms of Service"})

    def test_external_credibility_context_is_recorded_without_verification(self) -> None:
        result = self.analyze(
            [
                page(
                    text=(
                        "According to a study, Acme is award-winning. Read customer testimonials and "
                        "our latest case study. Trusted by teams worldwide."
                    ),
                    image_alt_text=["Customer logo"],
                )
            ]
        )
        signal = result.credibility_signals[0]

        self.assertIn("According to", signal.named_source_labels)
        self.assertIn("award-winning", signal.certifications_or_awards)
        self.assertIn("Customer logo", signal.customer_logo_signals)
        self.assertIn("testimonials", signal.testimonial_signals)
        self.assertIn("case study", signal.case_study_signals)

    def test_missing_structured_name_and_url_are_flagged(self) -> None:
        incomplete = page(json_ld=[{"@type": "Organization", "sameAs": []}])
        titles = self.titles([incomplete])

        self.assertIn("Organization structured data is missing a name", titles)
        self.assertIn("Organization structured data is missing an official URL", titles)

    def test_organization_and_person_names_are_not_compared_as_conflicts(self) -> None:
        result = self.analyze(
            [
                page(
                    title="Stripe",
                    h1="Stripe",
                    json_ld=[
                        {
                            "@type": "Organization",
                            "name": "Stripe",
                            "url": "https://stripe.example/",
                            "sameAs": [],
                        },
                        {"@type": "Person", "name": "Patrick Collison"},
                    ],
                )
            ]
        )

        self.assertNotIn("Entity Consistency Risk", [item.title for item in result.findings])
        self.assertEqual([item.name for item in result.person_entities], ["Patrick Collison"])

    def test_founder_person_is_not_treated_as_an_organization(self) -> None:
        result = self.analyze(
            [
                page(
                    title="Stripe",
                    h1="Stripe",
                    json_ld=[
                        {
                            "@type": "Organization",
                            "name": "Stripe",
                            "url": "https://stripe.example/",
                            "sameAs": [],
                            "founder": {"@type": "Person", "name": "Patrick Collison"},
                        }
                    ]
                )
            ]
        )

        titles = [item.title for item in result.findings]
        self.assertNotIn("Organization structured data is missing an official URL", titles)
        self.assertNotIn("Entity Consistency Risk", titles)
        self.assertEqual([item.name for item in result.person_entities], ["Patrick Collison"])

    def test_duplicate_person_json_ld_creates_one_missing_profile_finding(self) -> None:
        person = {"@type": "Person", "name": "Jane Doe"}
        result = self.analyze([page(json_ld=[person, person])])
        titles = [item.title for item in result.findings]

        self.assertEqual(len(result.person_entities), 1)
        self.assertEqual(titles.count("Person structured data is missing a profile URL"), 1)

    def test_identical_normalized_phone_numbers_are_not_inconsistent(self) -> None:
        contact_url = "https://acme.example/contact"
        titles = self.titles(
            [
                page(text="Call +1 (415) 555-1212", internal_links=[contact_url]),
                page(url=contact_url, title="Contact", h1="Contact", text="Call 415 555 1212"),
            ]
        )

        self.assertNotIn("Public organization contact details may be inconsistent", titles)

    def test_different_normalized_phone_numbers_create_one_finding(self) -> None:
        contact_url = "https://acme.example/contact"
        titles = self.titles(
            [
                page(text="Call +1 (415) 555-1212", internal_links=[contact_url]),
                page(url=contact_url, title="Contact", h1="Contact", text="Call +1 (646) 555-1212"),
            ]
        )

        self.assertEqual(titles.count("Public organization contact details may be inconsistent"), 1)

    def test_youtube_watch_url_is_not_classified_as_a_profile(self) -> None:
        watch_url = "https://www.youtube.com/watch?v=stripe-video"
        result = self.analyze([page(external_links=[watch_url], json_ld=[organization_json(same_as=[])])])

        self.assertFalse(any(item.url == watch_url for item in result.social_profiles))

    def test_youtube_channel_url_is_classified_as_a_profile(self) -> None:
        channel_url = "https://www.youtube.com/channel/UC123"
        result = self.analyze(
            [page(external_links=[channel_url], json_ld=[organization_json(same_as=[channel_url])])]
        )

        self.assertTrue(any(item.url == channel_url and item.network == "YouTube" for item in result.social_profiles))

    def test_github_repository_url_is_not_classified_as_an_organization_profile(self) -> None:
        repository_url = "https://github.com/stripe/stripe-python"
        result = self.analyze([page(external_links=[repository_url], json_ld=[organization_json(same_as=[])])])

        self.assertFalse(any(item.url == repository_url for item in result.social_profiles))

    def test_github_organization_url_is_classified_as_a_potential_profile(self) -> None:
        organization_url = "https://github.com/stripe"
        result = self.analyze(
            [
                page(
                    external_links=[organization_url],
                    json_ld=[organization_json(name="Stripe", same_as=[])],
                )
            ]
        )

        self.assertTrue(any(item.url == organization_url and item.network == "GitHub" for item in result.social_profiles))

    def test_duplicate_social_links_are_retained_once(self) -> None:
        github_url = "https://github.com/stripe-samples"
        result = self.analyze(
            [
                page(
                    external_links=[github_url, github_url, f"{github_url}/"],
                    json_ld=[organization_json(name="Stripe Samples", same_as=[])],
                )
            ]
        )
        finding = next(
            item
            for item in result.findings
            if item.title == "Potential official profiles are missing from organization sameAs"
        )

        self.assertEqual(len([item for item in result.social_profiles if item.source_type == "visible social link"]), 1)
        self.assertEqual(len(finding.evidence), 1)

    def test_stripe_and_stripe_inc_are_equivalent(self) -> None:
        stripe = page(
            title="Stripe, Inc.",
            h1="Stripe",
            open_graph={"og:site_name": "STRIPE"},
            json_ld=[organization_json(name="Stripe", url="https://stripe.example/", same_as=[])],
        )

        self.assertNotIn("Entity Consistency Risk", self.titles([stripe]))

    def test_organization_findings_use_organization_specific_labels(self) -> None:
        titles = self.titles([page(json_ld=[{"@type": "Organization", "name": "Acme", "sameAs": []}])])

        self.assertIn("Organization structured data is missing an official URL", titles)
        self.assertNotIn("Person structured data is missing a profile URL", titles)

    def test_person_findings_use_person_specific_labels(self) -> None:
        titles = self.titles([page(json_ld=[{"@type": "Person", "name": "Jane Doe"}])])

        self.assertIn("Person structured data is missing a profile URL", titles)
        self.assertNotIn("Organization structured data is missing an official URL", titles)

    def test_unrelated_wikipedia_topic_is_not_an_organization_profile(self) -> None:
        topic_url = "https://en.wikipedia.org/wiki/Tkinter"
        result = self.analyze(
            [
                page(
                    external_links=[topic_url],
                    json_ld=[organization_json(name="Python Software Foundation", same_as=[])],
                )
            ]
        )

        self.assertFalse(any(item.url == topic_url for item in result.social_profiles))

    def test_matching_organization_wikipedia_page_is_a_candidate(self) -> None:
        organization_url = "https://en.wikipedia.org/wiki/Python_Software_Foundation"
        result = self.analyze(
            [
                page(
                    external_links=[organization_url],
                    json_ld=[organization_json(name="Python Software Foundation", same_as=[])],
                )
            ]
        )

        self.assertTrue(any(item.url == organization_url and item.network == "Wikipedia" for item in result.social_profiles))

    def test_project_github_link_is_not_an_organization_profile(self) -> None:
        project_url = "https://github.com/python/cpython"
        result = self.analyze(
            [
                page(
                    external_links=[project_url],
                    json_ld=[organization_json(name="Python Software Foundation", same_as=[])],
                )
            ]
        )

        self.assertFalse(any(item.url == project_url for item in result.social_profiles))

    def test_social_link_with_matching_organization_slug_is_accepted(self) -> None:
        profile_url = "https://www.linkedin.com/company/python-software-foundation"
        result = self.analyze(
            [
                page(
                    external_links=[profile_url],
                    json_ld=[organization_json(name="Python Software Foundation", same_as=[])],
                )
            ]
        )

        profile = next(item for item in result.social_profiles if item.url == profile_url)
        self.assertIn("profile URL slug matches an organization name", profile.relevance_signals)

    def test_unrelated_partner_social_link_is_ignored(self) -> None:
        partner_url = "https://www.linkedin.com/company/example-partner"
        result = self.analyze(
            [
                page(
                    external_links=[partner_url],
                    json_ld=[organization_json(name="Python Software Foundation", same_as=[])],
                )
            ]
        )

        self.assertFalse(any(item.url == partner_url for item in result.social_profiles))

    def test_identical_social_urls_are_deduplicated_after_normalization(self) -> None:
        profile_url = "https://www.linkedin.com/company/acme"
        result = self.analyze(
            [
                page(
                    external_links=[profile_url, f"{profile_url}/"],
                    json_ld=[organization_json(name="Acme", same_as=[])],
                )
            ]
        )

        self.assertEqual(len([item for item in result.social_profiles if item.url.rstrip("/") == profile_url]), 1)

    def test_multiple_linkedin_candidates_are_not_collapsed_as_duplicates(self) -> None:
        first = "https://www.linkedin.com/company/acme"
        second = "https://www.linkedin.com/company/acme-inc"
        result = self.analyze(
            [
                page(
                    external_links=[first, second],
                    json_ld=[organization_json(name="Acme", same_as=[])],
                )
            ]
        )
        finding = next(
            item
            for item in result.findings
            if item.title == "Multiple potential LinkedIn profiles detected"
        )

        self.assertEqual([item.exact_text.rsplit(": ", 1)[-1] for item in finding.evidence], [first, second])
        self.assertIn("Verify which profile represents the organization", finding.recommendation)
        output = io.StringIO()
        with redirect_stdout(output):
            _print_entity_findings(
                CrawlResult(
                    requested_url=SITE_URL,
                    analyzed_url=SITE_URL,
                    pages=[],
                    entity_trust=result,
                    max_pages=12,
                    started_at=NOW,
                    completed_at=NOW,
                )
            )

        self.assertIn("Multiple potential LinkedIn profiles detected", output.getvalue())
        self.assertIn("Potential profiles:", output.getvalue())
        self.assertIn(f"- Potential LinkedIn profile detected: {first}", output.getvalue())
        self.assertIn(f"- Potential LinkedIn profile detected: {second}", output.getvalue())

    def test_nonprofit_recommendation_uses_organization_neutral_language(self) -> None:
        result = self.analyze([page(title="Python Software Foundation", h1="Python Software Foundation")])
        finding = next(item for item in result.findings if item.title == "Organization-like structured data was not detected")

        self.assertIn("accurate organization details", finding.recommendation)
        self.assertNotIn("business details", finding.recommendation)

    def test_entity_cli_flag_groups_findings(self) -> None:
        analysis = self.analyze([page()])
        result = CrawlResult(
            requested_url=SITE_URL,
            analyzed_url=SITE_URL,
            pages=[page()],
            entity_trust=analysis,
            max_pages=12,
            started_at=NOW,
            completed_at=NOW,
        )
        output = io.StringIO()

        with (
            patch("citeready.cli.load_crawler_settings", return_value=CrawlerSettings()),
            patch("citeready.cli.SiteCrawler") as crawler_type,
            patch("sys.argv", ["citeready", SITE_URL, "--show-entity-findings"]),
            redirect_stdout(output),
        ):
            crawler_type.return_value.crawl.return_value = result
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("Entity and Trust findings", output.getvalue())
        self.assertIn("Structured data", output.getvalue())
        self.assertIn("Contact and organization pages", output.getvalue())


if __name__ == "__main__":
    unittest.main()
