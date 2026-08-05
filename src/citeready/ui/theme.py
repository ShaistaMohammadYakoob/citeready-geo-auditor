"""Theme tokens and visual status helpers shared by the Streamlit UI."""

from __future__ import annotations

from typing import Literal

from ..models import Severity


ThemeMode = Literal["light", "dark"]

# The palette is deliberately small: all component states are derived from the
# approved ocean colours with transparency, rather than introducing new hues.
LIGHT_TOKENS = {
    "background": "#F3F8FB",
    "surface": "#FFFFFF",
    "raised_surface": "#F3F8FB",
    "surface_hover": "rgba(125, 211, 252, 0.12)",
    "input_surface": "#FFFFFF",
    "code_surface": "#F3F8FB",
    "text": "#102A43",
    "muted": "#52677B",
    "border": "#D9E6EE",
    "border_strong": "#7DD3FC",
    "primary": "#0F8B8D",
    "primary_soft": "rgba(15, 139, 141, 0.12)",
    "on_primary": "#FFFFFF",
    "ripple": "rgba(255, 255, 255, 0.28)",
    "success": "#28A879",
    "success_soft": "rgba(40, 168, 121, 0.12)",
    "warning": "#E6A23C",
    "warning_soft": "rgba(230, 162, 60, 0.14)",
    "danger": "#D95D5D",
    "danger_soft": "rgba(217, 93, 93, 0.12)",
    "navy": "#102A43",
    "cyan": "#38BDF8",
    "mint": "#74D3AE",
    "sky": "#7DD3FC",
    "warm": "#F4B860",
    "shadow": "0 12px 30px rgba(16, 42, 67, 0.10)",
    "shadow_subtle": "0 5px 16px rgba(16, 42, 67, 0.08)",
    "shadow_hover": "0 18px 38px rgba(16, 42, 67, 0.16)",
    "plot_grid": "#D9E6EE",
}

DARK_TOKENS = {
    "background": "#071A2B",
    "surface": "#0E2438",
    "raised_surface": "#12304A",
    "surface_hover": "rgba(125, 211, 252, 0.12)",
    "input_surface": "#0A2033",
    "code_surface": "#0A2033",
    "text": "#EFF8FF",
    "muted": "#A9BDD0",
    "border": "#23425A",
    "border_strong": "#38BDF8",
    "primary": "#0F8B8D",
    "primary_soft": "rgba(15, 139, 141, 0.22)",
    "on_primary": "#FFFFFF",
    "ripple": "rgba(255, 255, 255, 0.20)",
    "success": "#28A879",
    "success_soft": "rgba(40, 168, 121, 0.18)",
    "warning": "#E6A23C",
    "warning_soft": "rgba(230, 162, 60, 0.18)",
    "danger": "#D95D5D",
    "danger_soft": "rgba(217, 93, 93, 0.18)",
    "navy": "#102A43",
    "cyan": "#38BDF8",
    "mint": "#74D3AE",
    "sky": "#7DD3FC",
    "warm": "#F4B860",
    "shadow": "0 13px 32px rgba(0, 0, 0, 0.26)",
    "shadow_subtle": "0 6px 18px rgba(0, 0, 0, 0.24)",
    "shadow_hover": "0 20px 42px rgba(0, 0, 0, 0.34)",
    "plot_grid": "#23425A",
}


def theme_tokens(mode: ThemeMode) -> dict[str, str]:
    """Return an immutable-by-convention copy of the active visual tokens."""

    return dict(DARK_TOKENS if mode == "dark" else LIGHT_TOKENS)


def css_variables(mode: ThemeMode) -> str:
    """Generate the variables consumed by every custom dashboard style."""

    tokens = theme_tokens(mode)
    declarations = "\n".join(f"  --cr-{name.replace('_', '-')}: {value};" for name, value in tokens.items())
    return f":root {{\n{declarations}\n}}"


def plotly_layout(mode: ThemeMode) -> dict[str, object]:
    """Return a legible transparent Plotly layout for the active theme."""

    tokens = theme_tokens(mode)
    return {
        "template": "plotly_dark" if mode == "dark" else "plotly_white",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": 'Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', "color": tokens["text"], "size": 13},
        "xaxis": {"gridcolor": tokens["plot_grid"], "linecolor": tokens["border"], "zerolinecolor": tokens["border"]},
        "yaxis": {"gridcolor": tokens["plot_grid"], "linecolor": tokens["border"], "zerolinecolor": tokens["border"]},
        "margin": {"l": 8, "r": 12, "t": 16, "b": 8},
    }


def score_status_style(percentage: float, mode: ThemeMode) -> dict[str, str]:
    """Return text and non-color status styling for score labels."""

    tokens = theme_tokens(mode)
    if percentage >= 90:
        return {"label": "Excellent", "symbol": "✓", "color": tokens["success"]}
    if percentage >= 75:
        return {"label": "Good", "symbol": "✓", "color": tokens["primary"]}
    if percentage >= 60:
        return {"label": "Needs Improvement", "symbol": "!", "color": tokens["warning"]}
    return {"label": "Poor", "symbol": "!", "color": tokens["danger"]}


def severity_style(severity: Severity | str, mode: ThemeMode) -> dict[str, str]:
    """Map severity to an accessible text label, symbol, and theme token."""

    tokens = theme_tokens(mode)
    value = severity.value if isinstance(severity, Severity) else severity.lower()
    if value == Severity.CRITICAL.value:
        return {"label": "Critical", "symbol": "!", "color": tokens["danger"]}
    if value == Severity.HIGH.value:
        return {"label": "High", "symbol": "!", "color": tokens["warm"]}
    if value == Severity.MEDIUM.value:
        return {"label": "Medium", "symbol": "!", "color": tokens["warning"]}
    if value == Severity.LOW.value:
        return {"label": "Low", "symbol": "i", "color": tokens["sky"]}
    return {"label": "Info", "symbol": "i", "color": tokens["muted"]}
