"""Phase 2 — normalization.

Maps raw us-gaap XBRL concepts (as returned by the ``companyfacts`` API) onto
the canonical line items defined in :mod:`model`, resolving restatements
along the way, and assembles one fiscal year into a :class:`FinancialPeriod`.

Nothing here touches the network -- it operates on the dict already returned
by :func:`statement_analyzer.ingest.fetch_company_facts`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from .model import BalanceSheet, CashFlowStatement, FinancialPeriod, IncomeStatement

ANNUAL_FORM = "10-K"


class NormalizeError(RuntimeError):
    """Raised when a fiscal year can't be located in the raw facts."""


# --- canonical concept map --------------------------------------------------
# canonical name -> candidate us-gaap tags, tried in order (first tag with a
# matching value wins). Companies tag economically-identical line items under
# different concepts (e.g. CostOfRevenue vs CostOfGoodsAndServicesSold), so
# this is the one place those choices live. When a check fails against a real
# filing (Phase 3), extend the tuple here rather than special-casing a company
# elsewhere.
INCOME_STATEMENT_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "cost_of_revenue": (
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
    ),
    "gross_profit": ("GrossProfit",),
    "research_and_development": ("ResearchAndDevelopmentExpense",),
    "selling_general_administrative": ("SellingGeneralAndAdministrativeExpense",),
    "operating_expenses": ("OperatingExpenses", "CostsAndExpenses"),
    "operating_income": ("OperatingIncomeLoss",),
    "interest_expense": ("InterestExpense", "InterestExpenseDebt", "InterestExpenseNonoperating"),
    "other_income_expense": (
        "NonoperatingIncomeExpense",
        "OtherNonoperatingIncomeExpense",
    ),
    "income_before_tax": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems"
        "NoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterest"
        "AndIncomeLossFromEquityMethodInvestments",
    ),
    "income_tax_expense": ("IncomeTaxExpenseBenefit",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
}

BALANCE_SHEET_TAGS: dict[str, tuple[str, ...]] = {
    "cash_and_equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
    "short_term_investments": ("MarketableSecuritiesCurrent", "ShortTermInvestments"),
    "accounts_receivable": ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent"),
    "inventory": ("InventoryNet",),
    "other_current_assets": ("OtherAssetsCurrent",),
    "total_current_assets": ("AssetsCurrent",),
    "property_plant_equipment_net": ("PropertyPlantAndEquipmentNet",),
    "goodwill": ("Goodwill",),
    "other_noncurrent_assets": ("OtherAssetsNoncurrent",),
    "total_assets": ("Assets",),
    "accounts_payable": ("AccountsPayableCurrent", "AccountsPayableTradeCurrent"),
    "short_term_debt": (
        "ShortTermBorrowings",
        "LongTermDebtCurrent",
        "CommercialPaperAtCarryingValue",
    ),
    "other_current_liabilities": ("OtherLiabilitiesCurrent",),
    "total_current_liabilities": ("LiabilitiesCurrent",),
    "long_term_debt": ("LongTermDebtNoncurrent",),
    "other_noncurrent_liabilities": ("OtherLiabilitiesNoncurrent",),
    "total_liabilities": ("Liabilities",),
    "common_stock_and_apic": (
        "CommonStocksIncludingAdditionalPaidInCapital",
        "AdditionalPaidInCapital",
    ),
    "retained_earnings": ("RetainedEarningsAccumulatedDeficit",),
    "accumulated_oci": ("AccumulatedOtherComprehensiveIncomeLossNetOfTax",),
    "total_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "total_liabilities_and_equity": ("LiabilitiesAndStockholdersEquity",),
}

# Flow items: matched by (start, end) within the fiscal year.
CASH_FLOW_DURATION_TAGS: dict[str, tuple[str, ...]] = {
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "depreciation_and_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
    ),
    "stock_based_compensation": ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"),
    "deferred_income_tax": ("DeferredIncomeTaxExpenseBenefit",),
    "change_in_accounts_receivable": ("IncreaseDecreaseInAccountsReceivable",),
    "change_in_inventory": ("IncreaseDecreaseInInventories",),
    "change_in_accounts_payable": ("IncreaseDecreaseInAccountsPayable",),
    "other_operating_activities": (
        "OtherOperatingActivitiesCashFlowStatement",
        "IncreaseDecreaseInOtherOperatingCapitalNet",
    ),
    "cash_from_operations": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditures": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "cash_from_investing": ("NetCashProvidedByUsedInInvestingActivities",),
    "dividends_paid": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "DividendsCommonStockCash"),
    "stock_repurchases": ("PaymentsForRepurchaseOfCommonStock",),
    "cash_from_financing": ("NetCashProvidedByUsedInFinancingActivities",),
    "effect_of_exchange_rate": (
        "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestricted"
        "CashEquivalents",
    ),
    "net_change_in_cash": (
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriod"
        "IncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ),
}

# Instant items looked up at a single date (period start or end) rather than
# a (start, end) span. The CFS often tags beginning/ending cash under a
# concept that includes restricted cash, distinct from the BS cash line --
# deliberately kept separate so the Phase 3 "cash ties out" check has real
# tags to compare instead of comparing a value against itself.
CASH_FLOW_CASH_TAGS: tuple[str, ...] = (
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsAtCarryingValue",
    "CashAndCashEquivalentsAtCarryingValue",
)

# Derivation-only component tags: some filers report these as separate
# concepts instead of tagging the rolled-up figure at all (confirmed against
# Microsoft, Walmart, Johnson & Johnson, and Coca-Cola's real filings -- e.g.
# Microsoft tags Selling & Marketing and G&A separately with no combined SG&A
# concept; Walmart and Coca-Cola never tag a total "Liabilities" concept).
# These are only consulted when the primary/combined tag above comes back
# empty, never tried first.
_SELLING_EXPENSE_TAGS = ("SellingAndMarketingExpense",)
_GENERAL_ADMIN_EXPENSE_TAGS = ("GeneralAndAdministrativeExpense",)
_COMMON_STOCK_PAR_VALUE_TAGS = ("CommonStockValue",)
_ADDITIONAL_PAID_IN_CAPITAL_TAGS = ("AdditionalPaidInCapital", "AdditionalPaidInCapitalCommonStock")
_DEPRECIATION_ONLY_TAGS = ("Depreciation",)
_AMORTIZATION_OF_INTANGIBLES_TAGS = ("AmortizationOfIntangibleAssets",)


def _sum_optional(*values: Decimal | None) -> Decimal | None:
    """Sum whichever values are present, treating a missing one as 0 -- but
    None if every value is missing (so "no components found" still reads as
    unmapped, not a fabricated zero)."""
    present = [v for v in values if v is not None]
    return sum(present, Decimal("0")) if present else None


# --- raw fact access ---------------------------------------------------------
def _entries_for_tag(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    return (
        facts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
        .get("USD", [])
    )


def _most_recently_filed(entries: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Of several filed values for the same period (restatements, or the same
    historical period reported again as a comparative in a later 10-K), take
    the one filed last -- the most current view of that period."""
    entries = list(entries)
    if not entries:
        return None
    return max(entries, key=lambda e: e["filed"])


def _find_duration_value(
    facts: dict[str, Any],
    tags: tuple[str, ...],
    *,
    start: date,
    end: date,
) -> Decimal | None:
    # Matched purely by (start, end), not by fy/fp: SEC's fy/fp describe the
    # *filing's* own fiscal focus, not the period an individual fact covers --
    # a 10-K reports 2-3 years of comparative figures all stamped with that
    # filing's own fy. A restated FY2022 value shows up as a comparative row
    # inside the FY2023 10-K, tagged fy=2023, so filtering on fy would miss it.
    for tag in tags:
        matches = [
            e
            for e in _entries_for_tag(facts, tag)
            if e.get("form") == ANNUAL_FORM
            and e.get("start") == start.isoformat()
            and e.get("end") == end.isoformat()
        ]
        best = _most_recently_filed(matches)
        if best is not None:
            return Decimal(str(best["val"]))
    return None


def _find_instant_value(
    facts: dict[str, Any], tags: tuple[str, ...], *, end: date
) -> Decimal | None:
    for tag in tags:
        matches = [
            e
            for e in _entries_for_tag(facts, tag)
            if e.get("form") == ANNUAL_FORM and e.get("end") == end.isoformat()
        ]
        best = _most_recently_filed(matches)
        if best is not None:
            return Decimal(str(best["val"]))
    return None


def _anchor_period(facts: dict[str, Any], fiscal_year: int) -> tuple[date, date]:
    """Find the fiscal year's (start, end) dates.

    fy==fiscal_year & fp=="FY" & form=="10-K" pins down the one 10-K whose own
    fiscal-year focus is ``fiscal_year`` -- but that filing's facts also
    include 1-2 prior comparative years stamped with the same fy (see
    _find_duration_value). The row we want is the *current* year, which is
    the one with the latest end date among that group.
    """
    for tag in (
        "NetIncomeLoss",
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
    ):
        matches = [
            e
            for e in _entries_for_tag(facts, tag)
            if e.get("form") == ANNUAL_FORM
            and e.get("fy") == fiscal_year
            and e.get("fp") == "FY"
        ]
        if matches:
            best = max(matches, key=lambda e: e["end"])
            return date.fromisoformat(best["start"]), date.fromisoformat(best["end"])
    raise NormalizeError(f"Could not find fiscal year {fiscal_year} in filings")


def available_fiscal_years(facts: dict[str, Any]) -> list[int]:
    """Fiscal years with an annual (10-K, fp=FY) net income figure, newest first."""
    years = {
        e["fy"]
        for e in _entries_for_tag(facts, "NetIncomeLoss")
        if e.get("form") == ANNUAL_FORM and e.get("fp") == "FY" and e.get("fy") is not None
    }
    return sorted(years, reverse=True)


# --- assembly -----------------------------------------------------------------
def build_period(facts: dict[str, Any], fiscal_year: int) -> FinancialPeriod:
    """Normalize one fiscal year of raw ``companyfacts`` into a FinancialPeriod."""
    start, end = _anchor_period(facts, fiscal_year)

    income_values = {
        name: _find_duration_value(facts, tags, start=start, end=end)
        for name, tags in INCOME_STATEMENT_TAGS.items()
    }
    if income_values.get("gross_profit") is None:
        revenue, cogs = income_values.get("revenue"), income_values.get("cost_of_revenue")
        if revenue is not None and cogs is not None:
            income_values["gross_profit"] = revenue - cogs

    if income_values.get("selling_general_administrative") is None:
        income_values["selling_general_administrative"] = _sum_optional(
            _find_duration_value(facts, _SELLING_EXPENSE_TAGS, start=start, end=end),
            _find_duration_value(facts, _GENERAL_ADMIN_EXPENSE_TAGS, start=start, end=end),
        )

    if income_values.get("operating_income") is None:
        gross_profit = income_values.get("gross_profit")
        sga = income_values.get("selling_general_administrative")
        if gross_profit is not None and sga is not None:
            # R&D defaults to 0 when unmapped here, same tradeoff articulation.py
            # makes for stock comp/deferred tax: a filer missing this tag
            # (Walmart, Coca-Cola) simply doesn't do R&D, it isn't an unmapped
            # expense being silently dropped.
            rnd = income_values.get("research_and_development") or Decimal("0")
            income_values["operating_income"] = gross_profit - rnd - sga

    if income_values.get("operating_expenses") is None:
        gross_profit = income_values.get("gross_profit")
        operating_income = income_values.get("operating_income")
        if gross_profit is not None and operating_income is not None:
            income_values["operating_expenses"] = gross_profit - operating_income

    balance_values = {
        name: _find_instant_value(facts, tags, end=end)
        for name, tags in BALANCE_SHEET_TAGS.items()
    }
    if balance_values.get("common_stock_and_apic") is None:
        balance_values["common_stock_and_apic"] = _sum_optional(
            _find_instant_value(facts, _COMMON_STOCK_PAR_VALUE_TAGS, end=end),
            _find_instant_value(facts, _ADDITIONAL_PAID_IN_CAPITAL_TAGS, end=end),
        )
    if balance_values.get("total_liabilities") is None:
        # Walmart and Coca-Cola never tag a total "Liabilities" concept at
        # all -- derive it from the two totals that *are* always tagged.
        total_liabilities_and_equity = balance_values.get("total_liabilities_and_equity")
        total_equity = balance_values.get("total_equity")
        if total_liabilities_and_equity is not None and total_equity is not None:
            balance_values["total_liabilities"] = total_liabilities_and_equity - total_equity

    cash_flow_values = {
        name: _find_duration_value(facts, tags, start=start, end=end)
        for name, tags in CASH_FLOW_DURATION_TAGS.items()
    }
    if cash_flow_values.get("depreciation_and_amortization") is None:
        cash_flow_values["depreciation_and_amortization"] = _sum_optional(
            _find_duration_value(facts, _DEPRECIATION_ONLY_TAGS, start=start, end=end),
            _find_duration_value(facts, _AMORTIZATION_OF_INTANGIBLES_TAGS, start=start, end=end),
        )
    cash_flow_values["cash_beginning"] = _find_instant_value(
        facts, CASH_FLOW_CASH_TAGS, end=start
    )
    cash_flow_values["cash_ending"] = _find_instant_value(
        facts, CASH_FLOW_CASH_TAGS, end=end
    )

    return FinancialPeriod(
        entity_name=facts.get("entityName", "?"),
        cik=str(facts.get("cik", "?")),
        fiscal_year=fiscal_year,
        period_start=start,
        period_end=end,
        income_statement=IncomeStatement(**income_values),
        balance_sheet=BalanceSheet(**balance_values),
        cash_flow_statement=CashFlowStatement(**cash_flow_values),
    )
