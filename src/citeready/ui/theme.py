"""Theme tokens and visual status helpers shared by the Streamlit UI."""

from __future__ import annotations

from typing import Literal

from ..models import Severity


ThemeMode = Literal["light", "dark"]

LIGHT_TOKENS = {
    "background": "#F5F6F8",
    "surface": "#FFFFFF",
    "raised_surface": "#FAFAFB",
    "text": "#16181D",
    "muted": "#626875",
    "border": "#E2E5EA",
    "primary": "#315CFF",
    "success": "#177D52",
    "warning": "#A86209",
    "danger": "#B42335",
    "shadow": "0 8px 24px rgba(22, 24, 29, 0.06)",
    "plot_grid": "#E9ECF1",
}

DARK_TOKENS = {
    "background": "#0E1014",
    "surface": "#15181E",
    "raised_surface": "#1B1F27",
    "text": "#F1F3F7",
    "muted": "#9BA3B1",
    "border": "#2B303A",
    "primary": "#7894FF",
    "success": "#55B98A",
    "warning": "#E0A354",
    "danger": "#EF7A88",
    "shadow": "0 8px 24px rgba(0, 0, 0, 0.24)",
    "plot_grid": "#2B303A",
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
        return {"label": "High", "symbol": "!", "color": tokens["danger"]}
    if value == Severity.MEDIUM.value:
        return {"label": "Medium", "symbol": "!", "color": tokens["warning"]}
    if value == Severity.LOW.value:
        return {"label": "Low", "symbol": "i", "color": tokens["primary"]}
    return {"label": "Info", "symbol": "i", "color": tokens["muted"]}
