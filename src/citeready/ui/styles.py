"""Custom CSS for a compact, accessible CiteReady analytics interface."""

from __future__ import annotations

from .theme import ThemeMode, css_variables


def dashboard_css(mode: ThemeMode) -> str:
    """Return the complete variable-driven dashboard stylesheet."""

    return f"""
    <style>
    {css_variables(mode)}
    .stApp {{ background: var(--cr-background); color: var(--cr-text); font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .block-container {{ max-width: 1240px; padding: 1.35rem 1.25rem 3.5rem; }}
    [data-testid="stHeader"] {{ background: color-mix(in srgb, var(--cr-background) 92%, transparent); }}
    [data-testid="stMetric"] {{ background: transparent; border: 0; padding: 0; }}
    [data-testid="stMetricValue"] {{ color: var(--cr-text); font-variant-numeric: tabular-nums; font-size: 1.8rem; letter-spacing: -0.04em; }}
    [data-testid="stMetricLabel"], .cr-eyebrow {{ color: var(--cr-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
    [data-testid="stExpander"] {{ border: 1px solid var(--cr-border); border-radius: 12px; background: var(--cr-surface); }}
    [data-testid="stDataFrame"] {{ border: 1px solid var(--cr-border); border-radius: 12px; overflow: hidden; }}
    .cr-nav {{ position: sticky; top: 0; z-index: 40; display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.7rem 0 0.9rem; border-bottom: 1px solid var(--cr-border); background: var(--cr-background); }}
    .cr-wordmark {{ color: var(--cr-text); font-size: 1.15rem; font-weight: 760; letter-spacing: -0.04em; }}
    .cr-product-label {{ color: var(--cr-muted); font-size: 0.73rem; font-weight: 650; letter-spacing: 0.07em; text-transform: uppercase; }}
    .cr-hero {{ display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(260px, .7fr); gap: 1rem; align-items: stretch; margin: 1.35rem 0 1.1rem; }}
    .cr-hero-copy, .cr-area-map, .cr-score-panel, .cr-summary-column, .cr-action-ticket {{ background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: 12px; box-shadow: var(--cr-shadow); }}
    .cr-hero-copy {{ padding: 1.55rem; }}
    .cr-hero-title {{ margin: .25rem 0 .65rem; color: var(--cr-text); font-size: clamp(2rem, 4vw, 2.5rem); font-weight: 720; line-height: 1.08; letter-spacing: -0.045em; }}
    .cr-hero-copy p, .cr-muted {{ color: var(--cr-muted); font-size: .96rem; line-height: 1.55; }}
    .cr-area-map {{ padding: 1.1rem 1.25rem; }}
    .cr-area-row {{ display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: .77rem 0; border-bottom: 1px solid var(--cr-border); }}
    .cr-area-row:last-child {{ border-bottom: 0; }}
    .cr-area-row strong {{ font-size: .91rem; color: var(--cr-text); }}
    .cr-area-row span {{ color: var(--cr-muted); font-size: .78rem; }}
    .cr-report-header {{ display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem; margin: 1.5rem 0 1rem; }}
    .cr-report-domain {{ margin: .12rem 0; color: var(--cr-text); font-size: 1.55rem; font-weight: 690; letter-spacing: -0.035em; word-break: break-word; }}
    .cr-pill, .cr-badge {{ display: inline-flex; align-items: center; gap: .32rem; width: fit-content; border: 1px solid var(--cr-border); border-radius: 999px; padding: .22rem .55rem; color: var(--cr-muted); font-size: .73rem; font-weight: 690; line-height: 1.15; }}
    .cr-score-panel {{ display: grid; grid-template-columns: minmax(220px, .7fr) minmax(300px, 1.3fr); gap: 1.75rem; padding: 1.45rem; margin: .8rem 0 1.35rem; }}
    .cr-score-number {{ color: var(--cr-text); font-size: clamp(3.2rem, 8vw, 4.75rem); font-weight: 760; letter-spacing: -0.08em; font-variant-numeric: tabular-nums; line-height: .92; }}
    .cr-score-unit {{ color: var(--cr-muted); font-size: 1.05rem; font-weight: 650; letter-spacing: 0; }}
    .cr-score-label {{ margin: .7rem 0 .45rem; font-size: 1.05rem; font-weight: 720; }}
    .cr-category-row {{ display: grid; grid-template-columns: minmax(125px, 1fr) minmax(80px, auto); gap: .7rem; align-items: center; margin-bottom: .85rem; }}
    .cr-category-row-label {{ color: var(--cr-text); font-size: .86rem; font-weight: 650; }}
    .cr-category-points {{ color: var(--cr-muted); font-size: .78rem; font-variant-numeric: tabular-nums; text-align: right; }}
    .cr-progress-track {{ grid-column: 1 / -1; height: 7px; border-radius: 999px; background: var(--cr-raised-surface); border: 1px solid var(--cr-border); overflow: hidden; }}
    .cr-progress-fill {{ height: 100%; border-radius: inherit; background: var(--cr-primary); transition: width 200ms ease; }}
    .cr-section-title {{ margin: 1.55rem 0 .75rem; color: var(--cr-text); font-size: 1.42rem; font-weight: 700; letter-spacing: -0.03em; }}
    .cr-summary-column {{ min-height: 176px; padding: 1rem 1.05rem; }}
    .cr-summary-item {{ padding: .55rem 0; color: var(--cr-text); font-size: .87rem; line-height: 1.42; border-bottom: 1px solid var(--cr-border); }}
    .cr-summary-item:last-child {{ border-bottom: 0; }}
    .cr-action-ticket {{ padding: 1rem 1.05rem; margin: .65rem 0; border-left: 4px solid var(--cr-primary); }}
    .cr-action-ticket-primary {{ border-left-width: 5px; box-shadow: 0 10px 28px color-mix(in srgb, var(--cr-primary) 10%, transparent); }}
    .cr-ticket-topline {{ display: flex; align-items: flex-start; justify-content: space-between; gap: .75rem; }}
    .cr-ticket-rank {{ color: var(--cr-primary); font-size: .75rem; font-weight: 760; letter-spacing: .08em; }}
    .cr-ticket-title {{ margin: .18rem 0 .3rem; color: var(--cr-text); font-size: 1.04rem; font-weight: 710; letter-spacing: -.02em; }}
    .cr-ticket-meta {{ color: var(--cr-muted); font-size: .77rem; }}
    .cr-ticket-body {{ color: var(--cr-muted); font-size: .88rem; line-height: 1.48; }}
    .cr-severity-bar {{ width: 3px; min-height: 100%; border-radius: 3px; background: var(--severity-color); }}
    .cr-finding {{ display: grid; grid-template-columns: 3px 1fr; gap: .7rem; padding: .85rem 0; border-bottom: 1px solid var(--cr-border); }}
    .cr-finding:last-child {{ border-bottom: 0; }}
    .cr-finding h4 {{ margin: 0 0 .28rem; color: var(--cr-text); font-size: .96rem; font-weight: 690; }}
    .cr-evidence {{ margin: .55rem 0; padding: .55rem .7rem; border-left: 2px solid var(--cr-border); background: var(--cr-raised-surface); color: var(--cr-muted); font-size: .82rem; line-height: 1.45; }}
    .cr-timeline {{ display: grid; grid-template-columns: repeat(7, minmax(105px, 1fr)); gap: .35rem; margin: .8rem 0 1.25rem; }}
    .cr-timeline-step {{ padding: .52rem .58rem; border: 1px solid var(--cr-border); border-radius: 10px; color: var(--cr-muted); background: var(--cr-raised-surface); font-size: .73rem; line-height: 1.3; }}
    .cr-timeline-step[data-state="complete"] {{ color: var(--cr-success); border-color: color-mix(in srgb, var(--cr-success) 35%, var(--cr-border)); }}
    .cr-timeline-step[data-state="active"] {{ color: var(--cr-primary); border-color: var(--cr-primary); }}
    .cr-footer {{ margin-top: 2rem; padding: 1.1rem 0; border-top: 1px solid var(--cr-border); color: var(--cr-muted); font-size: .78rem; }}
    .stButton > button, [data-testid="stFormSubmitButton"] > button {{ border-radius: 10px; font-weight: 680; transition: transform 180ms ease, box-shadow 180ms ease; }}
    .stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {{ transform: translateY(-1px); box-shadow: var(--cr-shadow); }}
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div {{ border-radius: 10px; }}
    a:focus, button:focus, input:focus {{ outline: 2px solid var(--cr-primary) !important; outline-offset: 2px !important; }}
    @media (max-width: 760px) {{
      .block-container {{ padding-left: .9rem; padding-right: .9rem; }}
      .cr-hero, .cr-score-panel {{ grid-template-columns: 1fr; }}
      .cr-timeline {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .cr-nav {{ position: static; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important; }}
    }}
    </style>
    """
