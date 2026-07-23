"""Phase 3 tests. Per CLAUDE.md, verify the check math against the hand-entered
known-good CSV FIRST -- if a check is wrong, it must show up here, on data
where the right answer is known by construction, before it's ever pointed at
messy real filings.
"""
from __future__ import annotations

from decimal import Decimal

from statement_analyzer import articulation

from csv_fixture import load_known_good


def test_known_good_fixture_ties_out_exactly():
    periods = load_known_good()
    current, prior = periods[2023], periods[2022]

    checks = articulation.run_checks(current, prior)

    assert len(checks) == 4
    for check in checks:
        assert check.missing_inputs == ()
        assert check.delta == Decimal("0"), f"{check.name} expected 0, got {check.delta}"
        assert check.within_tolerance is True


def test_balance_sheet_check_catches_a_real_imbalance():
    periods = load_known_good()
    current = periods[2023]
    broken = current.model_copy(
        update={
            "balance_sheet": current.balance_sheet.model_copy(
                update={"total_assets": current.balance_sheet.total_assets + Decimal("100")}
            )
        }
    )

    check = articulation.check_balance_sheet_balances(broken)

    assert check.delta == Decimal("100")
    assert check.within_tolerance is False  # 100 / 1705 base is well outside 1%


def test_missing_input_reports_none_not_zero():
    # dividends_paid is unmapped -- the RE roll-forward must say so, not
    # silently assume the company paid no dividend.
    periods = load_known_good()
    current, prior = periods[2023], periods[2022]
    current_missing_dividends = current.model_copy(
        update={
            "cash_flow_statement": current.cash_flow_statement.model_copy(
                update={"dividends_paid": None}
            )
        }
    )

    check = articulation.check_retained_earnings_rollforward(
        current_missing_dividends, prior
    )

    assert check.delta is None
    assert check.within_tolerance is None
    assert "dividends_paid" in check.missing_inputs


def test_indirect_reconciliation_tolerates_unmapped_sbc_and_deferred_tax():
    # Unlike dividends, stock comp / deferred tax default to 0 when unmapped
    # so the check still runs and surfaces the gap as a delta.
    periods = load_known_good()
    current, prior = periods[2023], periods[2022]
    current_no_sbc = current.model_copy(
        update={
            "cash_flow_statement": current.cash_flow_statement.model_copy(
                update={"stock_based_compensation": None, "deferred_income_tax": None}
            )
        }
    )

    check = articulation.check_indirect_reconciliation(current_no_sbc, prior)

    assert check.missing_inputs == ()
    # Original fixture had sbc=22, deferred_tax=6 baked into a tying CFO;
    # zeroing them out should shift computed CFO down by exactly 28.
    assert check.delta == Decimal("-28")


def test_articulation_on_normalized_synthetic_facts(two_year_facts):
    from statement_analyzer import normalize

    current = normalize.build_period(two_year_facts, 2023)
    prior = normalize.build_period(two_year_facts, 2022)

    checks = {c.name: c for c in articulation.run_checks(current, prior)}

    # Balance sheet totals were tagged directly in the fixture and tie exactly.
    bs_check = checks["Balance sheet balances (Assets = Liabilities + Equity)"]
    assert bs_check.delta == Decimal("0")

    # AR/Inventory/AP and dividends were never tagged in this fixture, so the
    # deltas that depend on them must say "not computable", not "zero".
    re_check = checks["Retained earnings roll-forward (RE_end = RE_begin + NI - Dividends)"]
    assert re_check.delta is None
    assert "dividends_paid" in re_check.missing_inputs

    indirect_check = checks["Indirect-method CFO reconciliation (NI + non-cash ± ΔWC = CFO)"]
    assert indirect_check.delta is None
    assert "accounts_receivable" in indirect_check.missing_inputs
