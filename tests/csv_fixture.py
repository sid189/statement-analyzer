"""Loads tests/fixtures/known_good.csv directly into FinancialPeriod models,
bypassing normalize.py entirely. Per CLAUDE.md, this hand-entered fixture
tests articulation math independently of tag-mapping bugs: if a check fails
here, the bug is in the check; if it fails on EDGAR data but not here, the
bug is in normalize.py's tag map.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from statement_analyzer.model import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "known_good.csv"

_INCOME_FIELDS = set(IncomeStatement.model_fields)
_BALANCE_FIELDS = set(BalanceSheet.model_fields)
_CASH_FLOW_FIELDS = set(CashFlowStatement.model_fields)


def load_known_good(path: Path = FIXTURE_PATH) -> dict[int, FinancialPeriod]:
    """Return {fiscal_year: FinancialPeriod} for every row in the CSV."""
    periods: dict[int, FinancialPeriod] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fiscal_year = int(row["fiscal_year"])
            values = {
                k: Decimal(v)
                for k, v in row.items()
                if k not in ("fiscal_year", "period_start", "period_end")
            }
            periods[fiscal_year] = FinancialPeriod(
                entity_name="Fixture Known-Good Co.",
                cik="0000000001",
                fiscal_year=fiscal_year,
                period_start=date.fromisoformat(row["period_start"]),
                period_end=date.fromisoformat(row["period_end"]),
                income_statement=IncomeStatement(
                    **{k: v for k, v in values.items() if k in _INCOME_FIELDS}
                ),
                balance_sheet=BalanceSheet(
                    **{k: v for k, v in values.items() if k in _BALANCE_FIELDS}
                ),
                cash_flow_statement=CashFlowStatement(
                    **{k: v for k, v in values.items() if k in _CASH_FLOW_FIELDS}
                ),
            )
    return periods
