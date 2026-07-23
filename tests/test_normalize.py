"""Phase 2 tests for tag selection and period assembly. No network -- these
run against the synthetic two-year fixture in conftest.py.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from statement_analyzer import normalize


def test_available_fiscal_years(two_year_facts):
    assert normalize.available_fiscal_years(two_year_facts) == [2023, 2022]


def test_unknown_fiscal_year_raises(two_year_facts):
    with pytest.raises(normalize.NormalizeError):
        normalize.build_period(two_year_facts, 1999)


def test_restatement_takes_most_recently_filed_value(two_year_facts):
    # FY2022 revenue was originally filed as 1000, then restated to 1050 as a
    # comparative in the FY2023 10-K (filed later) -- normalize must prefer 1050.
    period = normalize.build_period(two_year_facts, 2022)
    assert period.income_statement.revenue == Decimal("1050")


def test_income_statement_values(two_year_facts):
    period = normalize.build_period(two_year_facts, 2023)
    stmt = period.income_statement
    assert stmt.revenue == Decimal("1200")
    assert stmt.cost_of_revenue == Decimal("700")
    assert stmt.operating_income == Decimal("300")
    assert stmt.income_tax_expense == Decimal("50")
    assert stmt.net_income == Decimal("200")


def test_gross_profit_is_derived_when_untagged(two_year_facts):
    # The fixture has no GrossProfit tag at all -- normalize must derive it.
    period = normalize.build_period(two_year_facts, 2023)
    assert period.income_statement.gross_profit == Decimal("500")  # 1200 - 700


def test_missing_concept_is_none_not_zero(two_year_facts):
    # PaymentsOfDividends was never tagged in the fixture.
    period = normalize.build_period(two_year_facts, 2023)
    assert period.cash_flow_statement.dividends_paid is None


def test_balance_sheet_values(two_year_facts):
    period = normalize.build_period(two_year_facts, 2023)
    bs = period.balance_sheet
    assert bs.cash_and_equivalents == Decimal("400")
    assert bs.total_current_assets == Decimal("900")
    assert bs.total_assets == Decimal("2200")
    assert bs.total_current_liabilities == Decimal("550")
    assert bs.total_liabilities == Decimal("1300")
    assert bs.total_equity == Decimal("900")


def test_balance_sheet_is_year_specific(two_year_facts):
    # FY2022 and FY2023 instants must not bleed into each other.
    fy2022 = normalize.build_period(two_year_facts, 2022)
    fy2023 = normalize.build_period(two_year_facts, 2023)
    assert fy2022.balance_sheet.total_assets == Decimal("2000")
    assert fy2023.balance_sheet.total_assets == Decimal("2200")


def test_cash_flow_beginning_and_ending_cash(two_year_facts):
    # Beginning-of-FY2023 cash (dated at the period start) should equal
    # end-of-FY2022 cash (dated at the prior period's end) -- 300 either way.
    period = normalize.build_period(two_year_facts, 2023)
    cfs = period.cash_flow_statement
    assert cfs.cash_beginning == Decimal("300")
    assert cfs.cash_ending == Decimal("400")
    assert cfs.cash_from_operations == Decimal("260")


def test_period_dates(two_year_facts):
    period = normalize.build_period(two_year_facts, 2023)
    assert period.period_start.isoformat() == "2022-01-01"
    assert period.period_end.isoformat() == "2022-12-31"
