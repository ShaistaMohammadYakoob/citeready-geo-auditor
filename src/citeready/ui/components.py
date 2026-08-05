"""Reusable Streamlit components for CiteReady's presentation layer."""

from __future__ import annotations

import os
from collections.abc import Callable

import streamlit as st

from ..dashboard import ActionCard, concise_evidence
from ..models import DiscoverabilityFinding
from .dashboard_helpers import safe_html
from .theme import ThemeMode, score_status_style, severity_style


AUDIT_STEPS = (
    ("validated", "Website validated"),
    ("robots_sitemap", "Robots and sitemap checked"),
    ("crawled", "Important pages crawled"),
    ("citation", "Citation structure analyzed"),
    ("entity", "Entity signals reviewed"),
    ("answerability", "Customer questions evaluated"),
    ("scored", "Score calculated"),
)


def render_navigation(mode: ThemeMode, on_theme_change: Callable[[bool], None]) -> None:
    """Render the compact, session-safe product navigation."""

    left, theme, methodology, github = st.columns((5.5, 1.45, 1.05, 1.0), vertical_alignment="center")
    with left:
        st.markdown(
            "<div class='cr-nav-brand'><div class='cr-logo-mark'>CR</div><div><div class='cr-wordmark'>CiteReady</div>"
            "<div class='cr-product-label'>GEO Visibility Auditor</div></div></div>",
            unsafe_allow_html=True,
        )
    with theme:
        _render_theme_control(mode, on_theme_change)
    with methodology:
        if st.button("Methodology", use_container_width=True, key="about-nav"):
            st.session_state["show_methodology"] = True
    with github:
        st.link_button("GitHub", os.getenv("CITEREADY_REPOSITORY_URL", "https://github.com"), use_container_width=True)


def _render_theme_control(mode: ThemeMode, on_theme_change: Callable[[bool], None]) -> None:
    """Render a native selector and synchronise the mode before rerendering."""

    selector_key = "theme-mode-selector"
    if selector_key not in st.session_state:
        st.session_state[selector_key] = mode

    def sync_theme_mode() -> None:
        on_theme_change(st.session_state[selector_key] == "dark")

    st.segmented_control(
        "Theme mode",
        options=("light", "dark"),
        format_func=lambda option: "☀ Light" if option == "light" else "🌙 Dark",
        key=selector_key,
        on_change=sync_theme_mode,
        label_visibility="collapsed",
        width="stretch",
    )


def render_hero() -> None:
    """Render the ocean-themed introduction and four audit areas."""

    st.markdown(
        """
        <section class="cr-hero">
          <div class="cr-hero-copy">
            <div class="cr-eyebrow">Evidence-based GEO audit</div>
            <h1 class="cr-hero-title">Can AI engines <span class="cr-title-accent">discover</span>,
              <span class="cr-title-underline">understand</span> and cite your website?</h1>
            <p>Run an evidence-based GEO audit across technical access, content structure, entity trust and answerability.</p>
            <div class="cr-hero-chips" aria-label="Audit coverage">
              <span class="cr-hero-chip">Discoverability</span>
              <span class="cr-hero-chip">Citation readiness</span>
              <span class="cr-hero-chip">Entity trust</span>
              <span class="cr-hero-chip">Answerability</span>
            </div>
          </div>
          <div class="cr-area-grid" aria-label="Four audit areas">
            <article class="cr-area-card" style="--area-color: var(--cr-cyan); --entry-delay: 190ms">
              <div class="cr-area-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 18h16M6 15l4-5 3 3 5-7"/><path d="M17 6h1v1"/></svg></div>
              <div class="cr-area-label">Discover</div><div class="cr-area-description">Access and crawl signals</div>
            </article>
            <article class="cr-area-card" style="--area-color: var(--cr-primary); --entry-delay: 260ms">
              <div class="cr-area-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 4h9l3 3v13H6z"/><path d="M9 11h6M9 15h5M15 4v4h4"/></svg></div>
              <div class="cr-area-label">Understand</div><div class="cr-area-description">Content and citation structure</div>
            </article>
            <article class="cr-area-card" style="--area-color: var(--cr-mint); --entry-delay: 330ms">
              <div class="cr-area-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7z"/><path d="M9 12l2 2 4-4"/></svg></div>
              <div class="cr-area-label">Trust</div><div class="cr-area-description">Entity and authority signals</div>
            </article>
            <article class="cr-area-card" style="--area-color: var(--cr-warm); --entry-delay: 400ms">
              <div class="cr-area-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 5h14v10H9l-4 4z"/><path d="M9 9h6M9 12h4"/></svg></div>
              <div class="cr-area-label">Answer</div><div class="cr-area-description">Customer-question coverage</div>
            </article>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_audit_console_intro() -> None:
    """Label the existing form as the hero-adjacent audit console."""

    st.markdown("<div class='cr-audit-console-intro'>Start a website audit</div>", unsafe_allow_html=True)


def render_timeline(completed: set[str], active: str | None = None) -> None:
    """Render the existing audit state as a readable animated timeline."""

    steps = []
    for step_id, label in AUDIT_STEPS:
        state = "complete" if step_id in completed else "active" if step_id == active else "pending"
        marker = "✓" if state == "complete" else "•" if state == "active" else "○"
        steps.append(f"<div class='cr-timeline-step' data-state='{state}'>{marker} {safe_html(label)}</div>")
    st.markdown(f"<div class='cr-timeline'>{''.join(steps)}</div>", unsafe_allow_html=True)


def render_action_ticket(index: int, action: ActionCard, *, primary: bool = False) -> None:
    """Render a priority action as an evidence-backed audit ticket."""

    card_class = " cr-action-ticket-primary" if primary else ""
    delay = min(120 + index * 70, 520)
    st.markdown(
        f"""
        <article class="cr-action-ticket{card_class}" style="--entry-delay: {delay}ms">
          <div class="cr-ticket-topline">
            <div>
              <div class="cr-ticket-rank">ACTION {index:02d} · PRIORITY {action.priority_score}/100</div>
              <h3 class="cr-ticket-title">{safe_html(action.title)}</h3>
              <div class="cr-ticket-meta">{safe_html(action.category)} · {len(action.affected_urls)} affected page(s) · Impact: {safe_html(_impact_label(action.impact))} · Effort: {safe_html(_effort_label(action.effort))}</div>
            </div>
          </div>
          <p class="cr-ticket-body">{safe_html(action.why_it_matters)}</p>
          <p class="cr-ticket-body"><strong>Recommended fix:</strong> {safe_html(action.recommendation)}</p>
        </article>
        """,
        unsafe_allow_html=True,
    )
    if action.affected_urls:
        with st.expander(f"View {len(action.affected_urls)} affected page(s)", expanded=False):
            for url in action.affected_urls:
                st.write(url)
    if action.copy_paste_fix:
        st.caption("Copy-paste fix")
        st.code(action.copy_paste_fix, language="html")


def render_finding_card(finding: DiscoverabilityFinding, mode: ThemeMode) -> None:
    """Render a compact finding while retaining full evidence in the model."""

    severity = severity_style(finding.severity, mode)
    st.markdown(
        f"""
        <article class="cr-finding" style="--severity-color: {severity['color']}">
          <div class="cr-severity-bar" aria-hidden="true"></div>
          <div>
            <div class="cr-badge" style="color: {severity['color']}; border-color: {severity['color']}">{severity['symbol']} {severity['label']} · {safe_html(finding.confidence.value)} confidence</div>
            <h4>{safe_html(finding.title)}</h4>
            <div class="cr-ticket-meta">Affected URL: {safe_html(finding.affected_url)}</div>
          </div>
        </article>
        """,
        unsafe_allow_html=True,
    )
    for evidence in concise_evidence(finding):
        st.markdown(f"<div class='cr-evidence'><strong>Evidence:</strong> {safe_html(evidence)}</div>", unsafe_allow_html=True)
    st.caption(f"Why it matters: {finding.why_it_matters}")
    st.write(f"**Recommended action:** {finding.recommendation}")
    if finding.copy_paste_fix:
        st.code(finding.copy_paste_fix, language="html")
    st.caption(f"Impact: {_impact_label(finding.impact)} · Effort: {_effort_label(finding.effort)}")


def render_score_badge(percentage: float, mode: ThemeMode) -> None:
    """Show score status text and symbol, never color alone."""

    style = score_status_style(percentage, mode)
    st.markdown(
        f"<span class='cr-badge' style='color: {style['color']}; border-color: {style['color']}'>{style['symbol']} {style['label']}</span>",
        unsafe_allow_html=True,
    )


def _impact_label(value: int | None) -> str:
    if value is None:
        return "Not estimated"
    return "High" if value >= 4 else "Medium" if value >= 3 else "Low"


def _effort_label(value: int | None) -> str:
    if value is None:
        return "Not estimated"
    return "High" if value >= 4 else "Medium" if value >= 3 else "Low"
