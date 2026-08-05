"""Restrained Plotly chart builders for the CiteReady report."""

from __future__ import annotations

import plotly.graph_objects as go

from ..dashboard import ActionCard
from ..models import CategoryScore
from .theme import ThemeMode, plotly_layout, theme_tokens


def category_comparison_chart(scores: list[CategoryScore], mode: ThemeMode) -> go.Figure:
    """Build a compact horizontal comparison chart for category percentages."""

    tokens = theme_tokens(mode)
    figure = go.Figure(
        go.Bar(
            x=[score.percentage for score in scores],
            y=[score.category.value for score in scores],
            orientation="h",
            marker_color=tokens["primary"],
            text=[f"{score.percentage:.0f}%" for score in scores],
            textposition="outside",
            hovertemplate="%{y}<br>%{x:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(**plotly_layout(mode), height=255, showlegend=False)
    figure.update_xaxes(range=[0, 100], ticksuffix="%", fixedrange=True)
    figure.update_yaxes(autorange="reversed", fixedrange=True)
    return figure


def impact_effort_chart(actions: list[ActionCard], mode: ThemeMode) -> go.Figure:
    """Build a readable impact-versus-effort chart with useful quadrant labels."""

    tokens = theme_tokens(mode)
    visible_actions = actions[:12]
    figure = go.Figure()
    if visible_actions:
        figure.add_trace(
            go.Scatter(
                x=[action.effort or 0 for action in visible_actions],
                y=[action.impact or 0 for action in visible_actions],
                mode="markers",
                marker={
                    "size": [max(10, min(26, 8 + len(action.affected_urls) * 3)) for action in visible_actions],
                    "color": tokens["primary"],
                    "line": {"color": tokens["surface"], "width": 1.5},
                    "opacity": 0.88,
                },
                customdata=[
                    [action.title, action.category, len(action.affected_urls), action.priority_score]
                    for action in visible_actions
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>Category: %{customdata[1]}<br>"
                    "Impact: %{y}/5<br>Effort: %{x}/5<br>Affected pages: %{customdata[2]}<br>"
                    "Priority score: %{customdata[3]}/100<extra></extra>"
                ),
            )
        )
    figure.update_layout(**plotly_layout(mode), height=350, showlegend=False)
    figure.update_xaxes(title="Effort", range=[0, 5.5], dtick=1, fixedrange=True)
    figure.update_yaxes(title="Impact", range=[0, 5.5], dtick=1, fixedrange=True)
    annotations = (
        (1.1, 4.95, "Quick wins"),
        (4.2, 4.95, "Strategic work"),
        (1.1, 0.55, "Maintenance"),
        (4.1, 0.55, "Lower priority"),
    )
    for x, y, text in annotations:
        figure.add_annotation(x=x, y=y, text=text, showarrow=False, font={"color": tokens["muted"], "size": 11})
    return figure
