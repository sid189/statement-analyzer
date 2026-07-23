"""Phase 5 tests: multi-year assembly and the pandas/rich rendering layer.
No network -- built on the synthetic two_year_facts fixture and the
known-good CSV fixture already used by earlier phases.
"""
from __future__ import annotations

import io
from decimal import Decimal

from rich.console import Console

from statement_analyzer import articulation, ratios as ratios_mod, report

from csv_fixture import load_known_good


def test_assemble_multi_year_builds_periods_ratios_and_checks(two_year_facts):
    result = report.assemble_multi_year(two_year_facts, [2022, 2023])

    assert set(result.periods) == {2022, 2023}
    assert result.skipped_years == ()
    # 2022 has no prior year in this fixture, so it gets ratios (current-only
    # ones, at least) but no articulation entry.
    assert 2022 in result.ratio_sets
    assert 2022 not in result.articulation_checks
    # 2023 has 2022 as prior, so both are populated.
    assert 2023 in result.ratio_sets
    assert 2023 in result.articulation_checks
    assert len(result.articulation_checks[2023]) == 4


def test_assemble_multi_year_skips_years_not_in_filings(two_year_facts):
    result = report.assemble_multi_year(two_year_facts, [1999, 2022, 2023])

    assert result.skipped_years == (1999,)
    assert set(result.periods) == {2022, 2023}


def test_income_statement_df_shape_and_values():
    periods = load_known_good()

    df = report.income_statement_df(periods)

    assert list(df.columns) == [2022, 2023]
    assert df.loc["Revenue", 2023] == Decimal("1200")
    assert df.loc["Revenue", 2022] == Decimal("1000")
    # unmapped-in-fixture line items surface as None, not zero or NaN-as-float
    assert df.loc["Interest expense", 2023] == Decimal("12")


def test_ratio_group_df_shape():
    periods = load_known_good()
    ratio_sets = {
        year: ratios_mod.compute_ratios(periods[year], periods.get(year - 1))
        for year in periods
    }

    df = report.liquidity_df(ratio_sets)

    assert list(df.columns) == [2022, 2023]
    assert df.loc["Current ratio", 2023] == Decimal("900") / Decimal("240")


def test_articulation_df_cells_are_check_objects():
    periods = load_known_good()
    checks_by_year = {2023: articulation.run_checks(periods[2023], periods[2022])}

    df = report.articulation_df(checks_by_year)

    cell = df.loc["Balance sheet balances (Assets = Liabilities + Equity)", 2023]
    assert isinstance(cell, articulation.ArticulationCheck)
    assert cell.delta == Decimal("0")


def test_render_statement_table_smoke():
    periods = load_known_good()
    df = report.income_statement_df(periods)
    console = Console(file=io.StringIO(), force_terminal=False, width=120)

    report.render_statement_table(console, "Income Statement ($)", df)

    output = console.file.getvalue()
    assert "Income Statement" in output
    assert "Revenue" in output
    assert "1,200" in output


def test_render_articulation_table_smoke():
    periods = load_known_good()
    checks_by_year = {2023: articulation.run_checks(periods[2023], periods[2022])}
    df = report.articulation_df(checks_by_year)
    console = Console(file=io.StringIO(), force_terminal=False, width=160)

    report.render_articulation_table(console, "Articulation Checks ($ delta)", df)

    output = console.file.getvalue()
    assert "Balance sheet balances" in output


def test_print_report_end_to_end_smoke():
    periods = load_known_good()

    ratio_sets = {y: ratios_mod.compute_ratios(periods[y], periods.get(y - 1)) for y in periods}
    articulation_checks = {2023: articulation.run_checks(periods[2023], periods[2022])}
    multi_year = report.MultiYearReport(
        entity_name="Fixture Known-Good Co.",
        cik="0000000001",
        periods=periods,
        ratio_sets=ratio_sets,
        articulation_checks=articulation_checks,
    )
    console = Console(file=io.StringIO(), force_terminal=False, width=160)

    report.print_report(multi_year, console=console)

    output = console.file.getvalue()
    assert "Fixture Known-Good Co." in output
    assert "Income Statement" in output
    assert "Liquidity Ratios" in output
    assert "Articulation Checks" in output
