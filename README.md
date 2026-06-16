# 💰 Pricing & Margin Model

A professional Streamlit web app for a repackaging business that buys **5kg bags**
from a supplier (Peony Trading @ R95/bag), receives **promotional free stock**
(e.g. 5 free for every 50 ordered), and repackages the product into smaller
retail variants.

## Features

- **Interactive sidebar inputs** — supplier bag cost, free-stock (% or "X free per Y"),
  budget, order quantity, per-variant selling prices, packaging costs, and order mix.
- **Three analysis tabs**
  - **Unit Economics** — per-variant cost breakdown, profit, margin % and markup %.
  - **First Order Mix** — recommended mix for fastest cash turnover, with ROI.
  - **5-Week Sales Plan** — weekly targets and cumulative revenue/profit.
- **Visual charts** (Plotly) — profit by variant, cost vs profit, margin comparison,
  unit distribution, weekly revenue and cumulative progression.
- **Exports** — full multi-sheet **Excel** workbook plus per-table **CSV** downloads.
- **Effective costing** — free stock lowers the effective cost per bag and per gram.

## Variants (defaults)

| Variant | Weight | Packaging | Sell |
|---|---|---|---|
| 100g Mini Sachet | 100g | R0.40 | R5.00 |
| 200g Sachet | 200g | R0.70 | R9.50 |
| 500g Pack | 500g | R1.20 | R21.00 |
| 1kg Pack | 1000g | R1.80 | R36.00 |
| 2kg Pack | 2000g | R2.50 | R60.00 |
| 5kg Bulk | 5000g | R0.00 | R135.00 |

> Product cost per gram is derived from the **effective** bag cost
> (`bag_cost / (1 + free_fraction) / 5000`).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 (or the port shown in the terminal).

## Files
- `app.py` — Streamlit UI, charts, exports.
- `logic.py` — pure business-logic calculations (testable, no UI).
- `requirements.txt` — dependencies.
