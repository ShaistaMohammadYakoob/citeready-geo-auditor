"""Offline coverage for deterministic Phase 5 AI Answerability analysis."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from citeready.analyzers.answerability import AnswerabilityAnalyzer
from citeready.cli import main
from citeready.config import CrawlerSettings
from citeready.models import (
    AnswerStatus,
    CallToActionSignal,
    ContentBlock,
    CrawlResult,
    CrawledPage,
    EntityTrustAnalysis,
    ExternalCredibilitySignal,
    Heading,
)
from citeready.parser import parse_html_page


SITE_URL = "https://acme.example/"
NOW = datetime.now(timezone.utc)


def heading(level: int, text: str) -> ContentBlock:
    return ContentBlock(kind="heading", text=text, heading_level=level)


def paragraph(text: str) -> ContentBlock:
    return ContentBlock(kind="paragraph", text=text)


def table(text: str) -> ContentBlock:
    return ContentBlock(kind="table", text=text)


def page(
    *,
    url: str = SITE_URL,
    title: str = "Acme Workflow Software",
    blocks: list[ContentBlock] | None = None,
    visible_addresses: list[str] | None = None,
    has_contact_form: bool = False,
    call_to_action_labels: list[str] | None = None,
    open_graph: dict[str, str] | None = None,
    json_ld: list[object] | None = None,
) -> CrawledPage:
    page_blocks = blocks if blocks is not None else [heading(1, title)]
    return CrawledPage(
        requested_url=url,
        url=url,
        status_code=200,
        title=title,
        headings=[Heading(level=1, text=title)],
        content_blocks=page_blocks,
        text_content=" ".join(block.text for block in page_blocks),
        open_graph=open_graph or {},
        json_ld=json_ld or [],
        visible_addresses=visible_addresses or [],
        has_contact_form=has_contact_form,
        call_to_action_labels=call_to_action_labels or [],
        fetched_at=NOW,
    )


class AnswerabilityAnalyzerTests(unittest.TestCase):
    """Exercise every requested Phase 5 deterministic heuristic without HTTP."""

    def setUp(self) -> None:
        self.analyzer = AnswerabilityAnalyzer()

    def analyze(self, pages: list[CrawledPage]):
        return self.analyzer.analyze(pages)

    def result(self, pages: list[CrawledPage], question_id: str):
        return next(item for item in self.analyze(pages).results if item.question.id == question_id)

    @staticmethod
    def organization(name: str) -> list[object]:
        return [{"@context": "https://schema.org", "@type": "Organization", "name": name}]

    def test_clear_purpose_answer(self) -> None:
        purpose = "Acme provides workflow software that helps operations teams automate approval processes."
        result = self.result([page(blocks=[heading(1, "Acme"), paragraph(purpose)])], "purpose")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.answer_excerpt, purpose)
        self.assertEqual(result.supporting_urls, [SITE_URL])

    def test_weak_purpose_answer_is_partial(self) -> None:
        result = self.result([page(blocks=[paragraph("We offer software.")])], "purpose")

        self.assertEqual(result.status, AnswerStatus.PARTIALLY_ANSWERED)
        self.assertIn("too brief or generic", result.explanation)

    def test_clear_target_audience(self) -> None:
        audience = "Our platform is built for operations teams that manage complex approval workflows."
        result = self.result([page(blocks=[paragraph(audience)])], "audience")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.answer_excerpt, audience)

    def test_missing_target_audience(self) -> None:
        result = self.result([page(blocks=[paragraph("Acme offers dependable workflow software with clear reporting.")])], "audience")

        self.assertEqual(result.status, AnswerStatus.NOT_ANSWERED)
        self.assertIn("specific audience", result.explanation)

    def test_pricing_page_with_amount_is_detected(self) -> None:
        pricing_page = page(
            url="https://acme.example/pricing",
            title="Acme Pricing",
            blocks=[table("Starter plan: $29 per month for one workspace.")],
        )
        result = self.result([pricing_page], "pricing")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertIn("$29", result.answer_excerpt or "")

    def test_noncommercial_site_does_not_receive_pricing_penalty(self) -> None:
        nonprofit = page(blocks=[paragraph("The Acme Foundation is a nonprofit organization funded by donations.")])
        analysis = self.analyze([nonprofit])
        result = next(item for item in analysis.results if item.question.id == "pricing")

        self.assertEqual(result.status, AnswerStatus.NOT_APPLICABLE)
        self.assertNotIn("Pricing is not findable where commercially relevant", [item.title for item in analysis.findings])

    def test_contact_method_detected_from_form(self) -> None:
        contact_page = page(url="https://acme.example/contact", title="Contact Acme", has_contact_form=True)
        result = self.result([contact_page], "contact")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.evidence[0].source_type, "HTML contact form")

    def test_geographic_scope_detected(self) -> None:
        location = "Acme is based in Pune, India and serves teams across Maharashtra."
        result = self.result([page(blocks=[paragraph(location)])], "location")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.answer_excerpt, location)

    def test_global_digital_product_does_not_receive_location_penalty(self) -> None:
        digital = "Our cloud software platform is available worldwide online for distributed developer teams."
        analysis = self.analyze([page(blocks=[paragraph(digital)])])
        result = next(item for item in analysis.results if item.question.id == "location")

        self.assertEqual(result.status, AnswerStatus.NOT_APPLICABLE)
        self.assertNotIn("Geographic coverage is unclear where relevant", [item.title for item in analysis.findings])

    def test_differentiation_language_detected(self) -> None:
        differentiator = "Unlike spreadsheets, Acme combines approvals, audit history, and reporting in one workspace."
        result = self.result([page(blocks=[paragraph(differentiator)])], "differentiation")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.answer_excerpt, differentiator)

    def test_clear_call_to_action_detected(self) -> None:
        result = self.result([page(call_to_action_labels=["Start a free trial"])], "next_action")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.answer_excerpt, "Start a free trial")

    def test_parser_retains_button_and_link_call_to_action_labels(self) -> None:
        parsed = parse_html_page(
            requested_url=SITE_URL,
            final_url=SITE_URL,
            status_code=200,
            content_type="text/html",
            html=(
                '<html><body><a href="/trial">Start a free trial</a>'
                '<button>Book a demo</button></body></html>'
            ),
        )

        self.assertEqual(parsed.call_to_action_labels, ["Start a free trial", "Book a demo"])

    def test_conflicting_purpose_descriptions_are_flagged_conservatively(self) -> None:
        home = page(blocks=[paragraph("Acme is a nonprofit organization that supports public-interest research.")])
        about = page(
            url="https://acme.example/about",
            title="About Acme",
            blocks=[paragraph("Acme is a commercial software company serving enterprise customers.")],
        )
        analysis = self.analyze([home, about])
        result = next(item for item in analysis.results if item.question.id == "purpose")

        self.assertEqual(result.status, AnswerStatus.CONFLICTING_ANSWER)
        self.assertIn("commercial software", result.conflicting_excerpt or "")
        self.assertIn("Contradictory organization descriptions", [item.title for item in analysis.findings])

    def test_navigation_only_text_is_not_treated_as_an_answer(self) -> None:
        navigation_only = page(
            blocks=[heading(1, "Acme"), heading(2, "Services"), heading(2, "Pricing"), heading(2, "Contact")]
        )
        analysis = self.analyze([navigation_only])
        purpose = next(item for item in analysis.results if item.question.id == "purpose")
        offerings = next(item for item in analysis.results if item.question.id == "offerings")

        self.assertEqual(purpose.status, AnswerStatus.NOT_ANSWERED)
        self.assertEqual(offerings.status, AnswerStatus.NOT_ANSWERED)

    def test_evidence_includes_exact_url_and_excerpt(self) -> None:
        purpose = "Acme provides workflow software for operations teams with complex approval needs."
        result = self.result([page(blocks=[paragraph(purpose)])], "purpose")

        self.assertEqual(result.evidence[0].page_url, SITE_URL)
        self.assertEqual(result.evidence[0].excerpt, purpose)
        self.assertEqual(result.supporting_urls, [SITE_URL])
        self.assertIn("Primary entity alias", result.evidence[0].entity_relevance_reason or "")
        self.assertIsNotNone(result.evidence[0].relevance_score)

    def test_not_applicable_classification_is_recorded_in_summary(self) -> None:
        analysis = self.analyze([page(blocks=[paragraph("The Acme Foundation is a nonprofit organization funded by donations.")])])

        self.assertGreaterEqual(analysis.summary.not_applicable, 1)
        self.assertTrue(any(item.status == AnswerStatus.NOT_APPLICABLE for item in analysis.results))

    def test_phase_four_credibility_signal_is_used_as_partial_trust_evidence(self) -> None:
        phase_four = EntityTrustAnalysis(
            credibility_signals=[
                ExternalCredibilitySignal(
                    page_url=SITE_URL,
                    certifications_or_awards=["ISO 27001 certified"],
                )
            ]
        )
        result = next(
            item
            for item in self.analyzer.analyze([page()], phase_four).results
            if item.question.id == "trust"
        )

        self.assertEqual(result.status, AnswerStatus.PARTIALLY_ANSWERED)
        self.assertEqual(result.evidence[0].excerpt, "ISO 27001 certified")
        self.assertEqual(result.evidence[0].source_type, "Phase 4 visible certification or award")

    def test_stripe_customer_case_study_is_rejected_as_an_offering(self) -> None:
        homepage = page(
            title="Stripe",
            json_ld=self.organization("Stripe"),
            blocks=[paragraph("Stripe is financial infrastructure for internet businesses.")],
        )
        case_study = page(
            url="https://acme.example/customers/supabase",
            title="Supabase customer story",
            blocks=[paragraph("Supabase delivers a developer platform for application teams.")],
        )
        result = self.result([homepage, case_study], "offerings")

        self.assertNotEqual(result.answer_excerpt, "Supabase delivers a developer platform for application teams.")
        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)

    def test_transaction_volume_is_rejected_as_pricing(self) -> None:
        homepage = page(
            title="Stripe",
            json_ld=self.organization("Stripe"),
            blocks=[paragraph("Stripe provides financial infrastructure and processed US$1.9tn in transaction volume.")],
        )
        result = self.result([homepage], "pricing")

        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertNotIn("US$1.9tn", result.answer_excerpt or "")

    def test_python_scipy_passage_is_rejected_as_purpose(self) -> None:
        homepage = page(
            title="Python.org",
            json_ld=self.organization("Python.org"),
            blocks=[paragraph("SciPy provides fundamental algorithms for scientific computing.")],
        )
        result = self.result([homepage], "purpose")

        self.assertEqual(result.status, AnswerStatus.NOT_ANSWERED)
        self.assertIsNone(result.answer_excerpt)

    def test_python_odoo_passage_is_rejected_as_an_offering(self) -> None:
        homepage = page(
            title="Python.org",
            json_ld=self.organization("Python.org"),
            blocks=[paragraph("Odoo is an open-source suite of business applications.")],
        )
        result = self.result([homepage], "offerings")

        self.assertEqual(result.status, AnswerStatus.NOT_ANSWERED)
        self.assertIsNone(result.answer_excerpt)

    def test_grant_amount_is_rejected_as_pricing(self) -> None:
        homepage = page(
            title="Python Software Foundation",
            json_ld=self.organization("Python Software Foundation"),
            blocks=[paragraph("The Python Software Foundation is a nonprofit organization that awarded a $10,000 grant.")],
        )
        result = self.result([homepage], "pricing")

        self.assertEqual(result.status, AnswerStatus.NOT_APPLICABLE)
        self.assertNotIn("$10,000", result.answer_excerpt or "")

    def test_arithmetic_content_is_rejected_as_contact_evidence(self) -> None:
        homepage = page(blocks=[paragraph("Acme provides software. Example code: print(1234567890 + 5).")])
        result = self.result([homepage], "contact")

        self.assertEqual(result.status, AnswerStatus.NOT_ANSWERED)

    def test_homepage_cta_wins_over_legal_page_cta(self) -> None:
        homepage = page(title="Acme", call_to_action_labels=["Download Acme"])
        legal = page(
            url="https://acme.example/privacy",
            title="Acme Privacy Policy",
            call_to_action_labels=["Join now"],
        )
        result = self.result([homepage, legal], "next_action")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertEqual(result.answer_excerpt, "Download Acme")

    def test_footer_only_cta_is_rejected(self) -> None:
        homepage = page(title="Acme")
        homepage.call_to_action_signals = [
            CallToActionSignal(label="Join now", element_type="a", location="footer")
        ]
        result = self.result([homepage], "next_action")

        self.assertEqual(result.status, AnswerStatus.NOT_ANSWERED)

    def test_homepage_cta_keeps_priority_over_a_higher_relevance_product_cta(self) -> None:
        homepage = page(title="Acme", call_to_action_labels=["Download Acme"])
        product = page(
            url="https://acme.example/product",
            title="Acme Product",
            call_to_action_labels=["Sign up to receive our newsletter!"],
        )
        result = self.result([homepage, product], "next_action")

        self.assertEqual(result.answer_excerpt, "Download Acme")

    def test_non_geographic_available_in_phrase_is_rejected_as_location(self) -> None:
        homepage = page(blocks=[paragraph("Acme support is available in Python through the documentation portal.")])
        result = self.result([homepage], "location")

        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)

    def test_third_party_ecosystem_content_is_rejected(self) -> None:
        homepage = page(
            title="Python.org",
            json_ld=self.organization("Python.org"),
            blocks=[paragraph("Django offers a high-level web framework for Python developers.")],
        )
        result = self.result([homepage], "offerings")

        self.assertEqual(result.status, AnswerStatus.NOT_ANSWERED)

    def test_actual_fee_phrase_is_accepted_as_pricing(self) -> None:
        homepage = page(
            title="Stripe",
            json_ld=self.organization("Stripe"),
            blocks=[paragraph("Stripe charges a $0.30 fee per transaction for this payment service.")],
        )
        result = self.result([homepage], "pricing")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertIn("$0.30 fee per transaction", result.answer_excerpt or "")

    def test_explicit_global_availability_is_accepted_for_a_primary_digital_offering(self) -> None:
        homepage = page(
            blocks=[paragraph("Acme's cloud platform is available worldwide for distributed operations teams.")]
        )
        result = self.result([homepage], "location")

        self.assertEqual(result.status, AnswerStatus.NOT_APPLICABLE)
        self.assertIn("available worldwide", result.answer_excerpt or "")

    def test_email_and_phone_are_accepted_as_contact_methods(self) -> None:
        homepage = page(
            blocks=[paragraph("Contact Acme at sales@acme.example or call +1 (415) 555-1212 for sales inquiries.")]
        )
        result = self.result([homepage], "contact")

        self.assertEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertIn("sales@acme.example", result.answer_excerpt or "")

    def test_primary_entity_passage_is_preferred_over_unrelated_passage(self) -> None:
        homepage = page(
            title="Stripe",
            json_ld=self.organization("Stripe"),
            blocks=[
                paragraph("Supabase provides database tools for developers."),
                paragraph("Stripe provides payment services for internet businesses with global ambitions."),
            ],
        )
        result = self.result([homepage], "offerings")

        self.assertIn("Stripe provides payment services", result.answer_excerpt or "")

    def test_low_relevance_candidate_produces_no_confident_purpose_answer(self) -> None:
        homepage = page(
            title="Python.org",
            json_ld=self.organization("Python.org"),
            blocks=[paragraph("NumPy is a package for scientific computing with Python.")],
        )
        result = self.result([homepage], "purpose")

        self.assertIn(result.status, {AnswerStatus.PARTIALLY_ANSWERED, AnswerStatus.NOT_ANSWERED})
        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)

    def test_open_source_site_without_paid_offering_gets_pricing_not_applicable(self) -> None:
        homepage = page(
            title="Python.org",
            json_ld=self.organization("Python.org"),
            blocks=[paragraph("Python is open source and maintained by a global community of contributors.")],
        )
        result = self.result([homepage], "pricing")

        self.assertEqual(result.status, AnswerStatus.NOT_APPLICABLE)

    def test_differentiation_must_describe_primary_entity(self) -> None:
        homepage = page(
            title="Python.org",
            json_ld=self.organization("Python.org"),
            blocks=[paragraph("Odoo is unique because it combines accounting and inventory tools.")],
        )
        result = self.result([homepage], "differentiation")

        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertNotIn("Odoo is unique", result.answer_excerpt or "")

    def test_partner_description_is_not_primary_entity_differentiation(self) -> None:
        homepage = page(
            title="Stripe",
            json_ld=self.organization("Stripe"),
            blocks=[paragraph("Crypto.com partners with Stripe to enable better crypto payments.")],
        )
        result = self.result([homepage], "differentiation")

        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertNotIn("Crypto.com partners", result.answer_excerpt or "")

    def test_customer_outcome_is_not_primary_entity_differentiation(self) -> None:
        homepage = page(
            title="Stripe",
            json_ld=self.organization("Stripe"),
            blocks=[
                paragraph(
                    "A leading retailer, the company called on Stripe to transform its payments infrastructure."
                )
            ],
        )
        result = self.result([homepage], "differentiation")

        self.assertNotEqual(result.status, AnswerStatus.CLEARLY_ANSWERED)
        self.assertNotIn("company called on Stripe", result.answer_excerpt or "")

    def test_case_study_customer_name_does_not_define_primary_entity(self) -> None:
        homepage = page(
            title="Stripe",
            open_graph={"og:site_name": "Stripe"},
            json_ld=self.organization("Stripe"),
        )
        case_study = page(
            url="https://acme.example/customers/supabase",
            title="Supabase customer story",
            json_ld=self.organization("Supabase"),
            blocks=[paragraph("Supabase is a developer platform.")],
        )
        analysis = self.analyze([homepage, case_study])

        self.assertEqual(analysis.primary_entity.entity_name, "Stripe")
        self.assertNotIn("Supabase", analysis.primary_entity.aliases)

    def test_answerability_findings_use_the_shared_finding_contract(self) -> None:
        analysis = self.analyze([page()])

        self.assertTrue(analysis.findings)
        for finding in analysis.findings:
            self.assertTrue(finding.id.startswith("answerability-"))
            self.assertEqual(finding.category.value, "AI Answerability")
            self.assertTrue(finding.evidence)
            self.assertTrue(finding.why_it_matters)
            self.assertTrue(finding.recommendation)
            self.assertIsNotNone(finding.impact)
            self.assertIsNotNone(finding.effort)

    def test_show_answerability_flag_prints_question_results_and_summary(self) -> None:
        analysis = self.analyze(
            [
                page(
                    blocks=[paragraph("Acme provides workflow software for operations teams with approval needs.")],
                    call_to_action_labels=["Start a free trial"],
                )
            ]
        )
        result = CrawlResult(
            requested_url=SITE_URL,
            analyzed_url=SITE_URL,
            pages=[],
            answerability=analysis,
            max_pages=12,
            started_at=NOW,
            completed_at=NOW,
        )
        output = io.StringIO()

        with (
            patch("citeready.cli.load_crawler_settings", return_value=CrawlerSettings()),
            patch("citeready.cli.SiteCrawler") as crawler_type,
            patch("sys.argv", ["citeready", SITE_URL, "--show-answerability"]),
            redirect_stdout(output),
        ):
            crawler_type.return_value.crawl.return_value = result
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("AI Answerability", output.getvalue())
        self.assertIn("Primary entity: Acme Workflow Software", output.getvalue())
        self.assertIn("What does this organization do?", output.getvalue())
        self.assertIn("Status: Clearly answered", output.getvalue())
        self.assertIn("Entity relevance:", output.getvalue())
        self.assertIn("Summary:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
