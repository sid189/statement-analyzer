"""Configuration constants and paths.

Everything the ingest layer needs to talk to SEC EDGAR politely, plus where to
cache what comes back. Values that a user might reasonably change are read from
environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- SEC politeness -------------------------------------------------------
# SEC requires a descriptive User-Agent that identifies you and includes a
# contact address. Override this with the SEC_USER_AGENT env var before running
# against the live API. The default is a placeholder and should be changed.
DEFAULT_USER_AGENT = "statement-analyzer/0.1 (contact: you@example.com)"


def user_agent() -> str:
    """Return the User-Agent to send with SEC requests."""
    return os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT)


# --- Paths ----------------------------------------------------------------
# Project root is two levels up from this file: src/statement_analyzer/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Cache directory. Overridable via SA_CACHE_DIR (useful for tests).
CACHE_DIR = Path(os.environ.get("SA_CACHE_DIR", PROJECT_ROOT / "data" / "cache"))


# --- SEC endpoints --------------------------------------------------------
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


# --- Retry / timeout ------------------------------------------------------
REQUEST_TIMEOUT = 30.0   # seconds
MAX_RETRIES = 4          # attempts before giving up
BACKOFF_BASE = 1.0       # seconds; wait = BACKOFF_BASE * 2**attempt
