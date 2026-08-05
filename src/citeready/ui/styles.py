"""Variable-driven visual system for CiteReady's premium analytics UI."""

from __future__ import annotations

from .animations import animation_css
from .theme import ThemeMode, css_variables


def dashboard_css(mode: ThemeMode) -> str:
    """Return the complete theme-aware dashboard stylesheet.

    The CSS changes how existing Streamlit output is presented; it does not
    alter crawling, scoring, report content, or session-state behavior.
    """

    return f"""
    <style>
    {css_variables(mode)}
    {animation_css()}

    /* Foundations and safe Streamlit chrome refinement. */
    .stApp, [data-testid="stAppViewContainer"] {{
      background: var(--cr-background);
      color: var(--cr-text);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .block-container {{ max-width: 1280px; padding: .7rem 1.35rem 3.5rem; }}
    [data-testid="stHeader"] {{ background: transparent; border: 0; }}
    [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p {{ color: var(--cr-text); }}
    [data-testid="stMarkdownContainer"] p {{ font-size: .92rem; line-height: 1.6; }}
    h1, h2, h3, h4 {{ color: var(--cr-text); letter-spacing: -.035em; }}
    [data-testid="stMetric"] {{ background: transparent; border: 0; padding: 0; }}
    [data-testid="stMetricValue"] {{ color: var(--cr-text); font-size: 1.88rem; font-weight: 760; font-variant-numeric: tabular-nums; letter-spacing: -.055em; }}
    [data-testid="stMetricLabel"], .cr-eyebrow {{ color: var(--cr-muted); font-size: .67rem; font-weight: 780; letter-spacing: .10em; text-transform: uppercase; }}
    [data-testid="stCaptionContainer"] {{ color: var(--cr-muted); }}

    /* One aligned sticky navigation surface. :has scopes this only to the nav row. */
    div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) {{
      position: sticky; top: .45rem; z-index: 90; align-items: center;
      min-height: 58px; margin: 0 0 1.1rem; padding: .46rem .55rem .46rem .85rem;
      background: color-mix(in srgb, var(--cr-background) 86%, transparent);
      border: 1px solid var(--cr-border); border-radius: 13px;
      box-shadow: var(--cr-shadow-subtle); backdrop-filter: blur(18px);
      animation: cr-nav-enter 360ms ease-out both;
    }}
    .cr-nav-brand {{ display: flex; align-items: center; gap: .65rem; min-height: 42px; }}
    .cr-logo-mark {{
      display: grid; width: 30px; height: 30px; place-items: center; color: var(--cr-on-primary);
      background: linear-gradient(135deg, var(--cr-primary), var(--cr-cyan)); border: 1px solid var(--cr-cyan);
      border-radius: 9px; font-size: .74rem; font-weight: 830; letter-spacing: -.06em;
    }}
    .cr-wordmark {{ color: var(--cr-text); font-size: 1rem; font-weight: 800; letter-spacing: -.05em; }}
    .cr-product-label {{ margin-top: .07rem; color: var(--cr-muted); font-size: .61rem; font-weight: 760; letter-spacing: .085em; text-transform: uppercase; }}
    .cr-nav-link-label {{ color: var(--cr-muted); font-size: .78rem; font-weight: 720; white-space: nowrap; }}
    .cr-theme-control {{ min-width: 108px; }}
    div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) .stButton > button,
    div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) [data-testid="stLinkButton"] a {{
      min-height: 34px; padding: .34rem .6rem; color: var(--cr-text); background: transparent;
      border-color: transparent; box-shadow: none; font-size: .76rem;
    }}
    div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) .stButton > button:hover,
    div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) [data-testid="stLinkButton"] a:hover {{
      color: var(--cr-primary); background: var(--cr-primary-soft); border-color: transparent; box-shadow: none;
    }}
    [data-testid="stSegmentedControl"] {{ min-width: 128px; }}
    [data-testid="stSegmentedControl"] [role="radiogroup"] {{
      display: flex; gap: 2px; padding: 3px; background: var(--cr-raised-surface);
      border: 1px solid var(--cr-border); border-radius: 9px;
    }}
    [data-testid="stSegmentedControl"] label {{
      min-height: 28px; padding: .26rem .42rem; color: var(--cr-muted) !important;
      border-radius: 6px; font-size: .66rem; font-weight: 730; line-height: 1;
      transition: color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }}
    [data-testid="stSegmentedControl"] label:has(input:checked) {{
      color: var(--cr-on-primary) !important; background: linear-gradient(135deg, var(--cr-primary), var(--cr-cyan));
      box-shadow: 0 2px 6px rgba(7, 26, 43, .18);
    }}

    /* Native controls share clear, theme-aware input and focus states. */
    [data-testid="stForm"] {{
      margin: 0 0 1.35rem; padding: .82rem .95rem .18rem; background: var(--cr-surface);
      border: 1px solid var(--cr-border); border-radius: 14px; box-shadow: var(--cr-shadow); animation: cr-fade-up 460ms 160ms ease-out both;
    }}
    .cr-audit-console-intro {{ margin: 1.1rem 0 -.05rem; color: var(--cr-muted); font-size: .75rem; font-weight: 760; letter-spacing: .08em; text-transform: uppercase; }}
    [data-testid="stTextInput"] label, [data-testid="stSelectbox"] label {{ color: var(--cr-muted); font-size: .73rem; font-weight: 760; letter-spacing: .025em; }}
    [data-testid="stTextInput"] input, [data-baseweb="select"] > div {{
      min-height: 43px; color: var(--cr-text) !important; background: var(--cr-input-surface) !important;
      border: 1px solid var(--cr-border-strong) !important; border-radius: 9px !important; box-shadow: none !important;
      transition: border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }}
    [data-testid="stTextInput"] input:focus, [data-baseweb="select"] > div:focus-within {{
      border-color: var(--cr-cyan) !important; box-shadow: 0 0 0 3px var(--cr-primary-soft) !important;
    }}
    [data-testid="stTextInput"] input::placeholder {{ color: var(--cr-muted); opacity: .78; }}
    [data-baseweb="select"] *, [data-baseweb="popover"] * {{ color: var(--cr-text) !important; }}
    [data-baseweb="popover"], [data-baseweb="menu"] {{ background: var(--cr-surface) !important; border: 1px solid var(--cr-border) !important; }}
    [role="option"]:hover {{ background: var(--cr-surface-hover) !important; }}
    .stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stLinkButton"] a {{
      position: relative; min-height: 40px; overflow: hidden; color: var(--cr-text); background: var(--cr-surface);
      border: 1px solid var(--cr-border-strong); border-radius: 9px; box-shadow: none; font-size: .81rem; font-weight: 730;
      transition: transform 180ms ease, background 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }}
    [data-testid="stFormSubmitButton"] > button {{ color: var(--cr-on-primary); background: linear-gradient(135deg, var(--cr-primary), var(--cr-cyan)); border-color: var(--cr-cyan); }}
    .stButton > button:hover, [data-testid="stLinkButton"] a:hover {{ background: var(--cr-surface-hover); border-color: var(--cr-primary); transform: translateY(-1px); box-shadow: var(--cr-shadow-subtle); }}
    [data-testid="stFormSubmitButton"] > button:hover {{ color: var(--cr-on-primary); border-color: var(--cr-sky); transform: translateY(-2px); box-shadow: var(--cr-shadow-hover); }}
    [data-testid="stFormSubmitButton"] > button::before {{ content: ""; position: absolute; inset: 0; width: 45%; background: linear-gradient(90deg, transparent, var(--cr-ripple), transparent); transform: translateX(-130%); }}
    [data-testid="stFormSubmitButton"] > button:hover::before {{ animation: cr-light-sweep 520ms ease-out; }}
    .stButton > button:active::after, [data-testid="stFormSubmitButton"] > button:active::after {{ content: ""; position: absolute; inset: 0; background: radial-gradient(circle at center, var(--cr-ripple), transparent 62%); animation: cr-ripple 180ms ease-out; }}
    button:focus-visible, input:focus-visible, a:focus-visible {{ outline: 2px solid var(--cr-cyan) !important; outline-offset: 2px !important; }}

    /* Hero and its four quiet, colourful audit-area cards. */
    .cr-hero {{
      position: relative; display: grid; grid-template-columns: minmax(0, 1.12fr) minmax(350px, .88fr); gap: 1.5rem;
      overflow: hidden; margin: .5rem 0 0; padding: clamp(1.55rem, 3.6vw, 2.7rem); isolation: isolate;
      background: linear-gradient(125deg, var(--cr-navy), var(--cr-primary), var(--cr-navy)); background-size: 210% 210%;
      border: 1px solid rgba(125, 211, 252, .36); border-radius: 18px; box-shadow: var(--cr-shadow); animation: cr-mesh-shift 14s ease-in-out infinite;
    }}
    .cr-hero::before, .cr-hero::after {{ content: ""; position: absolute; z-index: -1; border-radius: 999px; filter: blur(4px); opacity: .5; }}
    .cr-hero::before {{ width: 310px; height: 310px; top: -190px; right: 12%; background: radial-gradient(circle, var(--cr-cyan), transparent 66%); }}
    .cr-hero::after {{ width: 270px; height: 270px; bottom: -170px; left: 34%; background: radial-gradient(circle, var(--cr-mint), transparent 67%); }}
    .cr-hero-copy {{ max-width: 690px; padding-top: .32rem; }}
    .cr-hero .cr-eyebrow {{ color: var(--cr-sky); animation: cr-fade-up 360ms 80ms ease-out both; }}
    .cr-hero-title {{ max-width: 730px; margin: .42rem 0 .75rem; color: var(--cr-on-primary); font-size: clamp(2.3rem, 4.7vw, 4rem); font-weight: 760; line-height: 1.04; letter-spacing: -.065em; animation: cr-fade-up 480ms 150ms ease-out both; }}
    .cr-title-accent {{ color: var(--cr-mint); }}
    .cr-title-underline {{ background: linear-gradient(90deg, var(--cr-cyan), var(--cr-mint)); background-clip: text; color: transparent; border-bottom: 2px solid var(--cr-mint); }}
    .cr-hero-copy p {{ max-width: 615px; margin: 0; color: var(--cr-text); font-size: .98rem; line-height: 1.62; animation: cr-fade-up 520ms 220ms ease-out both; }}
    .cr-hero-chips {{ display: flex; flex-wrap: wrap; gap: .42rem; margin-top: 1.1rem; animation: cr-fade-up 600ms 290ms ease-out both; }}
    .cr-hero-chip {{ padding: .28rem .52rem; color: var(--cr-on-primary); background: rgba(7, 26, 43, .28); border: 1px solid rgba(239, 248, 255, .30); border-radius: 999px; font-size: .70rem; font-weight: 720; }}
    .cr-area-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .7rem; align-self: end; }}
    .cr-area-card {{
      min-height: 132px; padding: .88rem; background: rgba(7, 26, 43, .48); border: 1px solid color-mix(in srgb, var(--area-color) 62%, transparent);
      border-radius: 12px; box-shadow: 0 8px 20px rgba(7, 26, 43, .14); animation: cr-fade-up 500ms var(--entry-delay) ease-out both;
      transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }}
    .cr-area-card:hover {{ border-color: var(--area-color); transform: translateY(-3px); box-shadow: 0 14px 26px rgba(7, 26, 43, .24); }}
    .cr-area-icon {{ display: grid; width: 27px; height: 27px; place-items: center; color: var(--area-color); border: 1px solid color-mix(in srgb, var(--area-color) 70%, transparent); border-radius: 8px; }}
    .cr-area-icon svg {{ width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }}
    .cr-area-label {{ margin-top: .72rem; color: var(--cr-on-primary); font-size: .78rem; font-weight: 760; }}
    .cr-area-description {{ margin-top: .22rem; color: var(--cr-text); font-size: .69rem; line-height: 1.42; }}

    /* Report framework, score, and category cards. */
    .cr-report-header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin: 1.55rem 0 .8rem; animation: cr-fade-up 360ms ease-out both; }}
    .cr-report-domain {{ margin: .18rem 0 .28rem; color: var(--cr-text); font-size: 1.5rem; font-weight: 750; letter-spacing: -.045em; overflow-wrap: anywhere; }}
    .cr-pill, .cr-badge {{ display: inline-flex; align-items: center; gap: .3rem; width: fit-content; padding: .23rem .5rem; color: var(--cr-muted); background: var(--cr-raised-surface); border: 1px solid var(--cr-border); border-radius: 999px; font-size: .68rem; font-weight: 750; line-height: 1.2; }}
    .cr-muted {{ color: var(--cr-muted); font-size: .87rem; line-height: 1.55; }}
    .cr-score-panel {{ display: grid; grid-template-columns: minmax(225px, .68fr) minmax(330px, 1.32fr); gap: 2rem; padding: 1.45rem 1.55rem; margin: .4rem 0 .85rem; background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: 16px; box-shadow: var(--cr-shadow); animation: cr-fade-up 520ms ease-out both; }}
    .cr-score-number {{ color: var(--cr-text); font-size: clamp(3.8rem, 8vw, 5.7rem); font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -.1em; line-height: .86; animation: cr-score-reveal 650ms 100ms ease-out both; }}
    .cr-score-unit {{ color: var(--cr-muted); font-size: 1rem; font-weight: 680; letter-spacing: 0; }}
    .cr-score-label {{ display: inline-flex; align-items: center; margin: .75rem 0 .42rem; padding: .30rem .58rem; background: var(--cr-primary-soft); border: 1px solid var(--cr-border); border-radius: 999px; font-size: .81rem; font-weight: 780; }}
    .cr-score-facts {{ display: flex; flex-wrap: wrap; gap: .42rem; margin-top: .82rem; }}
    .cr-score-facts span {{ padding: .22rem .42rem; color: var(--cr-muted); background: var(--cr-raised-surface); border: 1px solid var(--cr-border); border-radius: 999px; font-size: .68rem; font-weight: 700; }}
    .cr-category-row {{ display: grid; grid-template-columns: minmax(140px, 1fr) auto; gap: .48rem .8rem; align-items: center; margin-bottom: .72rem; }}
    .cr-category-row-label {{ color: var(--cr-text); font-size: .82rem; font-weight: 700; }}
    .cr-category-points {{ color: var(--cr-muted); font-size: .73rem; font-variant-numeric: tabular-nums; text-align: right; }}
    .cr-progress-track {{ grid-column: 1 / -1; height: 7px; overflow: hidden; background: var(--cr-raised-surface); border: 1px solid var(--cr-border); border-radius: 999px; }}
    .cr-progress-fill {{ height: 100%; background: linear-gradient(90deg, var(--cr-primary), var(--cr-cyan)); border-radius: inherit; transform-origin: left; animation: cr-progress-fill 650ms 180ms ease-out both; }}
    .cr-category-card-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .7rem; margin: 0 0 1.15rem; }}
    .cr-category-card {{ padding: .88rem .95rem; background: var(--cr-surface); border: 1px solid var(--cr-border); border-top: 3px solid var(--category-color); border-radius: 12px; box-shadow: var(--cr-shadow-subtle); animation: cr-fade-up 480ms var(--entry-delay) ease-out both; transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease; }}
    .cr-category-card:hover {{ border-color: var(--category-color); transform: translateY(-3px); box-shadow: var(--cr-shadow-hover); }}
    .cr-category-card-title {{ color: var(--cr-muted); font-size: .69rem; font-weight: 760; letter-spacing: .05em; text-transform: uppercase; }}
    .cr-category-card-points {{ margin: .35rem 0 .10rem; color: var(--cr-text); font-size: 1.4rem; font-weight: 770; letter-spacing: -.05em; }}
    .cr-category-card-meta {{ color: var(--cr-muted); font-size: .72rem; }}
    .cr-category-card .cr-progress-track {{ height: 5px; margin-top: .64rem; }}
    .cr-category-card .cr-progress-fill {{ background: var(--category-color); }}
    .cr-section-title {{ margin: 1.55rem 0 .72rem; color: var(--cr-text); font-size: 1.35rem; font-weight: 760; letter-spacing: -.04em; }}
    .cr-summary-column {{ min-height: 150px; padding: .98rem 1rem; background: var(--cr-surface); border: 1px solid var(--cr-border); border-top: 3px solid var(--summary-color); border-radius: 12px; box-shadow: var(--cr-shadow-subtle); transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease; }}
    .cr-summary-column:hover {{ border-color: var(--summary-color); transform: translateY(-2px); box-shadow: var(--cr-shadow-hover); }}
    .cr-summary-item {{ padding: .48rem 0; color: var(--cr-text); border-bottom: 1px solid var(--cr-border); font-size: .82rem; line-height: 1.42; }}
    .cr-summary-item:last-child {{ border-bottom: 0; }}

    /* Tickets, findings, charts, tables, and operational detail. */
    .cr-action-ticket {{ margin: .6rem 0; padding: 1rem 1.05rem; background: var(--cr-surface); border: 1px solid var(--cr-border); border-left: 4px solid var(--cr-primary); border-radius: 12px; box-shadow: var(--cr-shadow-subtle); animation: cr-slide-in 460ms var(--entry-delay) ease-out both; transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease; }}
    .cr-action-ticket:hover {{ border-color: var(--cr-cyan); transform: translateY(-2px); box-shadow: var(--cr-shadow-hover); }}
    .cr-action-ticket-primary {{ border-left-color: var(--cr-cyan); background: var(--cr-surface); }}
    .cr-ticket-topline {{ display: flex; align-items: flex-start; justify-content: space-between; gap: .8rem; }}
    .cr-ticket-rank {{ color: var(--cr-primary); font-size: .65rem; font-weight: 800; letter-spacing: .10em; }}
    .cr-ticket-title {{ margin: .17rem 0 .25rem; color: var(--cr-text); font-size: 1rem; font-weight: 750; letter-spacing: -.025em; }}
    .cr-ticket-meta {{ color: var(--cr-muted); font-size: .72rem; line-height: 1.45; }}
    .cr-ticket-body {{ margin: .56rem 0 0; color: var(--cr-muted); font-size: .84rem; line-height: 1.5; }}
    .cr-finding {{ display: grid; grid-template-columns: 3px 1fr; gap: .72rem; padding: .85rem 0; border-bottom: 1px solid var(--cr-border); }}
    .cr-finding:last-child {{ border-bottom: 0; }}
    .cr-severity-bar {{ width: 3px; min-height: 100%; background: var(--severity-color); border-radius: 3px; }}
    .cr-finding h4 {{ margin: 0 0 .28rem; color: var(--cr-text); font-size: .92rem; font-weight: 720; }}
    .cr-evidence {{ margin: .48rem 0; padding: .55rem .66rem; color: var(--cr-muted); background: var(--cr-code-surface); border: 1px solid var(--cr-border); border-radius: 8px; font-size: .78rem; line-height: 1.45; }}
    [data-testid="stExpander"] {{ background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: 10px; box-shadow: none; transition: border-color 180ms ease, box-shadow 180ms ease; }}
    [data-testid="stExpander"]:hover {{ border-color: var(--cr-border-strong); box-shadow: var(--cr-shadow-subtle); }}
    [data-testid="stExpander"] details summary {{ color: var(--cr-text); font-size: .85rem; font-weight: 680; }}
    [data-baseweb="tab-list"] {{ gap: .25rem; border-bottom: 1px solid var(--cr-border); }}
    [data-baseweb="tab"] {{ color: var(--cr-muted) !important; font-size: .80rem; font-weight: 700; padding: .55rem .7rem; }}
    [aria-selected="true"][data-baseweb="tab"] {{ color: var(--cr-primary) !important; }}
    [data-testid="stPlotlyChart"] {{ padding: .35rem; background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: 12px; box-shadow: var(--cr-shadow-subtle); animation: cr-fade-up 560ms ease-out both; }}
    .cr-table-wrap {{ overflow-x: auto; background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: 10px; }}
    .cr-table {{ width: 100%; min-width: 700px; border-collapse: collapse; color: var(--cr-text); font-size: .79rem; }}
    .cr-table th {{ padding: .64rem .72rem; color: var(--cr-muted); background: var(--cr-raised-surface); border-bottom: 1px solid var(--cr-border); font-size: .66rem; font-weight: 780; letter-spacing: .075em; text-align: left; text-transform: uppercase; white-space: nowrap; }}
    .cr-table td {{ padding: .64rem .72rem; border-bottom: 1px solid var(--cr-border); line-height: 1.44; vertical-align: top; }}
    .cr-table tr:last-child td {{ border-bottom: 0; }}
    .cr-table tr:hover td {{ background: var(--cr-surface-hover); }}
    .cr-table-url {{ max-width: 360px; overflow: hidden; color: var(--cr-primary); text-overflow: ellipsis; white-space: nowrap; }}
    .cr-answer-status {{ display: inline-flex; padding: .18rem .42rem; border: 1px solid var(--status-color); border-radius: 999px; color: var(--status-color); background: var(--status-soft); font-size: .68rem; font-weight: 750; white-space: nowrap; }}
    [data-testid="stDataFrame"] {{ border: 1px solid var(--cr-border); border-radius: 10px; overflow: hidden; background: var(--cr-surface); }}
    [data-testid="stDataFrame"] [role="grid"], [data-testid="stDataFrame"] canvas {{ background: var(--cr-surface) !important; }}
    [data-testid="stCodeBlock"] pre, [data-testid="stCode"] pre, pre {{ color: var(--cr-text) !important; background: var(--cr-code-surface) !important; border: 1px solid var(--cr-border) !important; border-radius: 8px !important; font-size: .78rem !important; }}
    [data-testid="stAlert"] {{ color: var(--cr-text); background: var(--cr-surface); border: 1px solid var(--cr-border); border-radius: 10px; }}

    /* Audit progress and footer. */
    .cr-timeline {{ display: grid; grid-template-columns: repeat(7, minmax(105px, 1fr)); gap: .35rem; margin: .75rem 0 1rem; animation: cr-fade-up 380ms ease-out both; }}
    .cr-timeline-step {{ min-height: 43px; padding: .48rem .55rem; color: var(--cr-muted); background: var(--cr-raised-surface); border: 1px solid var(--cr-border); border-radius: 8px; font-size: .7rem; line-height: 1.28; transition: border-color 180ms ease, color 180ms ease, background 180ms ease; }}
    .cr-timeline-step[data-state="complete"] {{ color: var(--cr-success); background: var(--cr-success-soft); border-color: var(--cr-success); }}
    .cr-timeline-step[data-state="active"] {{ color: var(--cr-cyan); background: var(--cr-primary-soft); border-color: var(--cr-cyan); animation: cr-active-pulse 1.4s ease-in-out infinite; }}
    .cr-footer {{ margin-top: 1.85rem; padding: 1rem 0; color: var(--cr-muted); border-top: 1px solid var(--cr-border); font-size: .74rem; }}
    .cr-footer a {{ color: var(--cr-primary); text-decoration: none; }}

    @media (max-width: 880px) {{
      div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) {{ position: static; }}
      .cr-hero, .cr-score-panel {{ grid-template-columns: 1fr; gap: 1rem; }}
      .cr-category-card-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 680px) {{
      .block-container {{ padding: .45rem .80rem 2.5rem; }}
      div[data-testid="stHorizontalBlock"]:has(.cr-nav-brand) {{ padding: .45rem .5rem; }}
      .cr-product-label, .cr-nav-link-label {{ display: none; }}
      [data-testid="stSegmentedControl"] {{ min-width: 74px; }}
      [data-testid="stSegmentedControl"] label {{ padding: .26rem .34rem; font-size: 0; }}
      [data-testid="stSegmentedControl"] label:has(input[value="light"])::after {{ content: "☀"; font-size: .73rem; }}
      [data-testid="stSegmentedControl"] label:has(input[value="dark"])::after {{ content: "🌙"; font-size: .73rem; }}
      .cr-hero {{ padding: 1.35rem; border-radius: 14px; }}
      .cr-hero-title {{ font-size: 2.25rem; }}
      .cr-area-grid, .cr-category-card-grid {{ grid-template-columns: 1fr; }}
      .cr-timeline {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .cr-score-panel {{ padding: 1.05rem; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important; }}
    }}
    </style>
    """
