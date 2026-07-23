"""Phase 1 — ingestion.

Fetch a company's raw ``companyfacts`` JSON from SEC EDGAR and cache it to disk,
resolving a ticker to a CIK first if needed. Nothing here interprets the
accounting data; it only gets the raw bytes and caches them. Every network call
lives behind :func:`_get_json` so it can be mocked in tests and rate-limited
politely.

Public API:
    resolve_cik(identifier) -> str            # "AAPL" or "320193" -> "0000320193"
    fetch_company_facts(identifier) -> dict   # cached raw companyfacts JSON
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from . import config


class IngestError(RuntimeError):
    """Raised when a filing cannot be fetched or a ticker cannot be resolved."""


# --- cache helpers --------------------------------------------------------
def _cache_path(name: str) -> Path:
    """Return the path for a cache file named ``name``, creating the dir."""
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return config.CACHE_DIR / name


def _read_cache(path: Path) -> dict[str, Any] | None:
    """Return parsed JSON from ``path``, or None if it doesn't exist."""
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _write_cache(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``path`` as JSON, atomically via a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(path)


# --- network layer (the one place that touches the wire) ------------------
def _get_json(url: str) -> dict[str, Any]:
    """GET ``url`` and return parsed JSON, retrying on transient failures.

    Retries on 429 and 5xx with exponential backoff. Any other non-200 is a
    hard error. This is the single seam mocked in tests.
    """
    headers = {
        "User-Agent": config.user_agent(),
        "Accept-Encoding": "gzip, deflate",
    }
    last_exc: Exception | None = None
    for attempt in range(config.MAX_RETRIES):
        try:
            resp = httpx.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        except httpx.RequestError as exc:
            last_exc = exc
            time.sleep(config.BACKOFF_BASE * (2 ** attempt))
            continue

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(config.BACKOFF_BASE * (2 ** attempt))
            continue
        raise IngestError(f"SEC returned HTTP {resp.status_code} for {url}")

    raise IngestError(
        f"Failed to fetch {url} after {config.MAX_RETRIES} attempts"
    ) from last_exc


# --- ticker -> CIK --------------------------------------------------------
def _load_ticker_map(*, force_refresh: bool = False) -> dict[str, Any]:
    """Return SEC's ticker->CIK map, cached to disk."""
    path = _cache_path("company_tickers.json")
    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached
    data = _get_json(config.TICKER_MAP_URL)
    _write_cache(path, data)
    return data


def resolve_cik(identifier: str, *, force_refresh: bool = False) -> str:
    """Resolve a ticker or CIK to a zero-padded 10-digit CIK string.

    A purely numeric identifier is treated as a CIK and zero-padded. Anything
    else is looked up (case-insensitively) in SEC's ticker map.
    """
    identifier = identifier.strip()
    if not identifier:
        raise IngestError("Empty identifier")

    if identifier.isdigit():
        return identifier.zfill(10)

    ticker_map = _load_ticker_map(force_refresh=force_refresh)
    wanted = identifier.upper()
    for entry in ticker_map.values():
        if str(entry.get("ticker", "")).upper() == wanted:
            return str(entry["cik_str"]).zfill(10)

    raise IngestError(f"Could not resolve ticker {identifier!r} to a CIK")


# --- companyfacts ---------------------------------------------------------
def fetch_company_facts(
    identifier: str, *, force_refresh: bool = False
) -> dict[str, Any]:
    """Return the raw ``companyfacts`` JSON for a ticker or CIK.

    Served from the on-disk cache when present unless ``force_refresh`` is set.
    """
    cik = resolve_cik(identifier, force_refresh=force_refresh)
    path = _cache_path(f"companyfacts_CIK{cik}.json")

    if not force_refresh:
        cached = _read_cache(path)
        if cached is not None:
            return cached

    url = config.COMPANY_FACTS_URL.format(cik=cik)
    data = _get_json(url)
    _write_cache(path, data)
    return data
