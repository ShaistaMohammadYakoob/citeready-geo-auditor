"""Streamlit orchestration entry point for CiteReady's GEO audit dashboard."""

from __future__ import annotations

import logging

import streamlit as st

from citeready.config import load_crawler_settings
from citeready.crawler import SiteCrawler
from citeready.ui.components import render_hero, render_navigation, render_timeline
from citeready.ui.dashboard_helpers import initialise_theme_state, set_theme_mode
from citeready.ui.report_sections import render_report
from citeready.ui.styles import dashboard_css
from citeready.ui.theme import ThemeMode
from citeready.dashboard import safe_error_message, validate_dashboard_url


LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Render the app while preserving completed audits across UI interactions."""

    st.set_page_config(page_title="CiteReady | GEO Visibility Auditor", page_icon="CR", layout="wide")
    _initialise_state()
    mode = initialise_theme_state(st.session_state)
    st.markdown(dashboard_css(mode), unsafe_allow_html=True)
    render_navigation(mode, lambda is_dark: set_theme_mode(st.session_state, is_dark))
    mode = initialise_theme_state(st.session_state)
    st.markdown(dashboard_css(mode), unsafe_allow_html=True)
    render_hero()

    request = _render_audit_input()
    if request:
        _start_audit(*request)

    result = st.session_state.get("audit_result")
    if result is not None:
        rerun = render_report(result, mode)
        if rerun:
            _start_audit(result.analyzed_url, result.max_pages, force=True)
            st.rerun()


def _initialise_state() -> None:
    st.session_state.setdefault("audit_result", None)
    st.session_state.setdefault("audit_cache", {})
    st.session_state.setdefault("audit_running", False)
    st.session_state.setdefault("show_methodology", False)


def _render_audit_input() -> tuple[str, int] | None:
    """Collect an audit request without re-running a completed report on widget changes."""

    with st.form("audit-input", clear_on_submit=False):
        left, right = st.columns((4, 1), vertical_alignment="bottom")
        with left:
            url = st.text_input("Website URL", placeholder="https://example.com", help="Enter a public HTTP or HTTPS website.")
        with right:
            max_pages = st.selectbox("Maximum pages", options=list(range(1, 13)), index=11)
        submitted = st.form_submit_button("Run audit", type="primary", use_container_width=True, disabled=st.session_state.audit_running)

    if not submitted:
        return None
    normalized_url, error = validate_dashboard_url(url)
    if error:
        st.error(error)
        return None
    assert normalized_url is not None
    return normalized_url, max_pages


def _start_audit(site_url: str, max_pages: int, *, force: bool = False) -> None:
    """Run one audit, caching only completed results in the current session."""

    key = (site_url, max_pages)
    if not force and key in st.session_state.audit_cache:
        st.session_state.audit_result = st.session_state.audit_cache[key]
        st.info("Showing the completed audit already generated for this URL and page limit in this session.")
        return

    st.session_state.audit_running = True
    timeline_slot = st.empty()
    status = st.status("Audit underway", expanded=True)
    completed: set[str] = {"validated"}
    active = "crawled"

    def draw_timeline() -> None:
        timeline_slot.empty()
        with timeline_slot.container():
            render_timeline(completed, active)

    def update_progress(event: str) -> None:
        nonlocal active
        transitions = {
            "crawl_started": (None, "crawled", "Important pages are being crawled"),
            "crawl_completed": ("crawled", "robots_sitemap", "Important pages crawled"),
            "robots_txt_completed": (None, "robots_sitemap", "robots.txt checked"),
            "sitemap_completed": ("robots_sitemap", "citation", "Robots and sitemap checked"),
            "citation_readiness_completed": ("citation", "entity", "Citation structure analyzed"),
            "entity_trust_completed": ("entity", "answerability", "Entity signals reviewed"),
            "answerability_completed": ("answerability", "scored", "Customer questions evaluated"),
            "scoring_completed": ("scored", None, "Score calculated"),
        }
        transition = transitions.get(event)
        if transition is None:
            return
        completed_step, next_active, message = transition
        if completed_step:
            completed.add(completed_step)
        active = next_active
        status.write(f"✓ {message}" if completed_step else f"• {message}")
        draw_timeline()

    try:
        status.write("✓ Website validated")
        draw_timeline()
        settings = load_crawler_settings()
        settings = type(settings).model_validate({**settings.model_dump(), "max_pages": max_pages})
        result = SiteCrawler(settings).crawl(site_url, progress_callback=update_progress)
        status.write("✓ Building report")
        status.update(label="Audit completed", state="complete", expanded=False)
        st.session_state.audit_cache[key] = result
        st.session_state.audit_result = result
    except Exception as error:  # Technical context remains in the server log, not in the business report.
        LOGGER.exception("Audit failed for %s", site_url)
        status.update(label="Audit could not complete", state="error", expanded=True)
        st.error(safe_error_message(error))
    finally:
        st.session_state.audit_running = False


if __name__ == "__main__":
    main()
