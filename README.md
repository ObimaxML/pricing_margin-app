# Peony Washing Powder Pricing & Margin Model

A Streamlit web app for modelling pricing, margins, first-order planning, and cash flow for a repackaging business.

The app is designed for a business that:
- buys `5kg` washing powder bags from a supplier,
- receives promotional free stock,
- repackages the product into smaller retail variants,
- tracks profitability,
- accounts for variable order costs like transport/collection,
- and compares supplier/customer payment terms such as `7-day`, `14-day`, and `30-day`.

## Features

### Core pricing and margin analysis
- Calculates effective bag cost after free promotional stock
- Calculates cost per gram
- Computes unit economics per product variant
- Shows:
  - product cost
  - packaging cost
  - total cost
  - selling price
  - profit per unit
  - margin %
  - markup %

### Order planning
- Budget-based first order planning
- Supports paid bags plus promotional free bags
- Allows custom first-order mix allocation by variant
- Shows:
  - paid bags
  - free bags
  - total grams available
  - grams used
  - utilisation %
  - total revenue
  - total profit

### Variable cost tracking
- Includes extra order-level costs such as:
  - transport / collection
  - other variable costs
- Variable costs are incorporated into:
  - total investment
  - projected profit after variable costs
  - ROI after variable costs
  - cash-at-risk analysis

### Payment terms analysis
Supports supplier and customer payment terms:
- Cash on Delivery
- 7-Day
- 14-Day
- 30-Day

The app calculates:
- supplier payment timing
- customer collection timing
- cash gap in days
- cash at risk before revenue is collected

It also includes a payment terms scenario comparison table across all supplier/customer combinations.

### Visualisations
- Profit per unit by variant
- Cost vs profit stacked chart
- Margin % comparison
- Unit distribution pie chart
- Revenue composition chart
- Weekly revenue targets
- Cumulative revenue and profit trend
- Cost composition pie chart
- Revenue-to-net-profit waterfall chart

### Export options
- Excel workbook with multiple sheets
- CSV export for:
  - unit economics
  - first order mix
  - weekly sales plan

## Project Structure

```text
pricing_margin_app/
├── app.py
├── logic.py
└── README.md