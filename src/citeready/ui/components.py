"""Reusable Streamlit components for the refined CiteReady interface."""

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
    """Render the compact navigation and persistent light/dark preference."""

    left, middle, right = st.columns((5, 2, 3), vertical_alignment="center")
    with left:
        st.markdown(
            "<div class='cr-nav'><div><div class='cr-wordmark'>CiteReady</div>"
            "<div class='cr-product-label'>GEO Visibility Auditor</div></div></div>",
            unsafe_allow_html=True,
        )
    with middle:
        if st.button("Methodology", use_container_width=True, key="methodology-nav"):
            st.session_state["show_methodology"] = True
    with right:
        is_dark = st.toggle("Dark mode", value=mode == "dark", key="theme-toggle")
        on_theme_change(is_dark)
        repository_url = os.getenv("CITEREADY_REPOSITORY_URL")
        if repository_url:
            st.link_button("GitHub ↗", repository_url, use_container_width=True)


def render_hero() -> None:
    """Render the editorial two-column audit introduction."""

    st.markdown(
        """
        <div class="cr-hero">
          <section class="cr-hero-copy">
            <div class="cr-eyebrow">Evidence-based GEO audit</div>
            <h1 class="cr-hero-title">Can AI engines understand and cite your website?</h1>
            <p>Audit the technical, content, trust, and answerability signals that make a website easier for modern AI systems to discover and explain.</p>
          </section>
          <aside class="cr-area-map" aria-label="Four audit areas">
            <div class="cr-eyebrow">Four audit areas</div>
            <div class="cr-area-row"><strong>Discover</strong><span>Access &amp; crawl signals</span></div>
            <div class="cr-area-row"><strong>Understand</strong><span>Content structure</span></div>
            <div class="cr-area-row"><strong>Trust</strong><span>Entity &amp; authority</span></div>
            <div class="cr-area-row"><strong>Answer</strong><span>Customer questions</span></div>
          </aside>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_timeline(completed: set[str], active: str | None = None) -> None:
    """Render a real state timeline with completed, active, and pending labels."""

    steps = []
    for step_id, label in AUDIT_STEPS:
        state = "complete" if step_id in completed else "active" if step_id == active else "pending"
        marker = "✓" if state == "complete" else "•" if state == "active" else "○"
        steps.append(f"<div class='cr-timeline-step' data-state='{state}'>{marker} {safe_html(label)}</div>")
    st.markdown(f"<div class='cr-timeline'>{''.join(steps)}</div>", unsafe_allow_html=True)


def render_action_ticket(index: int, action: ActionCard, *, primary: bool = False) -> None:
    """Render a priority action as a compact evidence-backed audit ticket."""

    card_class = " cr-action-ticket-primary" if primary else ""
    st.markdown(
        f"""
        <article class="cr-action-ticket{card_class}">
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
    """Render a compact finding while retaining full evidence in the underlying model."""

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
