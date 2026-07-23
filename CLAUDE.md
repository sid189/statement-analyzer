Statement Analyzer
Goal

A learning-focused tool that ingests a public company's SEC filings, normalizes the three financial statements, verifies they articulate (interconnect) correctly, and computes ratios. The point is pedagogical: to make the accruals and the links between the income statement, balance sheet, and cash flow statement concrete and testable.

This is a library-first CLI tool, not a web app. Data flows one direction: identifier in → validated report out. No database, no server, no user accounts.

Data source

SEC EDGAR XBRL, specifically the companyfacts API: https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit-cik}.json

Ticker → CIK resolution uses https://www.sec.gov/files/company_tickers.json.
All SEC requests MUST send a descriptive User-Agent with contact info (SEC requirement). Set it via the SEC_USER_AGENT environment variable.
Raw responses are cached to data/cache/ so we never re-hit EDGAR while iterating. Cache is keyed by CIK and is not committed to git.
A hand-entered CSV of one company is kept as a known-good fixture for testing the articulation and ratio logic independently of parsing bugs.
Module boundaries (keep these separate)
ingest — fetch + cache raw filings; resolve ticker→CIK. (Phase 1)
normalize — map raw us-gaap tags to canonical line items. (Phase 2)
model — typed representation of IS / BS / CFS for a period. (Phase 2)
articulation — the pedagogical core: cross-statement checks. (Phase 3)
ratios — computed on the validated model. (Phase 4)
report — CLI/HTML output of numbers, ratios, and check results. (Phase 5)
Tech stack (deliberately boring)
Python 3.10+
httpx for HTTP (with retry/backoff). requests is an acceptable substitute.
pydantic for the typed statement models.
Decimal for all money — never float. Float rounding pollutes the articulation deltas and makes real reconciliation gaps indistinguishable from floating-point noise.
pytest for tests. Tests must not hit the network — mock the fetch layer and use the CSV fixture.
pandas only when multi-year trend tables arrive (Phase 5). Not before.
Output: rich for terminal tables first; Jinja2 HTML later if wanted.

No web framework, no database, no cloud. Every added dependency is surface area that isn't teaching accounting.

Build phases — do not start a phase until the previous one is green
Ingest — fetch and cache one company's companyfacts; resolve tickers. Done when: raw JSON lands on disk and re-runs are served from cache.
Normalize + model — map raw tags to canonical line items for one fiscal year; assemble typed statement models. Done when: a populated model prints.
Articulation — the cross-statement checks, tested against the CSV fixture where the answers are known. Done when: checks tie out on known-good data.
Ratios — liquidity, leverage, profitability, efficiency on the model.
Scale + report — multi-year, trends, output layer.

Build the Phase 3 checks against the CSV fixture FIRST, before trusting EDGAR-normalized data. Then, when a check fails on a real filing, you know the check is correct and the bug is in tag mapping — not the other way around.

Runtime workflow (what a single run does)
Resolve input (ticker → CIK, choose fiscal year).
Fetch filings through a disk-cache gate (hit → load; miss → GET + cache).
Normalize: when a concept has several filed values (restatements), take the most recently filed value for that period; map raw tags to line items; derive items that aren't tagged (e.g. gross profit = revenue − COGS).
Assemble typed models for the current AND prior period (articulation needs changes: ΔAR, ΔInventory, ΔAP).
Validate: run articulation checks. This stage does NOT transform data and does NOT halt on failure — it emits a report of deltas against a tolerance. The failures are the lesson; never suppress them.
Compute ratios on the validated model.
Render the report.
Articulation checks (the heart of Phase 3)

Each check reports a signed delta against a tolerance, not a pass/fail boolean.

Balance sheet balances: Assets = Liabilities + Equity.
Retained earnings roll-forward: RE_end = RE_begin + NetIncome − Dividends.
Cash ties out: ending cash on the CFS = cash line on the BS.
Indirect-method reconciliation: NetIncome + non-cash adjustments (depreciation) ± ΔworkingCapital (ΔAR, ΔInventory, ΔAP) = cash from operations. Recompute the working-capital deltas from two balance sheets and check them against the CFS. This check IS the accruals lesson. Expect real filings NOT to tie perfectly (rounding, reclassifications, unmapped items). The deltas show you what you haven't mapped yet.
Conventions
All money is Decimal. Parse straight from JSON strings/numbers into Decimal.
Canonical line-item names live in one place (Phase 2) and never change casually.
Every network call goes through the ingest layer so it can be cached & mocked.
Test target: Apple Inc., CIK 0000320193, ticker AAPL — real, messy data.
Commands
Install: pip install -e .
Run ingest: python -m statement_analyzer.cli AAPL --summary
Tests: pytest
Set UA: export SEC_USER_AGENT="statement-analyzer/0.1 (you@example.com)"