# CiteReady — GEO Visibility Auditor

Phase 1 provides the safe website-crawling foundation for the auditor. It can
normalize a public URL, crawl up to 12 useful same-domain HTML pages, and
extract the content and metadata required by later audit phases.

Phase 2 adds an unscored discoverability engine for robots.txt, sitemap.xml,
canonical tags, meta-robots directives, and llms.txt. No scoring or Streamlit
interface is included yet.

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
