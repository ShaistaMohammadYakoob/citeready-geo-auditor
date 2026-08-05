"""Offline checks for terminal-only finding presentation refinements."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from citeready.cli import _print_finding_details
from citeready.models import DiscoverabilityFinding, Evidence, Severity


def finding(
    *,
    title: str,
    page_url: str = "https://example.com/",
    evidence: list[Evidence] | None = None,
) -> DiscoverabilityFinding:
    return DiscoverabilityFinding(
        title=title,
        severity=Severity.MEDIUM,
        affected_url=page_url,
        evidence=evidence or [Evidence(page_url=page_url, exact_text="Detected evidence.", source_type="test")],
        why_it_matters="This is why the finding matters.",
        recommendation="Take the recommended action.",
        impact=3,
        effort=2,
    )


def render(findings: list[DiscoverabilityFinding]) -> str:
    output = io.StringIO()
    with redirect_stdout(output):
        _print_finding_details(findings)
    return output.getvalue()


class CliPresentationTests(unittest.TestCase):
    """Confirm presentation is bounded without changing the stored models."""

    def test_long_evidence_is_truncated_only_in_terminal_output(self) -> None:
        full_evidence = "x" * 300
        item = finding(
            title="Long evidence",
            evidence=[Evidence(page_url="https://example.com/", exact_text=full_evidence, source_type="test")],
        )
        output = render([item])

        self.assertIn("x" * 250, output)
        self.assertNotIn("x" * 251, output)
        self.assertIn("(+50 additional characters retained)", output)
        self.assertEqual(item.evidence[0].exact_text, full_evidence)

    def test_multiple_h1_finding_uses_count_first_five_and_remainder(self) -> None:
        h1s = [f"Heading {index}" for index in range(7)]
        item = finding(
            title="Page has multiple H1 headings",
            evidence=[
                Evidence(
                    page_url="https://example.com/",
                    exact_text="; ".join(f"H1: {heading}" for heading in h1s),
                    source_type="heading hierarchy",
                )
            ],
        )
        output = render([item])

        self.assertIn("Detected H1 count: 7", output)
        self.assertIn("First five headings:", output)
        self.assertIn("- Heading 4", output)
        self.assertNotIn("- Heading 5", output)
        self.assertIn("Remaining count: 2", output)
        self.assertNotIn("Evidence: H1:", output)

    def test_opening_finding_shows_excerpt_reason_and_recommendation(self) -> None:
        item = finding(
            title="Opening does not clearly state what the page is about",
            evidence=[
                Evidence(
                    page_url="https://example.com/",
                    exact_text="Opening content. " * 30,
                    source_type="opening 200 words",
                    context="The opening does not repeat enough title terms.",
                )
            ],
        )
        output = render([item])

        self.assertIn("Opening excerpt:", output)
        self.assertIn("Reason: The opening does not repeat enough title terms.", output)
        self.assertIn("Recommended action: Take the recommended action.", output)
        self.assertNotIn("Evidence: Opening content", output)

    def test_claim_and_question_examples_are_limited_to_five(self) -> None:
        claims = [
            Evidence(page_url="https://example.com/", exact_text=f"Claim example {index}", source_type="test")
            for index in range(7)
        ]
        questions = [
            Evidence(page_url="https://example.com/", exact_text=f"Question example {index}", source_type="test")
            for index in range(7)
        ]
        output = render(
            [
                finding(title="Potentially unsupported claims (confidence-based)", evidence=claims),
                finding(title="Question headings do not have visible answers", evidence=questions),
            ]
        )

        self.assertIn("Claim example 4", output)
        self.assertNotIn("Claim example 5", output)
        self.assertIn("Question example 4", output)
        self.assertNotIn("Question example 5", output)
        self.assertEqual(output.count("(+2 additional matches)"), 2)

    def test_findings_are_grouped_by_page(self) -> None:
        output = render(
            [
                finding(title="First", page_url="https://example.com/one"),
                finding(title="Second", page_url="https://example.com/one"),
                finding(title="Third", page_url="https://example.com/two"),
            ]
        )

        self.assertEqual(output.count("Page: https://example.com/one"), 1)
        self.assertEqual(output.count("Page: https://example.com/two"), 1)


if __name__ == "__main__":
    unittest.main()
