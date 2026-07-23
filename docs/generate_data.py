"""Pull the real data behind docs/learning/*.pdf and its charts into
docs/learning/_data.json. Not part of the shipped CLI -- run this first,
then generate_charts.py, then generate_pdfs.py, whenever the learning
material needs to be rebuilt (e.g. after extending normalize.py's tag map,
or to refresh against newly-filed fiscal years).

Requires SEC_USER_AGENT to be set, same as the CLI itself. Uses the ordinary
ingest/normalize/articulation/ratios modules -- the numbers here are exactly
what `statement-analyzer <TICKER> --report ...` would show.
"""
from __future__ import annotations

import json
from pathlib import Path

from statement_analyzer import articulation, ingest, normalize, ratios

COMPANIES = ["AAPL", "MSFT", "WMT", "JNJ", "KO"]
OUT = Path(__file__).parent / "learning" / "_data.json"


def d(x):
    return float(x) if x is not None else None


def main():
    facts_by_ticker = {t: ingest.fetch_company_facts(t) for t in COMPANIES}

    # Phase 1: raw filing complexity per company
    phase1 = {
        t: {
            "entity_name": f["entityName"],
            "cik": str(f["cik"]).zfill(10),
            "concept_count": len(f.get("facts", {}).get("us-gaap", {})),
            "years_available": len(normalize.available_fiscal_years(f)),
        }
        for t, f in facts_by_ticker.items()
    }

    # Phases 2-4: Apple's own multi-year trend, FY2010-FY2025
    aapl_facts = facts_by_ticker["AAPL"]
    years = list(range(2010, 2026))
    periods = {y: normalize.build_period(aapl_facts, y) for y in years}

    phase2 = []
    for y in years:
        p = periods[y]
        phase2.append({
            "fy": y,
            "revenue_b": d(p.income_statement.revenue) / 1e9 if p.income_statement.revenue else None,
            "net_income_b": d(p.income_statement.net_income) / 1e9 if p.income_statement.net_income else None,
        })

    phase3, phase4 = [], []
    for y in years:
        if y - 1 not in periods:
            continue
        prior, current = periods[y - 1], periods[y]
        checks = {c.name.split(" (")[0]: c for c in articulation.run_checks(current, prior)}
        re_check = checks["Retained earnings roll-forward"]
        phase3.append({
            "fy": y,
            "re_delta_b": d(re_check.delta) / 1e9 if re_check.delta is not None else None,
        })
        rs = ratios.compute_ratios(current, prior)
        phase4.append({
            "fy": y,
            "roe": d(rs.profitability.return_on_equity),
            "ccc": d(rs.efficiency.cash_conversion_cycle),
        })

    # Phase 5: cross-company comparison, latest fiscal year per company,
    # scaled by net income rather than the RE balance itself -- Apple's RE
    # balance is near zero from buybacks, which makes %-of-RE blow up.
    phase5 = []
    for t in COMPANIES:
        f = facts_by_ticker[t]
        yrs = sorted(normalize.available_fiscal_years(f), reverse=True)
        y2, y1 = yrs[0], yrs[1]
        current, prior = normalize.build_period(f, y2), normalize.build_period(f, y1)
        checks = {c.name.split(" (")[0]: c for c in articulation.run_checks(current, prior)}
        re_check = checks["Retained earnings roll-forward"]
        ni = current.income_statement.net_income
        phase5.append({
            "ticker": t,
            "fy": y2,
            "re_delta_b": float(re_check.delta) / 1e9,
            "re_delta_pct_of_net_income": float(re_check.delta) / float(ni) * 100,
        })

    out = {"phase1": phase1, "phase2": phase2, "phase3": phase3, "phase4": phase4, "phase5": phase5}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
