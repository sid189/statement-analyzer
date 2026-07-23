# Statement Analyzer

A learning-focused CLI that pulls a public company's SEC filings straight from
EDGAR, normalizes the three financial statements, checks whether they
actually articulate (tie together) correctly, and computes ratios. The point
is pedagogical: to make the accruals and the links between the income
statement, balance sheet, and cash flow statement concrete and testable,
against real, messy filings rather than a textbook example.

Identifier in, validated report out. No database, no server, no web
framework — a library-first CLI tool. See `CLAUDE.md` for the full design
philosophy and build history.

## Setup

```bash
pip install -e .
export SEC_USER_AGENT="statement-analyzer/0.1 (you@example.com)"
```

SEC requires every request to carry a descriptive `User-Agent` with contact
info — any real-looking email works, it isn't verified. Without this env var
set, requests fall back to a placeholder UA and SEC may reject them.

## Usage

Everything goes through one entry point, followed by a ticker or CIK and one
flag:

```bash
statement-analyzer AAPL --summary               # what got fetched
statement-analyzer AAPL --list-years            # fiscal years available
statement-analyzer AAPL --year 2023             # one year's full statements
statement-analyzer AAPL --articulate 2023       # do the statements tie out?
statement-analyzer AAPL --ratios 2023           # liquidity/leverage/profitability/efficiency
statement-analyzer AAPL --report 2019 2023      # multi-year trend report (all of the above)
```

`--report` is the one to reach for first — it prints rich tables for all
three statements, all four ratio groups, and the articulation checks, side
by side across however many years you ask for.

Ticker or numeric CIK both work (`AAPL` or `320193`). The pipeline has been
verified end-to-end against five real companies: `AAPL`, `MSFT`, `WMT`,
`JNJ`, `KO`. Other tickers should mostly work too, but expect more
`— (unmapped)` cells until the tag map is extended for that company's
specific conventions (see `normalize.py`'s tag tables).

Also available: `python -m statement_analyzer.cli AAPL --report 2019 2023`
works identically to the `statement-analyzer` console script.

### Things to know

- The first run for a new company hits the network and takes a few seconds;
  every run after that is served instantly from `data/cache/` (gitignored,
  keyed by CIK).
- `--refresh` on any command bypasses the cache and re-fetches from SEC.
- A blank/`—` cell means "unmapped or not computable," never zero — that
  distinction matters throughout the project (see below).
- Articulation checks report a signed dollar delta against a 1%-of-base
  tolerance, never a pass/fail flag. A large delta is often a real lesson,
  not a bug — e.g. Apple's retained-earnings roll-forward drifts by tens of
  billions because it retires repurchased stock against retained earnings,
  which the textbook formula doesn't model.

## Project layout

| Module | Job |
|---|---|
| `ingest` | Fetch + disk-cache raw `companyfacts` JSON; resolve ticker → CIK |
| `normalize` | Map raw us-gaap XBRL tags to canonical line items, resolving restatements |
| `model` | Typed (pydantic, `Decimal`-only) representation of one fiscal year's IS/BS/CFS |
| `articulation` | Cross-statement checks: does Assets = Liabilities + Equity, does cash tie out, etc. |
| `ratios` | Liquidity, leverage, profitability, and efficiency ratios on a validated model |
| `report` | Multi-year assembly (pandas) and rich-terminal rendering |

## Testing

```bash
pytest
```

No test hits the network — everything runs against small hand-built or
hand-entered fixtures (`tests/fixtures/known_good.csv` is a fully
tie-out-by-construction two-year company, used to prove the articulation and
ratio math is correct before it's ever pointed at real EDGAR data).

## Learning material

`docs/learning/` has one short PDF per phase (`phase1_ingest.pdf` through
`phase5_report.pdf`), each built from real findings surfaced while writing
this tool rather than generic explanation — the SEC `fy`/`fp` field trap,
Walmart and Coca-Cola never tagging a total `Liabilities` concept, Apple's
retained-earnings check drifting as buybacks accumulate, and so on. Rebuild
them after changing normalize.py's tag map or re-pulling company data with:

```bash
pip install fpdf2 matplotlib   # not project dependencies -- content-gen only
export SEC_USER_AGENT="statement-analyzer/0.1 (you@example.com)"
python docs/generate_data.py     # pulls real numbers via ingest/normalize/articulation/ratios
python docs/generate_charts.py   # renders the PNGs each PDF embeds
python docs/generate_pdfs.py     # assembles the five PDFs
```
# statement-analyzer
