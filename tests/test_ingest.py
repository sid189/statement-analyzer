"""Phase 1 tests. No network: the ``_get_json`` seam is monkeypatched and the
cache is redirected to a tmp dir.
"""
from __future__ import annotations

import pytest

from statement_analyzer import config, ingest

FAKE_TICKER_MAP = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}

FAKE_FACTS = {
    "entityName": "Apple Inc.",
    "cik": 320193,
    "facts": {"us-gaap": {"Assets": {}, "Liabilities": {}}},
}


@pytest.fixture(autouse=True)
def _tmp_cache(monkeypatch, tmp_path):
    """Point the cache at a fresh tmp dir for every test."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)


def test_resolve_cik_pads_numeric():
    assert ingest.resolve_cik("320193") == "0000320193"
    assert ingest.resolve_cik("0000320193") == "0000320193"


def test_resolve_cik_from_ticker(monkeypatch):
    monkeypatch.setattr(ingest, "_get_json", lambda url: FAKE_TICKER_MAP)
    assert ingest.resolve_cik("aapl") == "0000320193"
    assert ingest.resolve_cik("MSFT") == "0000789019"


def test_resolve_cik_unknown_ticker_raises(monkeypatch):
    monkeypatch.setattr(ingest, "_get_json", lambda url: FAKE_TICKER_MAP)
    with pytest.raises(ingest.IngestError):
        ingest.resolve_cik("NOPE")


def test_fetch_uses_cache_on_second_call(monkeypatch):
    calls = {"n": 0}

    def fake_get(url: str):
        calls["n"] += 1
        if "company_tickers" in url:
            return FAKE_TICKER_MAP
        return FAKE_FACTS

    monkeypatch.setattr(ingest, "_get_json", fake_get)

    first = ingest.fetch_company_facts("AAPL")
    calls_after_first = calls["n"]          # 1 ticker map + 1 facts = 2
    second = ingest.fetch_company_facts("AAPL")

    assert first == second == FAKE_FACTS
    assert calls_after_first == 2
    assert calls["n"] == calls_after_first  # second call hit the cache, no fetch


def test_force_refresh_bypasses_cache(monkeypatch):
    calls = {"n": 0}

    def fake_get(url: str):
        calls["n"] += 1
        if "company_tickers" in url:
            return FAKE_TICKER_MAP
        return FAKE_FACTS

    monkeypatch.setattr(ingest, "_get_json", fake_get)

    ingest.fetch_company_facts("AAPL")
    n1 = calls["n"]
    ingest.fetch_company_facts("AAPL", force_refresh=True)
    assert calls["n"] > n1  # refresh went back to the wire
