"""Phase 2 — typed representation of one fiscal year's statements.

Pure data: nothing here reaches into raw XBRL or the network. That's
:mod:`normalize`'s job. A :class:`FinancialPeriod` is what a populated model
looks like once normalization has done its work.

Every field is ``Decimal | None`` -- ``None`` means the concept wasn't found
in the filing (an unmapped tag or a company that doesn't report that line),
not zero. Articulation checks (Phase 3) need to tell "missing" apart from
"reported as zero".
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Statement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def __iter__(self):  # type: ignore[override]
        # Iterate as (field_name, value) pairs rather than pydantic's default
        # of iterating dict-like key/value from model_fields -- same thing,
        # named for readability at call sites like _format_statement.
        yield from ((name, getattr(self, name)) for name in type(self).model_fields)


class IncomeStatement(_Statement):
    revenue: Decimal | None = None
    cost_of_revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    research_and_development: Decimal | None = None
    selling_general_administrative: Decimal | None = None
    operating_expenses: Decimal | None = None
    operating_income: Decimal | None = None
    interest_expense: Decimal | None = None
    other_income_expense: Decimal | None = None
    income_before_tax: Decimal | None = None
    income_tax_expense: Decimal | None = None
    net_income: Decimal | None = None


class BalanceSheet(_Statement):
    cash_and_equivalents: Decimal | None = None
    short_term_investments: Decimal | None = None
    accounts_receivable: Decimal | None = None
    inventory: Decimal | None = None
    other_current_assets: Decimal | None = None
    total_current_assets: Decimal | None = None
    property_plant_equipment_net: Decimal | None = None
    goodwill: Decimal | None = None
    other_noncurrent_assets: Decimal | None = None
    total_assets: Decimal | None = None
    accounts_payable: Decimal | None = None
    short_term_debt: Decimal | None = None
    other_current_liabilities: Decimal | None = None
    total_current_liabilities: Decimal | None = None
    long_term_debt: Decimal | None = None
    other_noncurrent_liabilities: Decimal | None = None
    total_liabilities: Decimal | None = None
    common_stock_and_apic: Decimal | None = None
    retained_earnings: Decimal | None = None
    accumulated_oci: Decimal | None = None
    total_equity: Decimal | None = None
    total_liabilities_and_equity: Decimal | None = None


class CashFlowStatement(_Statement):
    net_income: Decimal | None = None
    depreciation_and_amortization: Decimal | None = None
    stock_based_compensation: Decimal | None = None
    deferred_income_tax: Decimal | None = None
    change_in_accounts_receivable: Decimal | None = None
    change_in_inventory: Decimal | None = None
    change_in_accounts_payable: Decimal | None = None
    other_operating_activities: Decimal | None = None
    cash_from_operations: Decimal | None = None
    capital_expenditures: Decimal | None = None
    cash_from_investing: Decimal | None = None
    dividends_paid: Decimal | None = None
    stock_repurchases: Decimal | None = None
    cash_from_financing: Decimal | None = None
    effect_of_exchange_rate: Decimal | None = None
    net_change_in_cash: Decimal | None = None
    cash_beginning: Decimal | None = None
    cash_ending: Decimal | None = None


class FinancialPeriod(BaseModel):
    """One fiscal year's three statements, plus the metadata articulation
    needs to line two periods up (period boundaries, not just a label)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_name: str
    cik: str
    fiscal_year: int
    period_start: date
    period_end: date
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow_statement: CashFlowStatement

    def summary(self) -> str:
        """Human-readable dump of every line item. 'A populated model prints'
        is the Phase 2 exit bar -- this is that print."""
        lines = [
            f"{self.entity_name} (CIK {self.cik}) -- FY{self.fiscal_year}"
            f" ({self.period_start} to {self.period_end})",
            "",
            "Income Statement",
            *_format_statement(self.income_statement),
            "",
            "Balance Sheet",
            *_format_statement(self.balance_sheet),
            "",
            "Cash Flow Statement",
            *_format_statement(self.cash_flow_statement),
        ]
        return "\n".join(lines)


def _format_statement(stmt: _Statement) -> list[str]:
    lines = []
    for field_name, value in stmt:
        label = field_name.replace("_", " ").capitalize()
        shown = f"{value:,}" if value is not None else "-- (unmapped)"
        lines.append(f"  {label:<40} {shown}")
    return lines
