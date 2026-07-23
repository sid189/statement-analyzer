"""Tests for normalize.py's derivation-only fallbacks, added after hardening
against real filings from Microsoft, Walmart, Johnson & Johnson, and
Coca-Cola. Each of these filers tags at least one canonical line item
differently than Apple -- these tests pin down the specific patterns found
(e.g. Walmart and Coca-Cola never tag a total "Liabilities" concept at all)
using small hand-built fixtures, so the fallback logic doesn't need network
access to stay covered.
"""
from __future__ import annotations

from decimal import Decimal

from statement_analyzer import normalize

from conftest import _concept, _fact

START, END, FY = "2024-01-01", "2024-12-31", 2024


def _facts(**concepts) -> dict:
    return {
        "cik": 1,
        "entityName": "Derivation Fixture Co.",
        "facts": {"us-gaap": concepts},
    }


def _duration(val):
    return _concept(_fact(val=val, start=START, end=END, fy=FY, filed="2025-01-01"))


def _instant(val):
    return _concept(_fact(val=val, end=END, fy=FY, filed="2025-01-01"))


def test_total_liabilities_derived_when_untagged():
    # Walmart and Coca-Cola never tag "Liabilities" at all.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        LiabilitiesAndStockholdersEquity=_instant(1000),
        StockholdersEquity=_instant(400),
    )

    period = normalize.build_period(facts, FY)

    assert period.balance_sheet.total_liabilities == Decimal("600")


def test_total_liabilities_stays_none_without_enough_to_derive_from():
    facts = _facts(
        NetIncomeLoss=_duration(100),
        StockholdersEquity=_instant(400),
    )

    period = normalize.build_period(facts, FY)

    assert period.balance_sheet.total_liabilities is None


def test_selling_general_administrative_derived_from_components():
    # Microsoft tags Selling & Marketing and G&A separately, no combined SG&A.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        SellingAndMarketingExpense=_duration(60),
        GeneralAndAdministrativeExpense=_duration(25),
    )

    period = normalize.build_period(facts, FY)

    assert period.income_statement.selling_general_administrative == Decimal("85")


def test_operating_income_derived_when_untagged():
    # Johnson & Johnson hasn't tagged OperatingIncomeLoss in a decade.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        RevenueFromContractWithCustomerExcludingAssessedTax=_duration(1000),
        CostOfGoodsAndServicesSold=_duration(400),
        SellingGeneralAndAdministrativeExpense=_duration(300),
        ResearchAndDevelopmentExpense=_duration(100),
    )

    period = normalize.build_period(facts, FY)

    # gross_profit (600, derived) - r&d (100) - sga (300) = 200
    assert period.income_statement.operating_income == Decimal("200")


def test_operating_income_derivation_defaults_missing_rd_to_zero():
    # Walmart/Coca-Cola: no R&D tag at all, because there's no R&D -- must
    # not block the derivation.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        RevenueFromContractWithCustomerExcludingAssessedTax=_duration(1000),
        CostOfGoodsAndServicesSold=_duration(700),
        SellingGeneralAndAdministrativeExpense=_duration(200),
    )

    period = normalize.build_period(facts, FY)

    assert period.income_statement.operating_income == Decimal("100")  # 300 - 0 - 200


def test_operating_expenses_derived_from_gross_profit_and_operating_income():
    facts = _facts(
        NetIncomeLoss=_duration(100),
        RevenueFromContractWithCustomerExcludingAssessedTax=_duration(1000),
        CostOfGoodsAndServicesSold=_duration(600),
        OperatingIncomeLoss=_duration(250),
    )

    period = normalize.build_period(facts, FY)

    assert period.income_statement.operating_expenses == Decimal("150")  # 400 - 250


def test_common_stock_and_apic_derived_from_components():
    # Johnson & Johnson and Coca-Cola tag common stock par value and APIC
    # as separate concepts, no combined tag.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        CommonStockValue=_instant(30),
        AdditionalPaidInCapitalCommonStock=_instant(200),
    )

    period = normalize.build_period(facts, FY)

    assert period.balance_sheet.common_stock_and_apic == Decimal("230")


def test_common_stock_and_apic_uses_par_value_alone_when_apic_absent():
    # Johnson & Johnson doesn't tag AdditionalPaidInCapital at all in recent
    # filings -- the derivation shouldn't require it.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        CommonStockValue=_instant(30),
    )

    period = normalize.build_period(facts, FY)

    assert period.balance_sheet.common_stock_and_apic == Decimal("30")


def test_depreciation_and_amortization_derived_from_components():
    # Microsoft tags Depreciation and AmortizationOfIntangibleAssets
    # separately, with no combined concept.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        Depreciation=_duration(22),
        AmortizationOfIntangibleAssets=_duration(6),
    )

    period = normalize.build_period(facts, FY)

    assert period.cash_flow_statement.depreciation_and_amortization == Decimal("28")


def test_interest_expense_nonoperating_fallback_tag():
    # Microsoft and Johnson & Johnson both migrated to this tag recently.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        InterestExpenseNonoperating=_duration(50),
    )

    period = normalize.build_period(facts, FY)

    assert period.income_statement.interest_expense == Decimal("50")


def test_dividends_paid_alternate_tag():
    # Johnson & Johnson's actual tag for cash dividends paid.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        DividendsCommonStockCash=_duration(40),
    )

    period = normalize.build_period(facts, FY)

    assert period.cash_flow_statement.dividends_paid == Decimal("40")


def test_stock_based_compensation_alternate_tag():
    # Walmart's actual stock comp tag.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        AllocatedShareBasedCompensationExpense=_duration(15),
    )

    period = normalize.build_period(facts, FY)

    assert period.cash_flow_statement.stock_based_compensation == Decimal("15")


def test_total_equity_including_noncontrolling_interest_fallback_tag():
    # Johnson & Johnson's current tag, now that it reports NCI.
    facts = _facts(
        NetIncomeLoss=_duration(100),
        StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest=_instant(900),
    )

    period = normalize.build_period(facts, FY)

    assert period.balance_sheet.total_equity == Decimal("900")
