"""Shared fixtures. No network anywhere in Phase 2 tests: this builds a
synthetic ``companyfacts``-shaped dict by hand, small enough to reason about,
so normalize.py logic can be tested independently of real EDGAR quirks.
"""
from __future__ import annotations

import pytest


def _fact(*, val, end, start=None, fy, fp="FY", form="10-K", filed):
    fact = {"val": val, "end": end, "fy": fy, "fp": fp, "form": form, "filed": filed, "accn": "0000000000-00-000000"}
    if start is not None:
        fact["start"] = start
    return fact


def _concept(*facts):
    return {"units": {"USD": list(facts)}}


@pytest.fixture
def two_year_facts():
    """Two fiscal years (FY2022, FY2023) of a small, internally-consistent
    company, plus one restated concept (revenue FY2022) to exercise the
    'most recently filed wins' rule.
    """
    return {
        "cik": 999999,
        "entityName": "Fixture Co.",
        "facts": {
            "us-gaap": {
                # --- income statement ---------------------------------
                "RevenueFromContractWithCustomerExcludingAssessedTax": _concept(
                    _fact(val=1000, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    # restated FY2022 revenue, filed later as a comparative in the FY2023 10-K
                    _fact(val=1050, start="2021-01-01", end="2021-12-31", fy=2022, filed="2023-02-01"),
                    _fact(val=1200, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "CostOfGoodsAndServicesSold": _concept(
                    _fact(val=600, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=700, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "OperatingIncomeLoss": _concept(
                    _fact(val=250, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=300, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "IncomeTaxExpenseBenefit": _concept(
                    _fact(val=40, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=50, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "NetIncomeLoss": _concept(
                    _fact(val=160, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=200, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                # --- balance sheet (instant) ---------------------------
                "CashAndCashEquivalentsAtCarryingValue": _concept(
                    # fiscal-year-end balances, as shown on the balance sheet
                    _fact(val=300, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=400, end="2022-12-31", fy=2023, filed="2023-02-01"),
                    # same concept, also disclosed as CFS beginning-of-year
                    # balances -- dated at the period *start*, not the prior
                    # period's end, per real XBRL contexts
                    _fact(val=250, end="2021-01-01", fy=2022, filed="2022-02-01"),
                    _fact(val=300, end="2022-01-01", fy=2023, filed="2023-02-01"),
                ),
                "AssetsCurrent": _concept(
                    _fact(val=800, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=900, end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "Assets": _concept(
                    _fact(val=2000, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=2200, end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "LiabilitiesCurrent": _concept(
                    _fact(val=500, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=550, end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "Liabilities": _concept(
                    _fact(val=1200, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=1300, end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "StockholdersEquity": _concept(
                    _fact(val=800, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=900, end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "RetainedEarningsAccumulatedDeficit": _concept(
                    _fact(val=500, end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=640, end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                # --- cash flow statement -------------------------------
                "NetCashProvidedByUsedInOperatingActivities": _concept(
                    _fact(val=220, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=260, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": _concept(
                    _fact(val=80, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=90, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "NetCashProvidedByUsedInInvestingActivities": _concept(
                    _fact(val=-80, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=-90, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
                "NetCashProvidedByUsedInFinancingActivities": _concept(
                    _fact(val=-60, start="2021-01-01", end="2021-12-31", fy=2022, filed="2022-02-01"),
                    _fact(val=-70, start="2022-01-01", end="2022-12-31", fy=2023, filed="2023-02-01"),
                ),
            }
        },
    }
