"""Phase 4 — ratios: liquidity, leverage, profitability, and efficiency
metrics computed on a validated FinancialPeriod.

Nothing here re-derives or corrects statement data -- ratios are computed from
whatever normalize.py already produced, on the same None-means-unmapped
discipline as articulation.py. A ratio is None when an input is unmapped, the
denominator is zero, or (for the average-balance ratios: ROA, ROE, turnover)
no prior period was supplied -- an ending-balance-only version of those is a
different, less standard ratio, not a degraded version of this one.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .model import FinancialPeriod

TWO = Decimal("2")
DAYS_PER_YEAR = Decimal("365")


def _div(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _avg(current: Decimal | None, prior: Decimal | None) -> Decimal | None:
    if current is None or prior is None:
        return None
    return (current + prior) / TWO


class LiquidityRatios(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_ratio: Decimal | None = None
    quick_ratio: Decimal | None = None
    cash_ratio: Decimal | None = None


class LeverageRatios(BaseModel):
    model_config = ConfigDict(frozen=True)

    debt_to_equity: Decimal | None = None
    debt_to_assets: Decimal | None = None
    equity_multiplier: Decimal | None = None
    interest_coverage: Decimal | None = None


class ProfitabilityRatios(BaseModel):
    model_config = ConfigDict(frozen=True)

    gross_margin: Decimal | None = None
    operating_margin: Decimal | None = None
    net_margin: Decimal | None = None
    return_on_assets: Decimal | None = None
    return_on_equity: Decimal | None = None


class EfficiencyRatios(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_turnover: Decimal | None = None
    inventory_turnover: Decimal | None = None
    receivables_turnover: Decimal | None = None
    payables_turnover: Decimal | None = None
    days_sales_outstanding: Decimal | None = None
    days_inventory_outstanding: Decimal | None = None
    days_payables_outstanding: Decimal | None = None
    cash_conversion_cycle: Decimal | None = None


class RatioSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    fiscal_year: int
    liquidity: LiquidityRatios
    leverage: LeverageRatios
    profitability: ProfitabilityRatios
    efficiency: EfficiencyRatios

    def summary(self) -> str:
        lines = [
            f"FY{self.fiscal_year} ratios",
            "",
            "Liquidity",
            *_format_section(self.liquidity),
            "",
            "Leverage",
            *_format_section(self.leverage),
            "",
            "Profitability",
            *_format_section(self.profitability),
            "",
            "Efficiency",
            *_format_section(self.efficiency),
        ]
        return "\n".join(lines)


def _format_section(section: BaseModel) -> list[str]:
    lines = []
    for name in type(section).model_fields:
        value = getattr(section, name)
        label = name.replace("_", " ").capitalize()
        shown = f"{value:.4f}" if value is not None else "-- (not computable)"
        lines.append(f"  {label:<28} {shown}")
    return lines


def _liquidity(period: FinancialPeriod) -> LiquidityRatios:
    bs = period.balance_sheet
    quick_assets = None
    if None not in (bs.cash_and_equivalents, bs.short_term_investments, bs.accounts_receivable):
        quick_assets = bs.cash_and_equivalents + bs.short_term_investments + bs.accounts_receivable
    cash_assets = None
    if None not in (bs.cash_and_equivalents, bs.short_term_investments):
        cash_assets = bs.cash_and_equivalents + bs.short_term_investments
    return LiquidityRatios(
        current_ratio=_div(bs.total_current_assets, bs.total_current_liabilities),
        quick_ratio=_div(quick_assets, bs.total_current_liabilities),
        cash_ratio=_div(cash_assets, bs.total_current_liabilities),
    )


def _leverage(period: FinancialPeriod) -> LeverageRatios:
    bs, inc = period.balance_sheet, period.income_statement
    return LeverageRatios(
        debt_to_equity=_div(bs.total_liabilities, bs.total_equity),
        debt_to_assets=_div(bs.total_liabilities, bs.total_assets),
        equity_multiplier=_div(bs.total_assets, bs.total_equity),
        # operating_income stands in for EBIT -- the model has no separate tag for it.
        interest_coverage=_div(inc.operating_income, inc.interest_expense),
    )


def _profitability(current: FinancialPeriod, prior: FinancialPeriod | None) -> ProfitabilityRatios:
    inc, bs = current.income_statement, current.balance_sheet
    prior_bs = prior.balance_sheet if prior is not None else None
    avg_assets = _avg(bs.total_assets, prior_bs.total_assets if prior_bs else None)
    avg_equity = _avg(bs.total_equity, prior_bs.total_equity if prior_bs else None)
    return ProfitabilityRatios(
        gross_margin=_div(inc.gross_profit, inc.revenue),
        operating_margin=_div(inc.operating_income, inc.revenue),
        net_margin=_div(inc.net_income, inc.revenue),
        return_on_assets=_div(inc.net_income, avg_assets),
        return_on_equity=_div(inc.net_income, avg_equity),
    )


def _efficiency(current: FinancialPeriod, prior: FinancialPeriod | None) -> EfficiencyRatios:
    inc, bs = current.income_statement, current.balance_sheet
    prior_bs = prior.balance_sheet if prior is not None else None
    avg_assets = _avg(bs.total_assets, prior_bs.total_assets if prior_bs else None)
    avg_inventory = _avg(bs.inventory, prior_bs.inventory if prior_bs else None)
    avg_receivables = _avg(bs.accounts_receivable, prior_bs.accounts_receivable if prior_bs else None)
    avg_payables = _avg(bs.accounts_payable, prior_bs.accounts_payable if prior_bs else None)

    asset_turnover = _div(inc.revenue, avg_assets)
    inventory_turnover = _div(inc.cost_of_revenue, avg_inventory)
    receivables_turnover = _div(inc.revenue, avg_receivables)
    payables_turnover = _div(inc.cost_of_revenue, avg_payables)

    dso = _div(DAYS_PER_YEAR, receivables_turnover)
    dio = _div(DAYS_PER_YEAR, inventory_turnover)
    dpo = _div(DAYS_PER_YEAR, payables_turnover)
    ccc = (dio + dso - dpo) if None not in (dio, dso, dpo) else None

    return EfficiencyRatios(
        asset_turnover=asset_turnover,
        inventory_turnover=inventory_turnover,
        receivables_turnover=receivables_turnover,
        payables_turnover=payables_turnover,
        days_sales_outstanding=dso,
        days_inventory_outstanding=dio,
        days_payables_outstanding=dpo,
        cash_conversion_cycle=ccc,
    )


def compute_ratios(current: FinancialPeriod, prior: FinancialPeriod | None = None) -> RatioSet:
    """Compute all four ratio groups for ``current``. Pass ``prior`` when
    available -- ROA, ROE, and the turnover/day ratios use average balances
    and are None without it."""
    return RatioSet(
        fiscal_year=current.fiscal_year,
        liquidity=_liquidity(current),
        leverage=_leverage(current),
        profitability=_profitability(current, prior),
        efficiency=_efficiency(current, prior),
    )
