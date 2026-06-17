from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Dict, List

import pandas as pd


BAG_GRAMS = 5000


@dataclass
class Variant:
    name: str
    grams: int
    sell_price: float
    packaging_cost: float = 0.0


def default_variants() -> List[Variant]:
    return [
        Variant("100g Mini Sachet", 100, 4.00, 0.25),
        Variant("200g Sachet", 200, 7.00, 0.35),
        Variant("500g Pack", 500, 16.00, 0.80),
        Variant("1kg Pack", 1000, 30.00, 1.20),
        Variant("2kg Pack", 2000, 55.00, 1.80),
        Variant("5kg Bulk", 5000, 120.00, 0.00),
    ]


def cost_per_gram(bag_cost: float, free_stock_pct: float) -> float:
    effective_grams_received = BAG_GRAMS * (1 + free_stock_pct / 100)
    if effective_grams_received <= 0:
        return 0.0
    return bag_cost / effective_grams_received


def effective_bag_cost(bag_cost: float, free_stock_pct: float) -> float:
    total_bags_received_per_paid_bag = 1 + free_stock_pct / 100
    if total_bags_received_per_paid_bag <= 0:
        return 0.0
    return bag_cost / total_bags_received_per_paid_bag


def unit_economics(
    variants: List[Variant],
    bag_cost: float,
    free_stock_pct: float,
) -> pd.DataFrame:
    cpg = cost_per_gram(bag_cost, free_stock_pct)

    rows = []
    for v in variants:
        product_cost = v.grams * cpg
        total_cost = product_cost + v.packaging_cost
        profit = v.sell_price - total_cost
        margin_pct = (profit / v.sell_price * 100) if v.sell_price else 0.0
        markup_pct = (profit / total_cost * 100) if total_cost else 0.0

        rows.append(
            {
                "Variant": v.name,
                "Size (g)": v.grams,
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


def _normalise_mix(mix_weights: Dict[str, float], variants: List[Variant]) -> Dict[str, float]:
    usable = {v.name: max(0.0, float(mix_weights.get(v.name, 0))) for v in variants}
    total = sum(usable.values())

    if total <= 0:
        equal_weight = 100 / len(variants) if variants else 0
        return {v.name: equal_weight for v in variants}

    return {name: (weight / total) * 100 for name, weight in usable.items()}


def first_order_mix(
    variants: List[Variant],
    bag_cost: float,
    free_stock_pct: float,
    budget: float,
    order_qty_bags: int,
    mix_weights: Dict[str, float],
    variable_cost: float = 0.0,
) -> Dict[str, pd.DataFrame | dict]:
    budget_for_stock = max(0.0, budget - variable_cost)
    affordable_paid_bags = int(budget_for_stock // bag_cost) if bag_cost > 0 else 0
    paid_bags = min(order_qty_bags, affordable_paid_bags)

    free_bags = int(round(paid_bags * free_stock_pct / 100))
    total_bags_available = paid_bags + free_bags
    grams_available = total_bags_available * BAG_GRAMS

    cpg = cost_per_gram(bag_cost, free_stock_pct)
    norm_mix = _normalise_mix(mix_weights, variants)

    rows = []
    grams_used = 0
    total_revenue = 0.0
    total_cost = 0.0

    for i, v in enumerate(variants):
        mix_pct = norm_mix[v.name]
        target_grams = grams_available * (mix_pct / 100)

        if i == len(variants) - 1:
            remaining_grams = max(0, grams_available - grams_used)
            units = floor(remaining_grams / v.grams) if v.grams > 0 else 0
        else:
            units = floor(target_grams / v.grams) if v.grams > 0 else 0

        grams_for_variant = units * v.grams
        product_cost = grams_for_variant * cpg
        packaging_cost = units * v.packaging_cost
        cost = product_cost + packaging_cost
        revenue = units * v.sell_price
        profit = revenue - cost

        grams_used += grams_for_variant
        total_revenue += revenue
        total_cost += cost

        rows.append(
            {
                "Variant": v.name,
                "Mix %": round(mix_pct, 1),
                "Grams / Unit": v.grams,
                "Units": int(units),
                "Revenue (R)": round(revenue, 2),
                "Cost (R)": round(cost, 2),
                "Profit (R)": round(profit, 2),
            }
        )

    order_df = pd.DataFrame(rows)

    stock_investment = round(paid_bags * bag_cost, 2)
    total_profit = round(total_revenue - total_cost, 2)
    roi_pct = (total_profit / stock_investment * 100) if stock_investment else 0.0

    summary = {
        "paid_bags": paid_bags,
        "free_bags": free_bags,
        "effective_bag_cost": round(effective_bag_cost(bag_cost, free_stock_pct), 2),
        "investment": stock_investment,
        "variable_cost": round(variable_cost, 2),
        "total_revenue": round(total_revenue, 2),
        "total_profit": round(total_profit, 2),
        "roi_pct": round(roi_pct, 1),
        "grams_available": int(grams_available),
        "grams_used": int(grams_used),
        "budget_for_stock": round(budget_for_stock, 2),
        "budget_total": round(budget, 2),
    }

    return {"table": order_df, "summary": summary}


def weekly_sales_plan(
    total_units: int,
    total_revenue: float,
    total_profit: float,
    weeks: int = 5,
) -> pd.DataFrame:
    if weeks <= 0:
        weeks = 1

    base_units = total_units // weeks
    extra_units = total_units % weeks

    revenue_per_week = total_revenue / weeks if weeks else 0.0
    profit_per_week = total_profit / weeks if weeks else 0.0

    rows = []
    cum_revenue = 0.0
    cum_profit = 0.0

    for week in range(1, weeks + 1):
        units = base_units + (1 if week <= extra_units else 0)
        revenue = round(revenue_per_week, 2)
        profit = round(profit_per_week, 2)

        cum_revenue += revenue
        cum_profit += profit

        rows.append(
            {
                "Week": f"Week {week}",
                "Units": int(units),
                "Revenue (R)": revenue,
                "Profit (R)": profit,
                "Cumulative Revenue (R)": round(cum_revenue, 2),
                "Cumulative Profit (R)": round(cum_profit, 2),
            }
        )

    return pd.DataFrame(rows)