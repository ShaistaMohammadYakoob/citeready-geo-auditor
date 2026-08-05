# CiteReady — GEO Visibility Auditor

Phase 1 provides the safe website-crawling foundation for the auditor. It can
normalize a public URL, crawl up to 12 useful same-domain HTML pages, and
extract the content and metadata required by later audit phases.

No scoring or Streamlit interface is included yet.

## Smoke test

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m citeready.cli https://example.com
```

Copy `.env.example` to `.env` to customize crawler settings.
