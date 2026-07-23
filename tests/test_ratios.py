"""Phase 4 tests. Verified against the same hand-entered known-good CSV used
for articulation, so expected values are computable by hand from tests/fixtures/known_good.csv.
"""
from __future__ import annotations

from decimal import Decimal

from statement_analyzer import ratios

from csv_fixture import load_known_good


def test_liquidity_and_leverage_need_only_current_period():
    periods = load_known_good()
    current = periods[2023]

    result = ratios.compute_ratios(current)  # no prior

    assert result.liquidity.current_ratio == Decimal("900") / Decimal("240")
    assert result.liquidity.quick_ratio == Decimal("715") / Decimal("240")  # 475+60+180
    assert result.liquidity.cash_ratio == Decimal("535") / Decimal("240")  # 475+60
    assert result.leverage.debt_to_equity == Decimal("770") / Decimal("835")
    assert result.leverage.debt_to_assets == Decimal("770") / Decimal("1605")
    assert result.leverage.equity_multiplier == Decimal("1605") / Decimal("835")
    assert result.leverage.interest_coverage == Decimal("330") / Decimal("12")
    assert result.profitability.gross_margin == Decimal("500") / Decimal("1200")
    assert result.profitability.operating_margin == Decimal("330") / Decimal("1200")
    assert result.profitability.net_margin == Decimal("260") / Decimal("1200")


def test_average_balance_ratios_are_none_without_prior_period():
    periods = load_known_good()
    current = periods[2023]

    result = ratios.compute_ratios(current, prior=None)

    assert result.profitability.return_on_assets is None
    assert result.profitability.return_on_equity is None
    assert result.efficiency.asset_turnover is None
    assert result.efficiency.inventory_turnover is None
    assert result.efficiency.cash_conversion_cycle is None
    # current-period-only ratios are unaffected by the missing prior period
    assert result.liquidity.current_ratio is not None


def test_average_balance_ratios_with_prior_period():
    periods = load_known_good()
    current, prior = periods[2023], periods[2022]

    result = ratios.compute_ratios(current, prior)

    avg_assets = (Decimal("1605") + Decimal("1300")) / 2
    avg_equity = (Decimal("835") + Decimal("600")) / 2
    avg_inventory = (Decimal("130") + Decimal("100")) / 2
    avg_receivables = (Decimal("180") + Decimal("150")) / 2
    avg_payables = (Decimal("150") + Decimal("120")) / 2

    assert result.profitability.return_on_assets == Decimal("260") / avg_assets
    assert result.profitability.return_on_equity == Decimal("260") / avg_equity
    assert result.efficiency.asset_turnover == Decimal("1200") / avg_assets

    inventory_turnover = Decimal("700") / avg_inventory
    receivables_turnover = Decimal("1200") / avg_receivables
    payables_turnover = Decimal("700") / avg_payables
    assert result.efficiency.inventory_turnover == inventory_turnover
    assert result.efficiency.receivables_turnover == receivables_turnover
    assert result.efficiency.payables_turnover == payables_turnover

    dso = Decimal("365") / receivables_turnover
    dio = Decimal("365") / inventory_turnover
    dpo = Decimal("365") / payables_turnover
    assert result.efficiency.days_sales_outstanding == dso
    assert result.efficiency.days_inventory_outstanding == dio
    assert result.efficiency.days_payables_outstanding == dpo
    assert result.efficiency.cash_conversion_cycle == dio + dso - dpo


def test_missing_input_gives_none_not_a_crash():
    periods = load_known_good()
    current, prior = periods[2023], periods[2022]
    current_no_inventory = current.model_copy(
        update={"balance_sheet": current.balance_sheet.model_copy(update={"inventory": None})}
    )

    result = ratios.compute_ratios(current_no_inventory, prior)

    assert result.efficiency.inventory_turnover is None
    assert result.efficiency.days_inventory_outstanding is None
    assert result.efficiency.cash_conversion_cycle is None
    # unrelated ratios still compute
    assert result.efficiency.receivables_turnover is not None
    assert result.liquidity.current_ratio is not None


def test_zero_denominator_gives_none_not_a_crash():
    periods = load_known_good()
    current = periods[2023]
    current_no_interest = current.model_copy(
        update={"income_statement": current.income_statement.model_copy(update={"interest_expense": Decimal("0")})}
    )

    result = ratios.compute_ratios(current_no_interest)

    assert result.leverage.interest_coverage is None
