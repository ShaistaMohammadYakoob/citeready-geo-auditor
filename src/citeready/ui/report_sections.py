"""Report sections composed from existing analysis and scoring output."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from ..models import AuditCategory, CrawlResult, Severity, SitemapAnalysisStatus
from .charts import category_comparison_chart, impact_effort_chart
from .components import render_action_ticket, render_finding_card, render_score_badge
from .dashboard_helpers import (
    action_cards_for_report,
    category_findings,
    category_summaries,
    findings_by_severity,
    inventory_filters,
    report_header_sentence,
    safe_html,
)
from .theme import ThemeMode, score_status_style


def render_report(result: CrawlResult, mode: ThemeMode) -> bool:
    """Render the complete report and return whether the user asked to rerun it."""

    rerun_requested = render_report_header(result)
    render_score_panel(result, mode)
    render_executive_summary(result)
    render_priority_actions(result)
    render_impact_effort(result, mode)
    render_category_tabs(result, mode)
    render_page_inventory(result)
    render_limitations(result)
    render_methodology()
    render_footer()
    return rerun_requested


def render_report_header(result: CrawlResult) -> bool:
    """Show audit identity, scope, and a deterministic status sentence."""

    is_partial = bool(result.warnings)
    if result.discoverability and result.discoverability.sitemap.status == SitemapAnalysisStatus.PARTIAL:
        is_partial = True
    left, right = st.columns((5, 1), vertical_alignment="bottom")
    with left:
        badge = " <span class='cr-pill'>! Partial analysis — review limitations</span>" if is_partial else " <span class='cr-pill'>✓ Audit completed</span>"
        st.markdown(
            f"""
            <section class="cr-report-header">
              <div>
                <div class="cr-eyebrow">Audited website{badge}</div>
                <div class="cr-report-domain">{safe_html(result.analyzed_url)}</div>
                <div class="cr-muted">Completed {result.completed_at.strftime('%d %b %Y, %H:%M UTC')} · {len(result.pages)}/{result.max_pages} pages crawled</div>
                <div class="cr-muted">{safe_html(report_header_sentence(result))}</div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with right:
        return st.button("Rerun audit", type="secondary", use_container_width=True, key="rerun-audit")


def render_score_panel(result: CrawlResult, mode: ThemeMode) -> None:
    """Render the primary overall score with comparable category progress bars."""

    if not result.scoring:
        st.warning("A transparent score was unavailable. Review the audit warnings and detailed findings.")
        return
    score = result.scoring
    status = score_status_style(score.overall_percentage, mode)
    category_rows = "".join(
        f"""
        <div class="cr-category-row">
          <div class="cr-category-row-label">{safe_html(item.category.value)}</div>
          <div class="cr-category-points">{_number(item.earned_points)}/{_number(item.maximum_points)} · {_number(item.percentage)}%</div>
          <div class="cr-progress-track" aria-label="{safe_html(item.category.value)} score {_number(item.percentage)} percent"><div class="cr-progress-fill" style="width: {max(0, min(100, item.percentage))}%"></div></div>
        </div>
        """
        for item in score.category_scores
    )
    st.markdown(
        f"""
        <section class="cr-score-panel">
          <div>
            <div class="cr-eyebrow">Overall GEO score</div>
            <div class="cr-score-number">{_number(score.overall_points)}<span class="cr-score-unit">/100</span></div>
            <div class="cr-score-label" style="color: {status['color']}">{status['symbol']} {status['label']}</div>
            <div class="cr-muted">{safe_html(_score_interpretation(score.overall_percentage))}</div>
          </div>
          <div>{category_rows}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_executive_summary(result: CrawlResult) -> None:
    """Render a compact owner-friendly summary from existing scoring output."""

    st.markdown("<h2 class='cr-section-title'>Executive summary</h2>", unsafe_allow_html=True)
    score = result.scoring
    strengths = score.top_strengths[:3] if score else []
    weaknesses = score.top_weaknesses[:3] if score else []
    actions = action_cards_for_report(result)[:3]
    columns = st.columns(3)
    content = (
        ("Strongest signals", strengths, "No scored strengths were available."),
        ("Biggest risks", weaknesses, "No evidence-backed risks were selected."),
        ("Start here Monday", [action.title for action in actions], "No action plan was selected."),
    )
    for column, (title, items, empty) in zip(columns, content, strict=True):
        with column:
            list_items = "".join(f"<div class='cr-summary-item'>{safe_html(item)}</div>" for item in items) or f"<div class='cr-summary-item'>{safe_html(empty)}</div>"
            st.markdown(
                f"<section class='cr-summary-column'><div class='cr-eyebrow'>{safe_html(title)}</div>{list_items}</section>",
                unsafe_allow_html=True,
            )


def render_priority_actions(result: CrawlResult) -> None:
    """Render the actionable plan with a restrained emphasis on the first ticket."""

    st.markdown("<h2 class='cr-section-title'>Priority actions</h2>", unsafe_allow_html=True)
    actions = action_cards_for_report(result)
    if not actions:
        st.info("No evidence-backed remediation actions were selected for this audit.")
        return
    for index, action in enumerate(actions[:5], start=1):
        render_action_ticket(index, action, primary=index == 1)
    if len(actions) > 5:
        with st.expander(f"Show {len(actions) - 5} additional action(s)"):
            for index, action in enumerate(actions[5:], start=6):
                render_action_ticket(index, action)


def render_impact_effort(result: CrawlResult, mode: ThemeMode) -> None:
    """Render a clutter-controlled action prioritization chart."""

    actions = action_cards_for_report(result)
    if not actions:
        return
    st.markdown("<h2 class='cr-section-title'>Impact vs effort</h2>", unsafe_allow_html=True)
    st.plotly_chart(
        impact_effort_chart(actions, mode),
        use_container_width=True,
        config={"displayModeBar": False, "responsive": True},
    )
    st.caption("Quick wins have high impact and lower effort. The chart shows up to 12 actions to remain readable.")


def render_category_tabs(result: CrawlResult, mode: ThemeMode) -> None:
    """Render category score, rule, and severity-grouped evidence details."""

    st.markdown("<h2 class='cr-section-title'>Category details</h2>", unsafe_allow_html=True)
    summaries = {item["category"]: item for item in category_summaries(result)}
    finding_groups = category_findings(result)
    labels = ("Discoverability", "Citation readiness", "Entity & Trust", "Answerability")
    categories = (
        AuditCategory.DISCOVERABILITY,
        AuditCategory.CITATION_READINESS,
        AuditCategory.ENTITY_TRUST,
        AuditCategory.ANSWERABILITY,
    )
    tabs = st.tabs(labels)
    for tab, category in zip(tabs, categories, strict=True):
        with tab:
            summary = summaries.get(category)
            if summary:
                left, right = st.columns((1, 4), vertical_alignment="center")
                with left:
                    st.metric("Score", f"{_number(summary['earned_points'])}/{_number(summary['maximum_points'])}")
                    render_score_badge(float(summary["percentage"]), mode)
                with right:
                    st.write(summary["interpretation"])
                with st.expander("Rule breakdown", expanded=False):
                    for rule in summary["rule_breakdown"]:
                        st.markdown(
                            f"**{rule.title}** — {_number(rule.earned_points)}/{_number(rule.max_points)} · {rule.status.value}"
                        )
                        st.caption(f"{rule.reason} · Linked evidence: {len(rule.linked_finding_ids)} item(s)")
            else:
                st.info("Score data was unavailable for this category.")
            _render_tab_findings(finding_groups[category], mode)
            if category == AuditCategory.ANSWERABILITY:
                render_answerability_matrix(result)


def _render_tab_findings(findings, mode: ThemeMode) -> None:
    if not findings:
        st.write("No actionable findings were detected in this category.")
        return
    for severity, grouped_findings in findings_by_severity(findings).items():
        if not grouped_findings:
            continue
        with st.expander(f"{severity.value.title()} findings ({len(grouped_findings)})", expanded=severity in {Severity.CRITICAL, Severity.HIGH}):
            for finding in grouped_findings:
                with st.expander(f"{finding.title} — {finding.affected_url}", expanded=False):
                    render_finding_card(finding, mode)


def render_answerability_matrix(result: CrawlResult) -> None:
    """Render answerability as a structured matrix with detail expanders."""

    if not result.answerability:
        st.info("AI answerability analysis was unavailable.")
        return
    st.markdown("#### Answerability matrix")
    rows = [
        {
            "Question": item.question.label,
            "Status": item.status.value,
            "Confidence": item.confidence.value,
            "Extracted answer": item.answer_excerpt or "—",
            "Source": item.supporting_urls[0] if item.supporting_urls else "—",
        }
        for item in result.answerability.results
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with st.expander("Detailed answerability reasoning"):
        for item in result.answerability.results:
            st.markdown(f"**{item.question.label}** — {item.status.value}")
            st.caption(f"Reason: {item.explanation}")
            st.write(f"Recommended action: {item.recommendation}")
            if item.conflicting_excerpt:
                st.write(f"Conflicting excerpt: {item.conflicting_excerpt}")


def render_page_inventory(result: CrawlResult) -> None:
    """Render filters for operational page-level audit review."""

    st.markdown("<h2 class='cr-section-title'>Page inventory</h2>", unsafe_allow_html=True)
    filters = inventory_filters(result)
    selected = st.selectbox("Show pages", options=list(filters), key="page-inventory-filter")
    rows = filters[selected]
    if not rows:
        st.info("No pages match this filter.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_limitations(result: CrawlResult) -> None:
    """Keep crawl limits and incomplete analysis visible near the report bottom."""

    with st.expander("Warnings and limitations", expanded=bool(result.warnings)):
        st.write(
            f"This audit crawled at most {result.max_pages} important same-domain server-rendered HTML pages. "
            "It uses deterministic checks and cannot guarantee AI ranking or citation."
        )
        if result.discoverability and result.discoverability.sitemap.status == SitemapAnalysisStatus.PARTIAL:
            sitemap = result.discoverability.sitemap
            st.warning(
                f"Sitemap analysis is partial: {len(sitemap.successfully_parsed_sitemap_files)} file(s) parsed, "
                f"{len(sitemap.skipped_sitemap_files)} skipped, and URL totals may be incomplete."
            )
        if result.warnings:
            for warning in result.warnings:
                location = f" ({warning.url})" if warning.url else ""
                st.warning(f"{warning.message}{location}")
        else:
            st.caption("No crawler warnings were recorded. The page limit and heuristic limitations still apply.")


def render_methodology() -> None:
    """Explain deterministic GEO scope in an accessible collapsed section."""

    with st.expander("Methodology", expanded=bool(st.session_state.pop("show_methodology", False))):
        st.markdown(
            "CiteReady checks whether a website is accessible to crawlers, structured for clear extraction, "
            "connected to an identifiable organization or publisher, and able to answer core visitor questions."
        )
        st.markdown(
            "The GEO score has four transparent 25-point categories. Rule details show points, reasons, and "
            "evidence counts. Incomplete sitemaps, unavailable pages, and crawler limits remain visible."
        )
        st.markdown(
            "This is deterministic heuristic analysis. It does not use a generative AI model and cannot promise "
            "ranking, citation, or placement in any AI answer engine."
        )


def render_footer() -> None:
    """Render a factual footer without adding fictional company information."""

    repository_url = os.getenv("CITEREADY_REPOSITORY_URL")
    repository = f" · <a href='{safe_html(repository_url)}' target='_blank'>Repository</a>" if repository_url else ""
    st.markdown(
        f"<footer class='cr-footer'>CiteReady — evidence-based GEO auditing{repository} · Methodology · v0.1.0</footer>",
        unsafe_allow_html=True,
    )


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def _score_interpretation(percentage: float) -> str:
    if percentage >= 90:
        return "Your audited foundation is strong and consistently easy for AI systems to interpret."
    if percentage >= 75:
        return "Your site has a good foundation; focused fixes can make its evidence easier to retrieve and cite."
    if percentage >= 60:
        return "Important signals are present, but targeted gaps are limiting consistent AI understanding."
    return "Material evidence and accessibility gaps are likely limiting reliable AI visibility."
