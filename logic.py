"""
Pricing & Margin Model - Core Business Logic
=============================================
Business model:
  - Buy 5kg bags from supplier (Peony Trading) at a base cost (default R95/bag).
  - Promotional free stock (e.g. 5 free bags for every 50 ordered) lowers the
    EFFECTIVE cost per bag, which in turn lowers the cost per gram.
  - Repackage the bulk product into smaller retail variants, each carrying a
    packaging cost. Sell each variant at its own price.

All monetary values are in South African Rand (R).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration / defaults
# ---------------------------------------------------------------------------

BAG_WEIGHT_G = 5000  # grams in one supplier bag (5 kg)


@dataclass
class Variant:
    """A retail product variant produced from the bulk product."""

    name: str
    weight_g: int          # net product weight in grams
    packaging_cost: float  # packaging / labour cost per unit (R)
    sell_price: float      # retail selling price per unit (R)


def default_variants() -> List[Variant]:
    """Default variant catalogue derived from the conversation."""
    return [
        Variant("100g Mini Sachet", 100, 0.40, 5.00),
        Variant("200g Sachet", 200, 0.70, 9.50),
        Variant("500g Pack", 500, 1.20, 21.00),
        Variant("1kg Pack", 1000, 1.80, 36.00),
        Variant("2kg Pack", 2000, 2.50, 60.00),
        Variant("5kg Bulk", 5000, 0.00, 135.00),
    ]


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------

def effective_bag_cost(bag_cost: float, free_stock_pct: float) -> float:
    """Effective cost per bag after accounting for promotional free stock.

    free_stock_pct is expressed as a percentage of paid stock that comes free.
    E.g. "5 free for every 50 ordered" => 10% free.
    If you pay for 50 bags and get 5 free, you have 55 bags for the price of 50,
    so the effective cost per bag = paid_cost / (1 + free_fraction).
    """
    free_fraction = free_stock_pct / 100.0
    return bag_cost / (1.0 + free_fraction)


def cost_per_gram(bag_cost: float, free_stock_pct: float) -> float:
    """Effective raw product cost per gram."""
    return effective_bag_cost(bag_cost, free_stock_pct) / BAG_WEIGHT_G


# ---------------------------------------------------------------------------
# Unit economics
# ---------------------------------------------------------------------------

def unit_economics(
    variants: List[Variant],
    bag_cost: float,
    free_stock_pct: float,
) -> pd.DataFrame:
    """Build a DataFrame of per-unit cost breakdown and margins."""
    cpg = cost_per_gram(bag_cost, free_stock_pct)
    rows = []
    for v in variants:
        product_cost = cpg * v.weight_g
        total_cost = product_cost + v.packaging_cost
        profit = v.sell_price - total_cost
        margin_pct = (profit / v.sell_price * 100.0) if v.sell_price else 0.0
        markup_pct = (profit / total_cost * 100.0) if total_cost else 0.0
        rows.append(
            {
                "Variant": v.name,
                "Weight (g)": v.weight_g,
                "Product Cost (R)": round(product_cost, 2),
                "Packaging Cost (R)": round(v.packaging_cost, 2),
                "Total Cost (R)": round(total_cost, 2),
                "Sell Price (R)": round(v.sell_price, 2),
                "Profit / Unit (R)": round(profit, 2),
                "Margin %": round(margin_pct, 1),
                "Markup %": round(markup_pct, 1),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# First order mix
# ---------------------------------------------------------------------------

def first_order_mix(
    variants: List[Variant],
    bag_cost: float,
    free_stock_pct: float,
    budget: float,
    order_qty_bags: int,
    mix_weights: Dict[str, float] | None = None,
) -> Dict[str, object]:
    """Recommend a product mix for the first order.

    The number of bags is determined by ``order_qty_bags`` (capped by budget).
    The total available grams are distributed across variants according to
    ``mix_weights`` (a dict of variant name -> relative weight). If not given,
    a default mix favouring fast-moving small variants is used.
    """
    eff_cost = effective_bag_cost(bag_cost, free_stock_pct)

    # Cap order quantity by budget (paid bags only).
    max_affordable = int(budget // bag_cost) if bag_cost else 0
    paid_bags = min(order_qty_bags, max_affordable) if max_affordable else order_qty_bags
    paid_bags = max(paid_bags, 0)

    free_bags = int(paid_bags * (free_stock_pct / 100.0))
    total_bags = paid_bags + free_bags
    total_grams = total_bags * BAG_WEIGHT_G
    investment = paid_bags * bag_cost

    if mix_weights is None:
        mix_weights = {
            "100g Mini Sachet": 0.30,
            "200g Sachet": 0.25,
            "500g Pack": 0.20,
            "1kg Pack": 0.15,
            "2kg Pack": 0.07,
            "5kg Bulk": 0.03,
        }

    cpg = cost_per_gram(bag_cost, free_stock_pct)
    total_weight = sum(mix_weights.get(v.name, 0) for v in variants) or 1.0

    rows = []
    grams_used = 0
    for v in variants:
        share = mix_weights.get(v.name, 0) / total_weight
        grams_for_variant = total_grams * share
        units = int(grams_for_variant // v.weight_g)
        grams_used += units * v.weight_g

        product_cost = cpg * v.weight_g
        total_cost = product_cost + v.packaging_cost
        profit_unit = v.sell_price - total_cost
        rows.append(
            {
                "Variant": v.name,
                "Mix %": round(share * 100, 1),
                "Units": units,
                "Revenue (R)": round(units * v.sell_price, 2),
                "Cost (R)": round(units * total_cost, 2),
                "Profit (R)": round(units * profit_unit, 2),
            }
        )

    df = pd.DataFrame(rows)
    summary = {
        "paid_bags": paid_bags,
        "free_bags": free_bags,
        "total_bags": total_bags,
        "effective_bag_cost": round(eff_cost, 2),
        "investment": round(investment, 2),
        "total_revenue": round(df["Revenue (R)"].sum(), 2),
        "total_profit": round(df["Profit (R)"].sum(), 2),
        "grams_available": total_grams,
        "grams_used": grams_used,
    }
    summary["roi_pct"] = round(
        (summary["total_profit"] / investment * 100.0) if investment else 0.0, 1
    )
    return {"table": df, "summary": summary}


# ---------------------------------------------------------------------------
# 5-week sales plan
# ---------------------------------------------------------------------------

def weekly_sales_plan(
    total_units: int,
    total_revenue: float,
    total_profit: float,
    weeks: int = 5,
    ramp: List[float] | None = None,
) -> pd.DataFrame:
    """Distribute the first-order sell-through over several weeks.

    ``ramp`` gives relative sales weight per week (defaults to an increasing
    ramp to model growing momentum). Returns weekly + cumulative figures.
    """
    if ramp is None:
        ramp = [0.10, 0.15, 0.20, 0.25, 0.30][:weeks]
    if len(ramp) < weeks:
        ramp = ramp + [ramp[-1]] * (weeks - len(ramp))
    ramp = ramp[:weeks]
    total_w = sum(ramp) or 1.0

    rows = []
    cum_units = cum_rev = cum_profit = 0
    for i in range(weeks):
        share = ramp[i] / total_w
        u = round(total_units * share)
        rev = round(total_revenue * share, 2)
        prof = round(total_profit * share, 2)
        cum_units += u
        cum_rev += rev
        cum_profit += prof
        rows.append(
            {
                "Week": f"Week {i + 1}",
                "Target Units": u,
                "Revenue (R)": rev,
                "Profit (R)": prof,
                "Cumulative Units": cum_units,
                "Cumulative Revenue (R)": round(cum_rev, 2),
                "Cumulative Profit (R)": round(cum_profit, 2),
            }
        )
    return pd.DataFrame(rows)
