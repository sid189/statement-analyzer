"""Phase 5 — scale + report: multi-year assembly and terminal output.

Assembles several fiscal years of FinancialPeriod / RatioSet / ArticulationCheck
into pandas trend tables (line item x year), then renders them as rich
terminal tables. pandas only enters the project here, per CLAUDE.md, now that
multi-year trend tables are the actual job -- a DataFrame column holds
Decimal/None objects (pandas object dtype), never a float, so nothing here
re-introduces the rounding the rest of the project goes out of its way to avoid.

This stage doesn't compute anything new; it's presentation over Phases 2-4.
A year that can't be normalized is skipped, not fatal -- the rest of the
range still renders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd
from rich.console import Console
from rich.table import Table

from . import articulation, normalize, ratios
from .articulation import ArticulationCheck
from .model import BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement
from .ratios import (
    EfficiencyRatios,
    LeverageRatios,
    LiquidityRatios,
    ProfitabilityRatios,
    RatioSet,
)


@dataclass(frozen=True)
class MultiYearReport:
    entity_name: str
    cik: str
    periods: dict[int, FinancialPeriod]
    ratio_sets: dict[int, RatioSet]
    articulation_checks: dict[int, list[ArticulationCheck]]
    skipped_years: tuple[int, ...] = field(default_factory=tuple)


def assemble_multi_year(facts: dict, years: list[int]) -> MultiYearReport:
    """Normalize every year in ``years``, then compute ratios (using the prior
    year for averages when available) and articulation checks (which need a
    prior year outright, so a year with none simply gets no entry)."""
    periods: dict[int, FinancialPeriod] = {}
    skipped: list[int] = []
    for year in years:
        try:
            periods[year] = normalize.build_period(facts, year)
        except normalize.NormalizeError:
            skipped.append(year)

    ratio_sets: dict[int, RatioSet] = {}
    articulation_checks: dict[int, list[ArticulationCheck]] = {}
    for year in sorted(periods):
        prior = periods.get(year - 1)
        ratio_sets[year] = ratios.compute_ratios(periods[year], prior)
        if prior is not None:
            articulation_checks[year] = articulation.run_checks(periods[year], prior)

    return MultiYearReport(
        entity_name=str(facts.get("entityName", "?")),
        cik=str(facts.get("cik", "?")),
        periods=periods,
        ratio_sets=ratio_sets,
        articulation_checks=articulation_checks,
        skipped_years=tuple(skipped),
    )


# --- DataFrame builders: rows = line item / ratio / check, columns = year ---
def _label(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _frame(years: list[int], field_names: list[str], get) -> pd.DataFrame:
    """Build a (line item x year) DataFrame. ``get(year, field_name)`` returns
    the cell value, or None if unavailable for that year."""
    data = {year: {_label(name): get(year, name) for name in field_names} for year in years}
    return pd.DataFrame(data)


def income_statement_df(periods: dict[int, FinancialPeriod]) -> pd.DataFrame:
    years = sorted(periods)
    fields = list(IncomeStatement.model_fields)
    return _frame(years, fields, lambda y, n: getattr(periods[y].income_statement, n))


def balance_sheet_df(periods: dict[int, FinancialPeriod]) -> pd.DataFrame:
    years = sorted(periods)
    fields = list(BalanceSheet.model_fields)
    return _frame(years, fields, lambda y, n: getattr(periods[y].balance_sheet, n))


def cash_flow_df(periods: dict[int, FinancialPeriod]) -> pd.DataFrame:
    years = sorted(periods)
    fields = list(CashFlowStatement.model_fields)
    return _frame(years, fields, lambda y, n: getattr(periods[y].cash_flow_statement, n))


def _ratio_group_df(ratio_sets: dict[int, RatioSet], group: str, fields: list[str]) -> pd.DataFrame:
    years = sorted(ratio_sets)
    return _frame(years, fields, lambda y, n: getattr(getattr(ratio_sets[y], group), n))


def liquidity_df(ratio_sets: dict[int, RatioSet]) -> pd.DataFrame:
    return _ratio_group_df(ratio_sets, "liquidity", list(LiquidityRatios.model_fields))


def leverage_df(ratio_sets: dict[int, RatioSet]) -> pd.DataFrame:
    return _ratio_group_df(ratio_sets, "leverage", list(LeverageRatios.model_fields))


def profitability_df(ratio_sets: dict[int, RatioSet]) -> pd.DataFrame:
    return _ratio_group_df(ratio_sets, "profitability", list(ProfitabilityRatios.model_fields))


def efficiency_df(ratio_sets: dict[int, RatioSet]) -> pd.DataFrame:
    return _ratio_group_df(ratio_sets, "efficiency", list(EfficiencyRatios.model_fields))


def articulation_df(articulation_checks: dict[int, list[ArticulationCheck]]) -> pd.DataFrame:
    """Rows = check name, columns = year, cells = the ArticulationCheck itself
    (delta, base, within_tolerance, missing_inputs all travel together so the
    renderer can color and annotate without a second lookup)."""
    years = sorted(articulation_checks)
    data = {
        year: {check.name: check for check in articulation_checks[year]}
        for year in years
    }
    return pd.DataFrame(data)


# --- rich terminal rendering -------------------------------------------------
def _fmt_money(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:,.0f}"


def _fmt_ratio(value: Decimal | None, decimals: int = 2) -> str:
    return "—" if value is None else f"{value:,.{decimals}f}"


def render_statement_table(console: Console, title: str, df: pd.DataFrame) -> None:
    table = Table(title=title, title_justify="left")
    table.add_column("Line item")
    for year in df.columns:
        table.add_column(str(year), justify="right")
    for label, row in df.iterrows():
        table.add_row(label, *(_fmt_money(v) for v in row))
    console.print(table)


def render_ratio_table(console: Console, title: str, df: pd.DataFrame) -> None:
    table = Table(title=title, title_justify="left")
    table.add_column("Ratio")
    for year in df.columns:
        table.add_column(str(year), justify="right")
    for label, row in df.iterrows():
        table.add_row(label, *(_fmt_ratio(v) for v in row))
    console.print(table)


def render_articulation_table(console: Console, title: str, df: pd.DataFrame) -> None:
    table = Table(title=title, title_justify="left")
    table.add_column("Check")
    for year in df.columns:
        table.add_column(str(year), justify="right")
    for label, row in df.iterrows():
        cells = []
        for check in row:
            if check is None or (not isinstance(check, ArticulationCheck)):
                cells.append("—")
            elif check.delta is None:
                cells.append("[dim]n/a[/dim]")
            else:
                color = "green" if check.within_tolerance else "red"
                cells.append(f"[{color}]{check.delta:,.2f}[/{color}]")
        table.add_row(label, *cells)
    console.print(table)


def print_report(report: MultiYearReport, console: Console | None = None) -> None:
    console = console or Console()
    console.print(f"[bold]{report.entity_name}[/bold] (CIK {report.cik})")
    if report.skipped_years:
        console.print(f"[dim]skipped (not found in filings): {', '.join(map(str, report.skipped_years))}[/dim]")
    console.print()

    render_statement_table(console, "Income Statement ($)", income_statement_df(report.periods))
    render_statement_table(console, "Balance Sheet ($)", balance_sheet_df(report.periods))
    render_statement_table(console, "Cash Flow Statement ($)", cash_flow_df(report.periods))
    console.print()

    render_ratio_table(console, "Liquidity Ratios", liquidity_df(report.ratio_sets))
    render_ratio_table(console, "Leverage Ratios", leverage_df(report.ratio_sets))
    render_ratio_table(console, "Profitability Ratios", profitability_df(report.ratio_sets))
    render_ratio_table(console, "Efficiency Ratios", efficiency_df(report.ratio_sets))
    console.print()

    if report.articulation_checks:
        render_articulation_table(
            console, "Articulation Checks ($ delta)", articulation_df(report.articulation_checks)
        )
