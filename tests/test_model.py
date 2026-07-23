"""Phase 2 tests for the typed model layer itself, independent of normalize.py."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from statement_analyzer.model import (
    BalanceSheet,
    CashFlowStatement,
    FinancialPeriod,
    IncomeStatement,
)


def _minimal_period(**overrides) -> FinancialPeriod:
    defaults = dict(
        entity_name="Fixture Co.",
        cik="0000999999",
        fiscal_year=2023,
        period_start=date(2022, 1, 1),
        period_end=date(2022, 12, 31),
        income_statement=IncomeStatement(revenue=Decimal("100")),
        balance_sheet=BalanceSheet(total_assets=Decimal("500")),
        cash_flow_statement=CashFlowStatement(cash_from_operations=Decimal("40")),
    )
    defaults.update(overrides)
    return FinancialPeriod(**defaults)


def test_unmapped_fields_default_to_none():
    stmt = IncomeStatement(revenue=Decimal("100"))
    assert stmt.net_income is None
    assert stmt.revenue == Decimal("100")


def test_statements_are_frozen():
    stmt = IncomeStatement(revenue=Decimal("100"))
    with pytest.raises(Exception):
        stmt.revenue = Decimal("200")  # type: ignore[misc]


def test_extra_fields_are_rejected():
    with pytest.raises(Exception):
        IncomeStatement(revenue=Decimal("100"), made_up_field=Decimal("1"))


def test_summary_prints_mapped_and_unmapped_lines():
    period = _minimal_period()
    text = period.summary()
    assert "Fixture Co." in text
    assert "FY2023" in text
    assert "Revenue" in text and "100" in text
    assert "-- (unmapped)" in text  # e.g. net income was never set
