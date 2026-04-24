# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

硅基流动免费模型筛选工具 (SiliconFlow Query) - A CLI tool to discover and query free models from SiliconFlow platform. The tool scrapes the official website to identify free models (input/output price = ¥0.000000/ K Tokens) and provides a local database for querying.

## Architecture

```
src/siliconflow_query/
├── cli.py          # Typer CLI entry point with lazy-loaded database
├── models.py       # ModelInfo dataclass + FreeModelsDB (JSON-backed)
├── scraper.py      # Playwright async scraper (requires login)
├── api_client.py   # SiliconFlow API client for verification
├── config.py       # Environment config (SILICONFLOW_API_KEY)
└── free_models.json # Local database of free models
```

**Data Flow:**
1. `sfq scrape` → Playwright scrapes cloud.siliconflow.cn → identifies free models via price sidebar
2. `sfq update` → scraped_models.json → free_models.json (local DB)
3. `sfq list/show/search` → reads free_models.json → displays via Rich tables

**Free Model Detection:**
- Models with `(Free)` suffix in DisplayName field (HTML embedded)
- Models with `¥0.000000/ K Tokens` price format in sidebar (requires clicking card)
- Deprecated models are marked with `is_deprecated` flag but **NOT filtered out** during scraping
- Use `--skip-detail-check` to skip detail page price check (faster but less complete)

## Commands

```bash
# Install (development)
pip install -e ".[dev]"

# Run CLI
sfq --help
sfq list
sfq scrape                    # Opens browser for login
sfq scrape --skip-login       # Skip login (limited data)
sfq scrape --headless         # Headless mode

# Run tests
pytest

# Install Playwright browsers (first-time setup)
playwright install chromium
```

## Key Patterns

**Lazy Loading (cli.py):**
```python
_DB: Optional[FreeModelsDB] = None

def get_db() -> FreeModelsDB:
    global _DB
    if _DB is None:
        _DB = FreeModelsDB()
    return _DB
```

**Scraper Entry Point:**
- `run_scrape()` orchestrates: dashboard scrape → detail page price check → public page supplement
- Returns `List[ScrapedModel]` with `is_free` and `is_deprecated` flags

**Data Files:**
- `free_models.json`: Local DB with `last_updated`, `source`, `models[]`
- `scraped_models.json`: Output from scraper with `free_models[]` and `all_models[]`
