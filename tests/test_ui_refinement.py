"""Offline checks for the refined Streamlit UI architecture and visual helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from citeready.models import AuditCategory, CategoryScore, CrawlResult, OverallScore
from citeready.ui.charts import category_comparison_chart, impact_effort_chart
from citeready.ui.dashboard_helpers import (
    category_summaries,
    initialise_theme_state,
    report_header_sentence,
    safe_html,
    set_theme_mode,
)
from citeready.ui.animations import animation_css
from citeready.ui.styles import dashboard_css
from citeready.ui.theme import score_status_style, theme_tokens


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
URL = "https://example.com/"


def result(scores: list[CategoryScore]) -> CrawlResult:
    return CrawlResult(
        requested_url=URL,
        analyzed_url=URL,
        scoring=OverallScore(
            overall_points=sum(item.earned_points for item in scores),
            overall_percentage=75,
            category_scores=scores,
        ),
        max_pages=12,
        started_at=NOW,
        completed_at=NOW,
    )


class UiRefinementTests(unittest.TestCase):
    def test_theme_tokens_change_between_light_and_dark(self) -> None:
        self.assertEqual(theme_tokens("light")["background"], "#F3F8FB")
        self.assertEqual(theme_tokens("dark")["background"], "#071A2B")
        self.assertEqual(theme_tokens("light")["primary"], "#0F8B8D")
        self.assertEqual(theme_tokens("dark")["surface"], "#0E2438")
        self.assertNotEqual(theme_tokens("light")["text"], theme_tokens("dark")["text"])

    def test_plotly_charts_use_active_theme_layout(self) -> None:
        score = CategoryScore(
            category=AuditCategory.DISCOVERABILITY,
            maximum_points=25,
            earned_points=20,
            percentage=80,
        )
        light_chart = category_comparison_chart([score], "light")
        dark_chart = category_comparison_chart([score], "dark")

        self.assertEqual(light_chart.layout.paper_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(dark_chart.layout.font.color, "#EFF8FF")
        self.assertEqual(dark_chart.layout.template.layout.paper_bgcolor, "rgb(17,17,17)")
        self.assertEqual(len(impact_effort_chart([], "light").layout.annotations), 4)

    def test_score_status_styles_include_text_and_symbol(self) -> None:
        style = score_status_style(61, "light")
        self.assertEqual(style["label"], "Needs Improvement")
        self.assertEqual(style["symbol"], "!")
        self.assertTrue(style["color"].startswith("#"))

    def test_theme_mode_persists_without_touching_other_session_values(self) -> None:
        state: dict[str, object] = {"audit_result": "kept"}
        self.assertEqual(initialise_theme_state(state), "light")
        self.assertEqual(set_theme_mode(state, True), "dark")
        self.assertEqual(state["audit_result"], "kept")
        self.assertEqual(initialise_theme_state(state), "dark")

    def test_segmented_theme_control_updates_the_rendered_app_state(self) -> None:
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
        app.run(timeout=10)
        self.assertEqual(app.button_group[0].value, "light")

        app.button_group[0].select("dark").run(timeout=10)
        self.assertEqual(app.button_group[0].value, "dark")
        self.assertEqual(app.session_state["theme_mode"], "dark")
        self.assertIsNone(app.session_state["audit_result"])

    def test_category_summary_generation_preserves_score_values(self) -> None:
        score = CategoryScore(
            category=AuditCategory.CITATION_READINESS,
            maximum_points=25,
            earned_points=19,
            percentage=76,
        )
        summary = category_summaries(result([score]))[0]
        self.assertEqual(summary["title"], "Citation Readiness")
        self.assertEqual(summary["status"], "Good")
        self.assertEqual(summary["earned_points"], 19)

    def test_report_header_sentence_is_deterministic_from_categories(self) -> None:
        good = CategoryScore(category=AuditCategory.DISCOVERABILITY, maximum_points=25, earned_points=23, percentage=92)
        weak = CategoryScore(category=AuditCategory.CITATION_READINESS, maximum_points=25, earned_points=14, percentage=56)
        sentence = report_header_sentence(result([good, weak]))
        self.assertIn("AI Discoverability", sentence)
        self.assertIn("Citation Readiness", sentence)

    def test_reduced_motion_rules_are_present_in_custom_css(self) -> None:
        css = dashboard_css("dark")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn("--cr-background: #071A2B", css)
        self.assertIn("transition-duration: .01ms", css)

    def test_dark_mode_css_styles_native_streamlit_surfaces(self) -> None:
        css = dashboard_css("dark")
        self.assertIn("[data-testid=\"stExpander\"]", css)
        self.assertIn("[data-testid=\"stCodeBlock\"]", css)
        self.assertIn("[data-testid=\"stDataFrame\"]", css)
        self.assertIn("var(--cr-code-surface)", css)
        self.assertIn("var(--cr-input-surface)", css)

    def test_premium_component_styles_include_compact_interactions(self) -> None:
        css = dashboard_css("light")
        self.assertIn(".cr-nav-brand", css)
        self.assertIn(".cr-action-ticket", css)
        self.assertIn(".cr-progress-fill", css)
        self.assertIn(".cr-table", css)
        self.assertIn("@keyframes cr-ripple", css)
        self.assertIn("180ms", css)

    def test_ocean_motion_system_includes_requested_entrances(self) -> None:
        css = dashboard_css("light")
        keyframes = animation_css()
        self.assertIn("cr-mesh-shift", keyframes)
        self.assertIn("cr-progress-fill", keyframes)
        self.assertIn("cr-active-pulse", keyframes)
        self.assertIn("stButtonGroup", css)
        self.assertIn("cr-category-card-grid", css)

    def test_hero_and_theme_selector_have_explicit_contrast_rules(self) -> None:
        css = dashboard_css("light")
        self.assertIn('button[data-variant="segmented_control"][data-selected]', css)
        self.assertIn(".cr-hero .cr-hero-title", css)
        self.assertIn("color: var(--cr-on-primary) !important", css)

    def test_safe_html_escapes_untrusted_finding_content(self) -> None:
        escaped = safe_html('<script>alert("x")</script>')
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)

    def test_package_imports_without_manual_pythonpath_after_install(self) -> None:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [sys.executable, "-c", "import citeready.ui.theme; print(citeready.ui.theme.__name__)"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("citeready.ui.theme", completed.stdout)


if __name__ == "__main__":
    unittest.main()
