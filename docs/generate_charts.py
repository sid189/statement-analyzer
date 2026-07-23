"""Generate the five phase-illustration charts used in docs/learning/*.pdf.

Reads docs/learning/_data.json (produced by a one-off data pull against
cached real EDGAR data) and writes one PNG per phase. Not part of the
shipped CLI -- a content-generation script for the learning material.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e1e0d9",
    "grid.linewidth": 0.8,
    "axes.edgecolor": "#898781",
    "axes.labelcolor": "#333333",
    "text.color": "#0b0b0b",
    "xtick.color": "#52514e",
    "ytick.color": "#52514e",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREEN = "#0ca30c"
RED = "#d03b3b"

HERE = Path(__file__).parent
data = json.loads((HERE / "learning" / "_data.json").read_text())
OUT = HERE / "learning"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# --- Phase 1: raw filing complexity varies a lot by company ----------------
fig, ax = plt.subplots(figsize=(6.4, 3.4))
tickers = [c["entity_name"].split(" ")[0] if False else t for t, c in data["phase1"].items()]
tickers = list(data["phase1"].keys())
counts = [data["phase1"][t]["concept_count"] for t in tickers]
bars = ax.bar(tickers, counts, color=BLUE, width=0.55)
for b, c in zip(bars, counts):
    ax.text(b.get_x() + b.get_width() / 2, c + 8, f"{c:,}", ha="center", fontsize=10, color="#333333")
ax.set_ylabel("us-gaap concepts tagged")
ax.set_title("Phase 1 — raw filing size varies a lot by company", loc="left", fontsize=12, fontweight="bold")
ax.set_ylim(0, max(counts) * 1.18)
save(fig, "phase1_concept_counts.png")

# --- Phase 2: Apple revenue & net income trend ------------------------------
fig, ax = plt.subplots(figsize=(6.4, 3.6))
years = [r["fy"] for r in data["phase2"]]
rev = [r["revenue_b"] for r in data["phase2"]]
ni = [r["net_income_b"] for r in data["phase2"]]
ax.plot(years, rev, color=BLUE, linewidth=2, marker="o", markersize=4, label="Revenue")
ax.plot(years, ni, color=ORANGE, linewidth=2, marker="o", markersize=4, label="Net income")
ax.set_ylabel("$ billions")
ax.set_title("Phase 2 — Apple revenue & net income, FY2010–FY2025", loc="left", fontsize=12, fontweight="bold")
ax.legend(frameon=False, loc="upper left")
save(fig, "phase2_revenue_trend.png")

# --- Phase 3: Apple RE roll-forward delta grows -----------------------------
fig, ax = plt.subplots(figsize=(6.4, 3.6))
years3 = [r["fy"] for r in data["phase3"]]
deltas3 = [r["re_delta_b"] for r in data["phase3"]]
colors3 = [RED if (d is not None and abs(d) > 1) else GREEN for d in deltas3]
valid = [(y, d, c) for y, d, c in zip(years3, deltas3, colors3) if d is not None]
ax.bar([v[0] for v in valid], [v[1] for v in valid], color=[v[2] for v in valid], width=0.6)
ax.axhline(0, color="#c3c2b7", linewidth=1)
ax.set_ylabel("Delta, $ billions")
ax.set_title(
    "Phase 3 — retained-earnings check drifts as buybacks accumulate",
    loc="left", fontsize=12, fontweight="bold",
)
save(fig, "phase3_re_rollforward.png")

# --- Phase 4: Apple ROE and cash conversion cycle ---------------------------
fig, ax1 = plt.subplots(figsize=(6.4, 3.6))
years4 = [r["fy"] for r in data["phase4"]]
roe = [r["roe"] * 100 if r["roe"] is not None else None for r in data["phase4"]]
ax1.plot(years4, roe, color=BLUE, linewidth=2, marker="o", markersize=4)
ax1.set_ylabel("Return on equity, %", color=BLUE)
ax1.tick_params(axis="y", colors=BLUE)
ax1.set_title("Phase 4 — Apple's return on equity climbs as buybacks shrink equity", loc="left", fontsize=12, fontweight="bold")
save(fig, "phase4_roe_trend.png")

# --- Phase 5: cross-company RE-rollforward delta as % of net income --------
fig, ax = plt.subplots(figsize=(6.4, 4.0))
p5 = data["phase5"]
tickers5 = [r["ticker"] for r in p5]
pct5 = [r["re_delta_pct_of_net_income"] for r in p5]
colors5 = [GREEN if abs(v) < 5 else RED for v in pct5]
bars = ax.bar(tickers5, pct5, color=colors5, width=0.55, zorder=3)
for b, v in zip(bars, pct5):
    y, va = (v + 2, "bottom") if abs(v) < 1 else (v - 3, "top")
    ax.text(b.get_x() + b.get_width() / 2, y, f"{v:.1f}%", ha="center", va=va, fontsize=10, color="#333333")
ax.axhline(0, color="#c3c2b7", linewidth=1, zorder=2)
ax.set_ylabel("RE roll-forward delta, % of net income")
ax.set_ylim(min(pct5) * 1.18, 12)
ax.set_title(
    "Phase 5 — scaling the check across 5 companies\nshows it isn't universal",
    loc="left", fontsize=12, fontweight="bold", pad=10,
)
save(fig, "phase5_cross_company.png")

print("done")
