"""Phase 3 — articulation: the cross-statement checks.

This is the pedagogical core of the project. Each check reports a signed
delta scaled against a tolerance, never a pass/fail boolean, and nothing here
transforms data or halts on failure -- see CLAUDE.md ("the failures are the
lesson; never suppress them"). A check that can't be computed because an
input line item is unmapped says so explicitly via ``missing_inputs`` rather
than defaulting to zero, since "unmapped" and "reported as zero" mean
different things here.

Build/verify these checks against tests/fixtures/known_good.csv FIRST: if a
check fails there, the check itself is wrong. If it only fails on real EDGAR
data, the check is right and the gap is in normalize.py's tag map (or a real
reconciling item the filer discloses but this tool doesn't parse).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

from pydantic import BaseModel, ConfigDict

from .model import FinancialPeriod

DEFAULT_TOLERANCE_PCT = Decimal("0.01")  # 1% of the check's base magnitude


class ArticulationCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    delta: Decimal | None  # signed; None if an input was unmapped
    base: Decimal | None = None  # magnitude delta is scaled against for tolerance
    tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT
    missing_inputs: tuple[str, ...] = ()

    @property
    def within_tolerance(self) -> bool | None:
        """None means "couldn't be checked", not "passed"."""
        if self.delta is None:
            return None
        if self.base is None or self.base == 0:
            return self.delta == 0
        return abs(self.delta) <= self.tolerance_pct * abs(self.base)


def _check(
    name: str,
    values: dict[str, Decimal | None],
    compute: Callable[[dict[str, Decimal]], Decimal],
    base_key: str,
    *,
    tolerance_pct: Decimal,
) -> ArticulationCheck:
    missing = tuple(k for k, v in values.items() if v is None)
    if missing:
        return ArticulationCheck(
            name=name, delta=None, missing_inputs=missing, tolerance_pct=tolerance_pct
        )
    delta = compute(values)  # type: ignore[arg-type]
    return ArticulationCheck(
        name=name, delta=delta, base=values[base_key], tolerance_pct=tolerance_pct
    )


def check_balance_sheet_balances(
    period: FinancialPeriod, *, tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT
) -> ArticulationCheck:
    bs = period.balance_sheet
    values = {
        "total_assets": bs.total_assets,
        "total_liabilities": bs.total_liabilities,
        "total_equity": bs.total_equity,
    }
    return _check(
        "Balance sheet balances (Assets = Liabilities + Equity)",
        values,
        lambda v: v["total_assets"] - (v["total_liabilities"] + v["total_equity"]),
        "total_assets",
        tolerance_pct=tolerance_pct,
    )


def check_cash_ties(
    period: FinancialPeriod, *, tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT
) -> ArticulationCheck:
    values = {
        "cash_ending": period.cash_flow_statement.cash_ending,
        "cash_and_equivalents": period.balance_sheet.cash_and_equivalents,
    }
    return _check(
        "Cash ties out (CFS ending cash = BS cash)",
        values,
        lambda v: v["cash_ending"] - v["cash_and_equivalents"],
        "cash_and_equivalents",
        tolerance_pct=tolerance_pct,
    )


def check_retained_earnings_rollforward(
    current: FinancialPeriod,
    prior: FinancialPeriod,
    *,
    tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT,
) -> ArticulationCheck:
    values = {
        "re_end": current.balance_sheet.retained_earnings,
        "re_begin": prior.balance_sheet.retained_earnings,
        "net_income": current.income_statement.net_income,
        "dividends_paid": current.cash_flow_statement.dividends_paid,
    }
    return _check(
        "Retained earnings roll-forward (RE_end = RE_begin + NI - Dividends)",
        values,
        lambda v: v["re_end"] - (v["re_begin"] + v["net_income"] - v["dividends_paid"]),
        "re_end",
        tolerance_pct=tolerance_pct,
    )


def check_indirect_reconciliation(
    current: FinancialPeriod,
    prior: FinancialPeriod,
    *,
    tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT,
) -> ArticulationCheck:
    """NetIncome + non-cash adjustments +/- ΔworkingCapital = cash from
    operations -- the accruals lesson. ΔAR/ΔInventory/ΔAP are recomputed from
    two balance sheets rather than trusted from the CFS's own tagged change_in_*
    figures, per CLAUDE.md: this check exists to catch exactly the gap between
    what the balance sheet implies and what the CFS reports.
    """
    cfs = current.cash_flow_statement
    values = {
        "net_income": current.income_statement.net_income,
        "depreciation_and_amortization": cfs.depreciation_and_amortization,
        "cash_from_operations": cfs.cash_from_operations,
        "accounts_receivable": current.balance_sheet.accounts_receivable,
        "prior_accounts_receivable": prior.balance_sheet.accounts_receivable,
        "inventory": current.balance_sheet.inventory,
        "prior_inventory": prior.balance_sheet.inventory,
        "accounts_payable": current.balance_sheet.accounts_payable,
        "prior_accounts_payable": prior.balance_sheet.accounts_payable,
    }
    # Stock comp and deferred tax default to 0 when unmapped rather than being
    # required inputs: unlike dividends (where "missing" could hide a real
    # payment), the point of this specific check is to surface whatever isn't
    # mapped as a residual delta, not to refuse to run because of it.
    stock_based_compensation = cfs.stock_based_compensation or Decimal("0")
    deferred_income_tax = cfs.deferred_income_tax or Decimal("0")

    def compute(v: dict[str, Decimal]) -> Decimal:
        delta_ar = v["accounts_receivable"] - v["prior_accounts_receivable"]
        delta_inventory = v["inventory"] - v["prior_inventory"]
        delta_ap = v["accounts_payable"] - v["prior_accounts_payable"]
        computed_cfo = (
            v["net_income"]
            + v["depreciation_and_amortization"]
            + stock_based_compensation
            + deferred_income_tax
            - delta_ar
            - delta_inventory
            + delta_ap
        )
        return computed_cfo - v["cash_from_operations"]

    return _check(
        "Indirect-method CFO reconciliation (NI + non-cash ± ΔWC = CFO)",
        values,
        compute,
        "cash_from_operations",
        tolerance_pct=tolerance_pct,
    )


def run_checks(
    current: FinancialPeriod,
    prior: FinancialPeriod,
    *,
    tolerance_pct: Decimal = DEFAULT_TOLERANCE_PCT,
) -> list[ArticulationCheck]:
    """Run all four articulation checks for ``current``, using ``prior`` for
    the two that need period-over-period deltas."""
    return [
        check_balance_sheet_balances(current, tolerance_pct=tolerance_pct),
        check_retained_earnings_rollforward(current, prior, tolerance_pct=tolerance_pct),
        check_cash_ties(current, tolerance_pct=tolerance_pct),
        check_indirect_reconciliation(current, prior, tolerance_pct=tolerance_pct),
    ]
