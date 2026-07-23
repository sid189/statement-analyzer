"""Command-line entry point.

Phase 1 fetches and caches. Phase 2 normalizes into typed statement models.
Phase 3 adds the articulation checks. Phase 4 adds ratios. Phase 5 adds the
multi-year rich report.

    python -m statement_analyzer.cli AAPL --summary
    python -m statement_analyzer.cli AAPL --list-years
    python -m statement_analyzer.cli AAPL --year 2023
    python -m statement_analyzer.cli AAPL --articulate 2023
    python -m statement_analyzer.cli AAPL --ratios 2023
    python -m statement_analyzer.cli AAPL --report 2019 2023
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from . import articulation, ingest, normalize, ratios as ratios_module
from . import report as report_module


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="statement-analyzer",
        description="Fetch, cache, and normalize a company's SEC companyfacts filings.",
    )
    parser.add_argument(
        "identifier",
        help="Ticker (e.g. AAPL) or CIK (e.g. 320193).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore the cache and re-fetch from SEC.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a short summary of what was fetched.",
    )
    parser.add_argument(
        "--list-years",
        action="store_true",
        help="List fiscal years available to normalize.",
    )
    parser.add_argument(
        "--year",
        type=int,
        metavar="FY",
        help="Normalize this fiscal year and print the populated model.",
    )
    parser.add_argument(
        "--articulate",
        type=int,
        metavar="FY",
        help="Run articulation checks for this fiscal year against the prior year.",
    )
    parser.add_argument(
        "--ratios",
        type=int,
        metavar="FY",
        help="Compute liquidity/leverage/profitability/efficiency ratios for this fiscal year.",
    )
    parser.add_argument(
        "--report",
        nargs=2,
        type=int,
        metavar=("FROM_FY", "TO_FY"),
        help="Print a multi-year rich report (statements, ratios, articulation) for FROM_FY..TO_FY inclusive.",
    )
    return parser


def _print_articulation(checks: list[articulation.ArticulationCheck]) -> None:
    for check in checks:
        print(check.name)
        if check.missing_inputs:
            print(f"  not computable -- missing: {', '.join(check.missing_inputs)}")
            continue
        verdict = "within tolerance" if check.within_tolerance else "OUTSIDE tolerance"
        pct = (check.delta / abs(check.base) * 100) if check.base else Decimal("0")
        print(f"  delta: {check.delta:,} ({pct:.2f}% of base {check.base:,}) -- {verdict}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        facts = ingest.fetch_company_facts(
            args.identifier, force_refresh=args.refresh
        )
    except ingest.IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.list_years:
        years = normalize.available_fiscal_years(facts)
        print(" ".join(str(y) for y in years) if years else "No fiscal years found.")
        return 0

    if args.year is not None:
        try:
            period = normalize.build_period(facts, args.year)
        except normalize.NormalizeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(period.summary())
        return 0

    if args.articulate is not None:
        try:
            current = normalize.build_period(facts, args.articulate)
            prior = normalize.build_period(facts, args.articulate - 1)
        except normalize.NormalizeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        checks = articulation.run_checks(current, prior)
        _print_articulation(checks)
        return 0

    if args.ratios is not None:
        try:
            current = normalize.build_period(facts, args.ratios)
        except normalize.NormalizeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        try:
            prior = normalize.build_period(facts, args.ratios - 1)
        except normalize.NormalizeError:
            # Average-balance ratios (ROA, ROE, turnover) will show as not
            # computable; everything else still prints.
            prior = None
        print(ratios_module.compute_ratios(current, prior).summary())
        return 0

    if args.report is not None:
        from_fy, to_fy = sorted(args.report)
        multi_year = report_module.assemble_multi_year(facts, list(range(from_fy, to_fy + 1)))
        if not multi_year.periods:
            print("error: no fiscal years in that range could be normalized", file=sys.stderr)
            return 1
        report_module.print_report(multi_year)
        return 0

    if args.summary:
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        print(f"Entity:  {facts.get('entityName', '?')}")
        print(f"CIK:     {facts.get('cik', '?')}")
        print(f"us-gaap concepts tagged: {len(us_gaap)}")
    else:
        print(f"Cached companyfacts for {args.identifier}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
