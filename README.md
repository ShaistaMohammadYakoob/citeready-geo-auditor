# CiteReady — GEO Visibility Auditor

CiteReady is a deterministic GEO (Generative Engine Optimization) auditor. It
checks whether a public website can be discovered, understood, and cited by
modern AI answer systems, then presents evidence-backed findings and a fully
transparent 100-point score.

The project includes a safe 12-page crawler, discoverability analysis,
citation-readiness checks, entity and trust signals, AI answerability analysis,
and a business-focused Streamlit dashboard. It does not use an LLM API.

## Dashboard

Run the professional business report UI:

```powershell
streamlit run app.py
```

The dashboard includes:

- URL validation and actual audit progress updates
- Light/dark visual modes that preserve the completed audit in the current session
- Executive, category, and rule-level score summaries
- Evidence-backed findings grouped by audit category
- Deduplicated priority actions, affected pages, impact, and effort
- Impact-versus-effort chart, AI answerability results, and page inventory
- Visible crawl warnings, sitemap completeness, and methodology limitations

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, create an app from the repository and select `app.py` as the entry point.
3. Use the repository root as the working directory and deploy with the included `requirements.txt`.
4. Optionally set `CITEREADY_REPOSITORY_URL` to show a repository link in the dashboard navigation and footer.

`requirements.txt` installs this repository as an editable package, so the
`src/citeready` imports work without setting `PYTHONPATH`. No secrets, database,
or system packages are required.

## CLI remains supported

The command-line analyzer is still available for smoke tests and detailed
technical output:

```powershell
$env:PYTHONPATH="src"
python -m citeready.cli https://example.com --show-score
```

## Screenshot placeholder

Add an approved dashboard screenshot here before final submission. No mock or
placeholder image is included in the repository.

## Known limitations

- The crawl is intentionally limited to 12 same-domain server-rendered HTML pages.
- Oversized resources and unavailable pages remain warnings rather than being retried without bounds.
- Heuristics are deterministic and evidence-based, but cannot guarantee ranking,
  citation, or placement in any AI engine.
- Dynamic client-rendered content may not be visible to the crawler.

## Development

### Create virtual environment

```powershell
python -m venv .venv
```

Windows

```powershell
.venv\Scripts\activate
```

Linux/macOS

```bash
source .venv/bin/activate
```

### Install runtime dependencies

```powershell
pip install -r requirements.txt
```

### Install development dependencies

```powershell
pip install -r requirements-dev.txt
```

### Run tests

```powershell
python -m pytest -q
```

### Run CLI

```powershell
$env:PYTHONPATH="src"
python -m citeready.cli https://example.com
```

### Show detailed findings

```powershell
$env:PYTHONPATH="src"
python -m citeready.cli https://example.com --show-findings
```

## Smoke test

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m citeready.cli https://example.com
```

Copy `.env.example` to `.env` to customize crawler settings.
