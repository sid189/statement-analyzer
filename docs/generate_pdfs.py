"""Generate the five phase learning PDFs into docs/learning/.

Not part of the shipped CLI -- run manually (after generate_charts.py) to
rebuild the learning material:

    pip install fpdf2 matplotlib
    python docs/generate_charts.py
    python docs/generate_pdfs.py
"""
from __future__ import annotations

from pathlib import Path

from pdf_builder import LearningPDF

OUT = Path(__file__).parent / "learning"


# ============================================================ PHASE 1 =====
def phase1():
    pdf = LearningPDF(1, "Ingest")
    pdf.title_block("Getting one company's raw SEC filings onto disk, reliably and cheaply re-usable.")

    pdf.h2("What this phase does")
    pdf.p(
        "Every US public company's financial filings are available, for free, as structured data: "
        "the SEC's XBRL \"companyfacts\" API returns one JSON document per company containing every "
        "number that company has ever tagged in any filing, going back years. Phase 1's whole job is "
        "narrow: resolve a ticker to a CIK (SEC's company identifier), fetch that JSON, and cache it "
        "to disk so nothing downstream ever needs the network again."
    )
    pdf.code([
        "GET https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        "  -> { \"entityName\": \"Apple Inc.\",",
        "       \"facts\": { \"us-gaap\": {",
        "         \"Assets\": { \"units\": { \"USD\": [",
        "           {\"end\": \"2023-09-30\", \"val\": 352583000000,",
        "            \"fy\": 2023, \"fp\": \"FY\", \"form\": \"10-K\", ...}",
        "         ] } }, ... } } }",
    ])

    pdf.h2("The core idea: cache everything, hit the network once")
    pdf.p(
        "SEC explicitly asks for a descriptive User-Agent with contact information and reasonable "
        "request rates -- this is a shared public resource, not a private API. The ingest layer sends "
        "that User-Agent on every request, retries transient failures (429s, 5xx) with exponential "
        "backoff, and writes every response to data/cache/, keyed by CIK. Every later phase reads "
        "through this same cache. The practical effect: you can iterate on normalization logic, run "
        "the tool a hundred times, and never re-download a byte from SEC after the first fetch."
    )

    pdf.h2("What real data looks like before you've done anything with it")
    pdf.p(
        "Even at the raw-ingest stage, one thing is already visible: companies don't tag the same "
        "amount of detail. The number of distinct us-gaap concepts a company has ever used varies "
        "by industry and filing history -- more concepts doesn't mean a bigger company, it means a "
        "more complex or more thoroughly-tagged one."
    )
    pdf.chart(
        str(OUT / "phase1_concept_counts.png"),
        "us-gaap concepts tagged, by company (from real cached companyfacts JSON).",
    )
    pdf.table(
        ["Company", "CIK", "us-gaap concepts", "Fiscal years cached"],
        [
            ["Apple Inc.", "0000320193", "503", "17"],
            ["Microsoft Corp.", "0000789019", "544", "16"],
            ["Walmart Inc.", "0000104169", "478", "17"],
            ["Johnson & Johnson", "0000200406", "609", "16"],
            ["Coca-Cola Co.", "0000021344", "724", "17"],
        ],
        col_widths=[55, 35, 40, 41],
    )

    pdf.callout(
        "Key takeaway",
        "Phase 1 deliberately does no interpretation at all -- it doesn't know what \"Assets\" means, "
        "it just fetches and caches. That discipline matters: when something looks wrong three phases "
        "later, you can always go back to the exact raw JSON on disk and know it hasn't been silently "
        "transformed anywhere upstream.",
    )
    pdf.output(str(OUT / "phase1_ingest.pdf"))
    print("wrote phase1_ingest.pdf")


# ============================================================ PHASE 2 =====
def phase2():
    pdf = LearningPDF(2, "Normalize + Model")
    pdf.title_block("Mapping messy, inconsistent XBRL tags onto one clean, typed representation of a company-year.")

    pdf.h2("What this phase does")
    pdf.p(
        "Two companies reporting the same economic fact -- cost of goods sold, say -- often use "
        "different XBRL tags for it. normalize.py holds a table of canonical line item -> candidate "
        "tags, tried in order, and assembles the result into typed pydantic models (IncomeStatement, "
        "BalanceSheet, CashFlowStatement) where every field is Decimal or None -- never float, and "
        "never a fabricated zero standing in for \"we don't know.\""
    )

    pdf.h2("A real bug this phase caught: SEC's fy/fp field is not what it looks like")
    pdf.p(
        "It's tempting to assume a fact's \"fy\" field tells you which fiscal year that number covers. "
        "It doesn't -- fy/fp describe the filing's own fiscal focus, not the period an individual fact "
        "covers. A single 10-K reports 2-3 years of comparative figures, and every one of those rows "
        "is stamped with that filing's own fy. Filtering on fy == target_year silently pulled the "
        "wrong year's numbers in an early version of this tool; the bug only surfaced when printing a "
        "\"FY2023\" model against real Apple data showed FY2021's date range. The fix: anchor the "
        "target period by finding the row with the latest end-date within that fy/fp group, then match "
        "every other concept purely by (start, end) dates -- which also correctly picks up a restated "
        "value filed later, since a restatement shows up as a comparative row in a subsequent 10-K "
        "carrying that later filing's own fy."
    )

    pdf.h2("Real cross-company tag divergence found while hardening this phase")
    pdf.bullets([
        "Walmart and Coca-Cola never tag a total \"Liabilities\" concept at all, in any filing -- "
        "their balance sheets simply don't present that subtotal as its own XBRL fact.",
        "Johnson & Johnson hasn't tagged \"OperatingIncomeLoss\" directly since 2014.",
        "Microsoft tags Selling & Marketing and General & Administrative expense as two separate "
        "concepts, with no combined SG&A tag at all.",
        "JNJ and Coca-Cola tag common stock par value and additional paid-in capital as separate "
        "concepts; JNJ doesn't tag APIC at all in recent filings.",
    ])
    pdf.p(
        "None of these are bugs in the filing -- they're legitimate differences in how each company's "
        "10-K is structured. normalize.py handles them with derivation: sum the parts when a combined "
        "tag is missing (SG&A = Selling + G&A), or take the difference of two totals that are always "
        "tagged (Liabilities = Assets - Equity). A component that's genuinely absent (not every "
        "company tags additional paid-in capital) is treated as 0 only when deriving a sum -- never "
        "silently assumed elsewhere."
    )

    pdf.chart(
        str(OUT / "phase2_revenue_trend.png"),
        "Apple's revenue and net income, normalized from raw XBRL facts across 16 fiscal years.",
    )

    pdf.callout(
        "Key takeaway",
        "The typed model's real value isn't the numbers it successfully fills in -- it's the fields it "
        "leaves as None. A missing value that propagates cleanly through every downstream calculation "
        "is honest; a missing value silently treated as zero would quietly corrupt every ratio and "
        "check built on top of it.",
    )
    pdf.output(str(OUT / "phase2_normalize_model.pdf"))
    print("wrote phase2_normalize_model.pdf")


# ============================================================ PHASE 3 =====
def phase3():
    pdf = LearningPDF(3, "Articulation")
    pdf.title_block("The pedagogical core: do the three statements actually tie together?")

    pdf.h2("The four checks, and the accounting idea behind each")
    pdf.table(
        ["Check", "What it verifies"],
        [
            ["Balance sheet balances", "Assets = Liabilities + Equity, always, by definition"],
            ["Retained earnings roll-forward", "RE_end = RE_begin + Net income - Dividends"],
            ["Cash ties out", "Ending cash on the cash flow statement = cash on the balance sheet"],
            ["Indirect-method reconciliation", "Net income + non-cash items +/- working capital = cash from ops"],
        ],
        col_widths=[70, 101],
    )
    pdf.p(
        "Every check reports a signed dollar delta scaled against a 1%-of-base tolerance -- never a "
        "pass/fail boolean. That's deliberate: a check that fails on real data is showing you "
        "something true about the filing or about a gap in normalize.py's tag map, and hiding it "
        "behind a green checkmark would throw away the lesson."
    )

    pdf.h2("The accruals lesson, specifically")
    pdf.p(
        "The fourth check is the heart of the exercise. Net income is an accrual number: it recognizes "
        "revenue when earned and expenses when incurred, not when cash actually moves. The indirect "
        "method reconciles the two by adding back non-cash charges (depreciation, stock compensation) "
        "and adjusting for the timing gaps in working capital -- if receivables went up, some of this "
        "period's revenue hasn't been collected in cash yet, so that increase is subtracted; if payables "
        "went up, some expenses haven't been paid in cash yet, so that increase is added back. This "
        "tool recomputes those deltas straight from two balance sheets, rather than trusting a "
        "company's own tagged \"change in receivables\" figure, specifically so the two can be checked "
        "against each other."
    )

    pdf.h2("A real, large delta that is a lesson, not a bug")
    pdf.p(
        "Apple's retained-earnings check shows a delta of -$91.7 billion in FY2025, and the gap has "
        "grown every year since Apple started paying dividends in 2012. This is not a tagging error: "
        "Apple retires the shares it repurchases and charges the excess over par value against "
        "retained earnings, rather than holding them in a separate treasury-stock account. The "
        "textbook formula RE_end = RE_begin + NI - Dividends has no term for that, so the delta grows "
        "every year buybacks happen -- and the size of the delta is itself a rough measure of how much "
        "share retirement is charged against retained earnings that period."
    )
    pdf.chart(
        str(OUT / "phase3_re_rollforward.png"),
        "Apple's retained-earnings roll-forward delta, FY2013-FY2025 (no delta is computable before "
        "FY2013 -- Apple paid no dividends before August 2012, so \"dividends paid\" is genuinely "
        "unmapped, not zero).",
    )

    pdf.callout(
        "Key takeaway",
        "A large articulation delta on real data is usually teaching you something real -- either "
        "about the filer's specific accounting choices, or about a line item your tag map hasn't "
        "reached yet. The check's job is to surface that gap clearly, with a real dollar number "
        "attached, not to decide whether it's \"okay.\"",
    )
    pdf.output(str(OUT / "phase3_articulation.pdf"))
    print("wrote phase3_articulation.pdf")


# ============================================================ PHASE 4 =====
def phase4():
    pdf = LearningPDF(4, "Ratios")
    pdf.title_block("Liquidity, leverage, profitability, and efficiency, computed on a validated model.")

    pdf.h2("The four families")
    pdf.table(
        ["Family", "Question it answers"],
        [
            ["Liquidity", "Can the company cover short-term obligations? (current, quick, cash ratios)"],
            ["Leverage", "How much of the balance sheet is debt-financed? (debt/equity, interest coverage)"],
            ["Profitability", "How much of revenue turns into profit, and profit relative to capital? (margins, ROA, ROE)"],
            ["Efficiency", "How fast do assets and working capital turn over into revenue? (turnover, days ratios)"],
        ],
        col_widths=[35, 136],
    )

    pdf.h2("Why some ratios need a prior year, and what happens without one")
    pdf.p(
        "Net income accrues over an entire fiscal year, but a balance sheet total is a single point-in-"
        "time snapshot. Dividing this year's net income by this year's ending total assets (or equity) "
        "compares a flow to one arbitrary instant, which becomes noisy exactly when the balance changed "
        "a lot mid-year. Averaging the beginning and ending balance is the standard fix for return-on-"
        "assets, return-on-equity, and every turnover/days ratio here -- and it means those specific "
        "ratios come back None, not a misleading ending-balance-only number, whenever a prior period "
        "isn't available. Everything else (liquidity, leverage, margins) only needs the current period."
    )

    pdf.h2("What the same ratio can mean two different things")
    pdf.p(
        "Apple's return on equity climbed from roughly 40% in FY2011 to 175% by FY2022. Read naively, "
        "that looks like a dramatically more profitable business. It isn't, mostly: equity is the "
        "denominator, and years of share buybacks shrank it faster than profits grew. A rising ROE "
        "driven by a shrinking denominator is a different story than one driven by a growing numerator "
        "-- the ratio alone can't tell you which, you have to look at what moved."
    )
    pdf.chart(
        str(OUT / "phase4_roe_trend.png"),
        "Apple's return on equity, FY2011-FY2025 -- the climb tracks buyback-driven equity reduction "
        "more than profit growth.",
    )

    pdf.h2("A genuinely useful number: the cash conversion cycle")
    pdf.p(
        "Apple's FY2023 cash conversion cycle is -70.9 days: it collects from customers in about 27 "
        "days, turns over inventory in about 10, but doesn't pay its own suppliers for about 108 days. "
        "The negative result means Apple is, in effect, financed by its suppliers rather than the "
        "other way around -- a real, well-known structural advantage of its scale and supplier "
        "leverage, and a case where the ratio genuinely does tell a clean story on its own."
    )

    pdf.callout(
        "Key takeaway",
        "A ratio is a lens, not a verdict -- the same number can be read as \"strong business\" or "
        "\"financial engineering\" depending on which side of the fraction actually moved. Computing "
        "the ratio is the easy part; knowing what moved is the actual analysis.",
    )
    pdf.output(str(OUT / "phase4_ratios.pdf"))
    print("wrote phase4_ratios.pdf")


# ============================================================ PHASE 5 =====
def phase5():
    pdf = LearningPDF(5, "Scale + Report")
    pdf.title_block("Multi-year trend tables, a real report layer -- and testing the whole pipeline against five companies.")

    pdf.h2("What this phase adds")
    pdf.p(
        "Phases 1-4 work one fiscal year (and, where needed, its prior year) at a time. Phase 5 "
        "assembles a whole range of years into pandas DataFrames -- line item by year, ratio by year, "
        "articulation check by year -- and renders them as rich terminal tables. pandas enters the "
        "project only here, on purpose: it's the one tool actually suited to a line-item x year trend "
        "table, and every cell holds a Decimal or None object, never a float, so multi-year tables "
        "never quietly round through binary floating point."
    )
    pdf.p(
        "A year that can't be normalized is skipped, not fatal -- the rest of the requested range still "
        "renders, with a note about what was skipped. A year at the edge of the requested range with no "
        "fetched prior year correctly shows the prior-dependent figures as unmapped rather than "
        "reaching outside the range or guessing."
    )

    pdf.h2("Scale as a debugging tool, not just a feature")
    pdf.p(
        "The most valuable thing about running five real companies through this pipeline wasn't more "
        "data -- it was finding out where the model was quietly wrong. Walmart and Coca-Cola never tag "
        "a total \"Liabilities\" concept at all, which would have silently broken the single most basic "
        "check in the whole tool (Assets = Liabilities + Equity) for two of five companies tested. That "
        "kind of gap doesn't show up testing one company carefully -- it shows up testing several "
        "companies casually. After adding a derivation (total_liabilities = total_liabilities_and_equity "
        "- total_equity when the direct tag is absent), all five companies tie exactly."
    )

    pdf.h2("Scale also answers a question one company can't: is this pattern universal?")
    pdf.p(
        "Phase 3's retained-earnings finding on Apple -- a growing delta from buyback-driven treasury "
        "stock retirement -- could have been an Apple-specific quirk. Running the same check across "
        "five companies' latest fiscal years, scaled to each company's own net income for a fair "
        "comparison, shows it isn't universal at all: Johnson & Johnson and Coca-Cola tie almost "
        "exactly, while Apple, Microsoft, and Walmart show real, material drift."
    )
    pdf.chart(
        str(OUT / "phase5_cross_company.png"),
        "Retained-earnings roll-forward delta, latest fiscal year per company, as a percentage of that "
        "year's net income.",
    )
    pdf.table(
        ["Company", "Delta ($B)", "Delta (% of net income)"],
        [
            ["Apple", "-91.7", "-81.9%"],
            ["Microsoft", "-13.2", "-12.9%"],
            ["Walmart", "-7.9", "-36.2%"],
            ["Johnson & Johnson", "-1.2", "-4.6%"],
            ["Coca-Cola", "0.0", "0.0%"],
        ],
        col_widths=[70, 45, 56],
    )

    pdf.callout(
        "Key takeaway",
        "One company's result can look like a bug, an outlier, or a lesson -- you often can't tell "
        "which from a single data point. Five companies' results turn the same check into a real "
        "comparison, and that's exactly when a pattern like \"buybacks distort the RE roll-forward\" "
        "stops being a guess and becomes something you've actually shown.",
    )
    pdf.output(str(OUT / "phase5_report.pdf"))
    print("wrote phase5_report.pdf")


if __name__ == "__main__":
    phase1()
    phase2()
    phase3()
    phase4()
    phase5()
