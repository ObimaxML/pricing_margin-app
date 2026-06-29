"""
Pricing & Margin Model - Streamlit Web App
===========================================
Interactive calculator for a repackaging business that buys 5kg bags from a
supplier, receives promotional free stock, and resells smaller variants.

Run with: python -m streamlit run app.py
"""

from __future__ import annotations

import io
import json
import random
import re
from pathlib import Path
from typing import Any
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import logic


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURRENCY = "R"
FIVE_KG_GRAMS = 5000
SESSION_FILE = Path(__file__).with_name("peony_pricing_session.json")
CAMPAIGN_FILE = Path(__file__).with_name("peony_marketing_campaigns.json")

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
PEONY_LOGO = ASSETS_DIR / "peony_logo.png"

# If peony_logo.png is not found, automatically use the first image in /assets.
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def get_logo_path() -> Path | None:
    if PEONY_LOGO.exists():
        return PEONY_LOGO

    if not ASSETS_DIR.exists():
        return None

    image_files = sorted(
        p for p in ASSETS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )

    return image_files[0] if image_files else None


# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Peony Washing Powder Pricing & Margin Model",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .main .block-container {padding-top: 2rem;}
        h1, h2, h3 {color: #1f2a44;}
        div[data-testid="stMetricValue"] {font-size: 1.6rem;}
        .stTabs [data-baseweb="tab-list"] {gap: 8px;}
        .stTabs [data-baseweb="tab"] {
            background: #f0f2f6;
            border-radius: 8px 8px 0 0;
            padding: 10px 18px;
        }
        .stTabs [aria-selected="true"] {
            background: #1f77b4;
            color: white;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session persistence helpers
# ---------------------------------------------------------------------------

def load_saved_session() -> dict[str, Any]:
    if not SESSION_FILE.exists():
        return {}

    try:
        with SESSION_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

        return {}
    except Exception:
        return {}


def is_json_safe(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, type(None)))


def save_current_session() -> None:
    data = {
        key: value
        for key, value in st.session_state.items()
        if is_json_safe(value)
    }

    with SESSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def init_state(key: str, default: Any, saved_session: dict[str, Any]) -> None:
    if key not in st.session_state:
        st.session_state[key] = saved_session.get(key, default)


# ---------------------------------------------------------------------------
# Campaign persistence helpers
# ---------------------------------------------------------------------------

def load_campaigns() -> dict[str, Any]:
    """
    Loads saved marketing campaigns and sales records from a local JSON file.

    Structure:
    {
        "Campaign Name": {
            "name": "Campaign Name",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "sales_records": [...]
        }
    }
    """
    if not CAMPAIGN_FILE.exists():
        return {}

    try:
        with CAMPAIGN_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_campaigns(campaigns: dict[str, Any]) -> None:
    with CAMPAIGN_FILE.open("w", encoding="utf-8") as f:
        json.dump(campaigns, f, indent=2)


def date_to_iso(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):
        return value

    return date.today().isoformat()


def iso_to_date(value: Any, fallback: date | None = None) -> date:
    if fallback is None:
        fallback = date.today()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return fallback

    return fallback


def get_campaign_options(campaigns: dict[str, Any]) -> list[str]:
    return sorted(campaigns.keys())


def upsert_campaign(
    campaigns: dict[str, Any],
    campaign_name: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    clean_name = campaign_name.strip()

    if not clean_name:
        return campaigns

    existing_campaign = campaigns.get(clean_name, {})

    campaigns[clean_name] = {
        "name": clean_name,
        "start_date": date_to_iso(start_date),
        "end_date": date_to_iso(end_date),
        "sales_records": existing_campaign.get("sales_records", []),
    }

    return campaigns


def add_campaign_sale(
    campaigns: dict[str, Any],
    campaign_name: str,
    sale_date: date,
    outlet: str,
    variant: str,
    units_sold: int,
    sell_price: float,
    notes: str = "",
) -> dict[str, Any]:
    clean_name = campaign_name.strip()

    if clean_name not in campaigns:
        return campaigns

    revenue = float(units_sold) * float(sell_price)

    campaigns[clean_name].setdefault("sales_records", []).append(
        {
            "sale_id": f"SALE-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{random.randint(1000, 9999)}",
            "sale_date": date_to_iso(sale_date),
            "outlet": outlet,
            "variant": variant,
            "units_sold": int(units_sold),
            "sell_price": float(sell_price),
            "revenue": revenue,
            "notes": notes.strip(),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
    )

    return campaigns




def delete_campaign_sale_at_index(
    campaigns: dict[str, Any],
    campaign_name: str,
    record_index: int,
) -> dict[str, Any]:
    clean_name = campaign_name.strip()

    if clean_name not in campaigns:
        return campaigns

    records = campaigns[clean_name].get("sales_records", [])

    if not isinstance(records, list):
        campaigns[clean_name]["sales_records"] = []
        return campaigns

    if 0 <= int(record_index) < len(records):
        records.pop(int(record_index))

    campaigns[clean_name]["sales_records"] = records
    return campaigns


def clear_campaign_sales(
    campaigns: dict[str, Any],
    campaign_name: str,
) -> dict[str, Any]:
    clean_name = campaign_name.strip()

    if clean_name in campaigns:
        campaigns[clean_name]["sales_records"] = []

    return campaigns

def build_campaign_sales_df(campaign: dict[str, Any] | None) -> pd.DataFrame:
    if not campaign:
        return pd.DataFrame()

    records = campaign.get("sales_records", [])

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if "sale_date" in df.columns:
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.date

    if "units_sold" in df.columns:
        df["units_sold"] = df["units_sold"].fillna(0).astype(int)

    if "sell_price" in df.columns:
        df["sell_price"] = df["sell_price"].fillna(0.0).astype(float)

    if "revenue" in df.columns:
        df["revenue"] = df["revenue"].fillna(0.0).astype(float)

    return df


def build_campaign_progress(
    campaign: dict[str, Any] | None,
    order_df: pd.DataFrame,
    outlet_detail_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns two views:
    1. variant_progress_df: planned/available units vs actual campaign sales.
    2. outlet_progress_df: allocated outlet units vs actual outlet sales.
    """
    campaign_sales_df = build_campaign_sales_df(campaign)

    if order_df.empty or "Variant" not in order_df.columns:
        return pd.DataFrame(), pd.DataFrame()

    available_df = order_df[["Variant", "Units"]].copy()
    available_df = available_df.rename(columns={"Units": "Available Units"})

    if campaign_sales_df.empty:
        sold_by_variant = pd.DataFrame(columns=["Variant", "Units Sold", "Actual Revenue (R)"])
        sold_by_outlet = pd.DataFrame(columns=["Outlet", "Variant", "Units Sold", "Actual Revenue (R)"])
    else:
        sold_by_variant = (
            campaign_sales_df
            .groupby("variant", as_index=False)
            .agg(
                {
                    "units_sold": "sum",
                    "revenue": "sum",
                }
            )
            .rename(
                columns={
                    "variant": "Variant",
                    "units_sold": "Units Sold",
                    "revenue": "Actual Revenue (R)",
                }
            )
        )

        sold_by_outlet = (
            campaign_sales_df
            .groupby(["outlet", "variant"], as_index=False)
            .agg(
                {
                    "units_sold": "sum",
                    "revenue": "sum",
                }
            )
            .rename(
                columns={
                    "outlet": "Outlet",
                    "variant": "Variant",
                    "units_sold": "Units Sold",
                    "revenue": "Actual Revenue (R)",
                }
            )
        )

    variant_progress_df = available_df.merge(sold_by_variant, on="Variant", how="left")
    variant_progress_df["Units Sold"] = variant_progress_df["Units Sold"].fillna(0).astype(int)
    variant_progress_df["Actual Revenue (R)"] = variant_progress_df["Actual Revenue (R)"].fillna(0.0)
    variant_progress_df["Remaining Units"] = (
        variant_progress_df["Available Units"] - variant_progress_df["Units Sold"]
    )

    variant_progress_df["Sell-through %"] = variant_progress_df.apply(
        lambda row: (
            row["Units Sold"] / row["Available Units"] * 100
            if row["Available Units"]
            else 0
        ),
        axis=1,
    )

    if outlet_detail_df.empty:
        outlet_progress_df = sold_by_outlet.copy()
    else:
        allocated_df = outlet_detail_df[
            ["Outlet", "Variant", "Units Allocated", "Revenue (R)", "Profit (R)"]
        ].copy()

        allocated_df = allocated_df.rename(
            columns={
                "Revenue (R)": "Projected Revenue (R)",
                "Profit (R)": "Projected Profit (R)",
            }
        )

        outlet_progress_df = allocated_df.merge(
            sold_by_outlet,
            on=["Outlet", "Variant"],
            how="left",
        )

        outlet_progress_df["Units Sold"] = outlet_progress_df["Units Sold"].fillna(0).astype(int)
        outlet_progress_df["Actual Revenue (R)"] = outlet_progress_df["Actual Revenue (R)"].fillna(0.0)
        outlet_progress_df["Remaining Allocated Units"] = (
            outlet_progress_df["Units Allocated"] - outlet_progress_df["Units Sold"]
        )

        outlet_progress_df["Outlet Sell-through %"] = outlet_progress_df.apply(
            lambda row: (
                row["Units Sold"] / row["Units Allocated"] * 100
                if row["Units Allocated"]
                else 0
            ),
            axis=1,
        )

    return variant_progress_df, outlet_progress_df



saved_session = load_saved_session()
campaigns = load_campaigns()


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def money(x: float) -> str:
    return f"{CURRENCY}{x:,.2f}"


def get_variant_grams(variant) -> float:
    possible_attrs = [
        "grams",
        "size_g",
        "weight_g",
        "gram_weight",
        "pack_size_g",
        "unit_grams",
    ]

    for attr in possible_attrs:
        if hasattr(variant, attr):
            value = getattr(variant, attr)
            if value is not None:
                return float(value)

    name = str(getattr(variant, "name", "")).lower()

    kg_match = re.search(r"(\d+(?:\.\d+)?)\s*kg", name)
    if kg_match:
        return float(kg_match.group(1)) * 1000

    g_match = re.search(r"(\d+(?:\.\d+)?)\s*g", name)
    if g_match:
        return float(g_match.group(1))

    return 0.0


def add_5kg_equivalent_column(order_df: pd.DataFrame, variants) -> pd.DataFrame:
    df = order_df.copy()

    variant_gram_map = {
        v.name: get_variant_grams(v)
        for v in variants
    }

    if "Variant" not in df.columns or "Units" not in df.columns:
        return df

    df["5kg Packs Equivalent"] = df.apply(
        lambda row: (
            float(row["Units"]) * variant_gram_map.get(row["Variant"], 0.0)
        ) / FIVE_KG_GRAMS,
        axis=1,
    )

    cols = list(df.columns)

    if "Units" in cols and "5kg Packs Equivalent" in cols:
        cols.remove("5kg Packs Equivalent")
        units_index = cols.index("Units")
        cols.insert(units_index + 1, "5kg Packs Equivalent")
        df = df[cols]

    return df


def build_mix_explanation(order_df: pd.DataFrame, variants) -> pd.DataFrame:
    df = order_df.copy()

    variant_gram_map = {
        v.name: get_variant_grams(v)
        for v in variants
    }

    if "Variant" not in df.columns or "Units" not in df.columns:
        return pd.DataFrame()

    df["Variant Size (g)"] = df["Variant"].map(variant_gram_map)
    df["Derived Grams Used"] = df["Units"] * df["Variant Size (g)"]

    df["Formula"] = df.apply(
        lambda row: (
            f"{row['Derived Grams Used']:,.0f}g ÷ "
            f"{row['Variant Size (g)']:,.0f}g = "
            f"{row['Units']:,.0f} units"
        ),
        axis=1,
    )

    return df[
        [
            "Variant",
            "Variant Size (g)",
            "Units",
            "5kg Packs Equivalent",
            "Derived Grams Used",
            "Formula",
        ]
    ]


def adjustable_sales_plan(
    total_units: int,
    total_revenue: float,
    total_profit: float,
    weeks: int,
    sales_pattern: str,
    custom_weights: list[float] | None = None,
) -> pd.DataFrame:
    if weeks <= 0:
        weeks = 1

    if sales_pattern == "Even Split":
        weights = [1 / weeks] * weeks

    elif sales_pattern == "Slow Start / Ramp Up":
        raw_weights = list(range(1, weeks + 1))
        total_weight = sum(raw_weights)
        weights = [w / total_weight for w in raw_weights]

    elif sales_pattern == "Fast Start":
        raw_weights = list(range(weeks, 0, -1))
        total_weight = sum(raw_weights)
        weights = [w / total_weight for w in raw_weights]

    elif sales_pattern == "Custom Weekly %" and custom_weights:
        total_weight = sum(custom_weights)
        weights = [1 / weeks] * weeks if total_weight == 0 else [
            w / total_weight for w in custom_weights
        ]

    else:
        weights = [1 / weeks] * weeks

    rows = []
    cumulative_units = 0
    cumulative_revenue = 0.0
    cumulative_profit = 0.0

    for i, weight in enumerate(weights, start=1):
        weekly_units = round(total_units * weight)
        weekly_revenue = total_revenue * weight
        weekly_profit = total_profit * weight

        cumulative_units += weekly_units
        cumulative_revenue += weekly_revenue
        cumulative_profit += weekly_profit

        rows.append(
            {
                "Week": f"Week {i}",
                "Sales %": weight * 100,
                "Units Target": weekly_units,
                "Revenue (R)": weekly_revenue,
                "Profit (R)": weekly_profit,
                "Cumulative Units": cumulative_units,
                "Cumulative Revenue (R)": cumulative_revenue,
                "Cumulative Profit (R)": cumulative_profit,
            }
        )

    plan_df = pd.DataFrame(rows)

    if not plan_df.empty:
        unit_difference = total_units - int(plan_df["Units Target"].sum())
        plan_df.loc[plan_df.index[-1], "Units Target"] += unit_difference
        plan_df["Cumulative Units"] = plan_df["Units Target"].cumsum()

    return plan_df


def build_competitor_pricing(
    variants,
    competitor_names: list[str],
    competitor_prices: dict[str, dict[str, float]],
) -> pd.DataFrame:
    rows = []

    clean_competitor_names = [
        name.strip()
        for name in competitor_names
        if name.strip()
    ]

    for v in variants:
        peony_price = float(v.sell_price)

        row = {
            "Variant": v.name,
            "Peony Price (R)": peony_price,
        }

        active_competitor_prices = []

        for competitor_name in clean_competitor_names:
            competitor_price = float(
                competitor_prices.get(competitor_name, {}).get(v.name, 0.0)
            )

            price_col = f"{competitor_name} Price (R)"
            gap_col = f"Peony vs {competitor_name} Gap (R)"
            gap_pct_col = f"Peony vs {competitor_name} Gap %"
            position_col = f"Position vs {competitor_name}"

            row[price_col] = competitor_price

            if competitor_price > 0:
                gap = peony_price - competitor_price
                gap_pct = gap / competitor_price * 100
                active_competitor_prices.append(competitor_price)

                if peony_price < competitor_price:
                    position = f"Cheaper than {competitor_name}"
                elif peony_price == competitor_price:
                    position = f"Same as {competitor_name}"
                else:
                    position = f"More expensive than {competitor_name}"
            else:
                gap = 0.0
                gap_pct = 0.0
                position = f"{competitor_name} not selling"

            row[gap_col] = gap
            row[gap_pct_col] = gap_pct
            row[position_col] = position

        if active_competitor_prices:
            competitor_avg_price = sum(active_competitor_prices) / len(active_competitor_prices)
            avg_gap = peony_price - competitor_avg_price
            avg_gap_pct = avg_gap / competitor_avg_price * 100

            if peony_price < competitor_avg_price:
                avg_position = "Below competitor average"
            elif peony_price == competitor_avg_price:
                avg_position = "Equal to competitor average"
            else:
                avg_position = "Above competitor average"
        else:
            competitor_avg_price = 0.0
            avg_gap = 0.0
            avg_gap_pct = 0.0
            avg_position = "No competitor price available"

        row["Competitor Avg Price (R)"] = competitor_avg_price
        row["Peony vs Competitor Avg Gap (R)"] = avg_gap
        row["Peony vs Competitor Avg Gap %"] = avg_gap_pct
        row["Position vs Competitor Avg"] = avg_position

        rows.append(row)

    return pd.DataFrame(rows)


def build_competitor_chart_df(
    variants,
    competitor_names: list[str],
    competitor_prices: dict[str, dict[str, float]],
) -> pd.DataFrame:
    rows = []

    for v in variants:
        rows.append(
            {
                "Variant": v.name,
                "Brand": "Peony",
                "Price (R)": float(v.sell_price),
            }
        )

        for competitor_name in competitor_names:
            clean_name = competitor_name.strip()

            if not clean_name:
                continue

            price = float(
                competitor_prices.get(clean_name, {}).get(v.name, 0.0)
            )

            if price > 0:
                rows.append(
                    {
                        "Variant": v.name,
                        "Brand": clean_name,
                        "Price (R)": price,
                    }
                )

    return pd.DataFrame(rows)


def set_mix_preset(variants, preset_name: str) -> None:
    default_mix = {
        "100g Mini Sachet": 30,
        "200g Sachet": 25,
        "500g Pack": 20,
        "1kg Pack": 15,
        "2kg Pack": 7,
        "5kg Bulk": 3,
    }

    conservative_mix = {
        "100g Mini Sachet": 5,
        "200g Sachet": 10,
        "500g Pack": 20,
        "1kg Pack": 25,
        "2kg Pack": 25,
        "5kg Bulk": 15,
    }

    if preset_name == "reset":
        selected_mix = default_mix

    elif preset_name == "conservative":
        selected_mix = conservative_mix

    elif preset_name == "random":
        random_values = [random.randint(0, 100) for _ in variants]

        if sum(random_values) == 0:
            random_values[0] = 100

        selected_mix = {
            v.name: random_values[i]
            for i, v in enumerate(variants)
        }

    else:
        selected_mix = default_mix

    for v in variants:
        st.session_state[f"mix_{v.name}"] = int(selected_mix.get(v.name, 0))


def get_available_units_map(order_df: pd.DataFrame) -> dict[str, int]:
    if "Variant" not in order_df.columns or "Units" not in order_df.columns:
        return {}

    return {
        row["Variant"]: int(row["Units"])
        for _, row in order_df.iterrows()
    }


def get_profit_per_unit_map(ue_df: pd.DataFrame) -> dict[str, float]:
    if "Variant" not in ue_df.columns or "Profit / Unit (R)" not in ue_df.columns:
        return {}

    return {
        row["Variant"]: float(row["Profit / Unit (R)"])
        for _, row in ue_df.iterrows()
    }


def set_outlet_units(
    outlet_names: list[str],
    variants,
    allocation_map: dict[str, dict[str, int]],
) -> None:
    for outlet_index, outlet_name in enumerate(outlet_names):
        for v in variants:
            key = f"outlet_{outlet_index}_units_{v.name}"
            st.session_state[key] = int(
                allocation_map.get(outlet_name, {}).get(v.name, 0)
            )


def suggest_profitable_outlet_allocation(
    outlet_names: list[str],
    variants,
    order_df: pd.DataFrame,
    ue_df: pd.DataFrame,
) -> None:
    """
    Allocates all available stock dynamically.

    Logic:
    - Sort variants by profit per unit, highest first.
    - Allocate available units across outlets in a round-robin pattern.
    - This makes sure the highest-profit variants are allocated first.
    """

    clean_outlets = [
        outlet.strip()
        for outlet in outlet_names
        if outlet.strip()
    ]

    if not clean_outlets:
        return

    available_units_map = get_available_units_map(order_df)
    profit_map = get_profit_per_unit_map(ue_df)

    sorted_variants = sorted(
        variants,
        key=lambda v: profit_map.get(v.name, 0.0),
        reverse=True,
    )

    allocation_map = {
        outlet: {
            v.name: 0
            for v in variants
        }
        for outlet in clean_outlets
    }

    for v in sorted_variants:
        available_units = int(available_units_map.get(v.name, 0))

        for unit_number in range(available_units):
            outlet = clean_outlets[unit_number % len(clean_outlets)]
            allocation_map[outlet][v.name] += 1

    set_outlet_units(clean_outlets, variants, allocation_map)


def fix_outlet_allocation(
    outlet_names: list[str],
    variants,
    order_df: pd.DataFrame,
    ue_df: pd.DataFrame,
) -> None:
    """
    Fixes Variant Allocation Check.

    Logic:
    1. If a variant is over-allocated, reduce allocations from the last outlet backwards.
    2. If a variant is under-allocated, allocate remaining units across outlets.
    3. Variants are processed by profit per unit, highest first.
    """

    clean_outlets = [
        outlet.strip()
        for outlet in outlet_names
        if outlet.strip()
    ]

    if not clean_outlets:
        return

    available_units_map = get_available_units_map(order_df)
    profit_map = get_profit_per_unit_map(ue_df)

    current_allocation = {
        outlet: {
            v.name: int(
                st.session_state.get(
                    f"outlet_{outlet_index}_units_{v.name}",
                    0,
                )
            )
            for v in variants
        }
        for outlet_index, outlet in enumerate(clean_outlets)
    }

    sorted_variants = sorted(
        variants,
        key=lambda v: profit_map.get(v.name, 0.0),
        reverse=True,
    )

    for v in sorted_variants:
        variant_name = v.name
        available_units = int(available_units_map.get(variant_name, 0))

        allocated_units = sum(
            current_allocation[outlet].get(variant_name, 0)
            for outlet in clean_outlets
        )

        # Reduce over-allocation from the last outlet backwards
        if allocated_units > available_units:
            excess = allocated_units - available_units

            for outlet in reversed(clean_outlets):
                current_units = current_allocation[outlet][variant_name]
                reduction = min(current_units, excess)

                current_allocation[outlet][variant_name] -= reduction
                excess -= reduction

                if excess <= 0:
                    break

        # Fill under-allocation across outlets
        allocated_units = sum(
            current_allocation[outlet].get(variant_name, 0)
            for outlet in clean_outlets
        )

        if allocated_units < available_units:
            remaining = available_units - allocated_units

            for unit_number in range(remaining):
                outlet = clean_outlets[unit_number % len(clean_outlets)]
                current_allocation[outlet][variant_name] += 1

    set_outlet_units(clean_outlets, variants, current_allocation)


def build_outlet_variant_allocation(
    outlet_names: list[str],
    outlet_variant_units: dict[str, dict[str, int]],
    variants,
    order_df: pd.DataFrame,
    ue_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clean_outlets = [
        outlet.strip()
        for outlet in outlet_names
        if outlet.strip()
    ]

    if not clean_outlets:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    available_units_map = get_available_units_map(order_df)

    cost_map = {}
    sell_price_map = {}
    profit_map = {}

    if "Variant" in ue_df.columns:
        if "Total Cost (R)" in ue_df.columns:
            cost_map = dict(zip(ue_df["Variant"], ue_df["Total Cost (R)"]))

        if "Sell Price (R)" in ue_df.columns:
            sell_price_map = dict(zip(ue_df["Variant"], ue_df["Sell Price (R)"]))

        if "Profit / Unit (R)" in ue_df.columns:
            profit_map = dict(zip(ue_df["Variant"], ue_df["Profit / Unit (R)"]))

    rows = []

    for outlet in clean_outlets:
        variant_units = outlet_variant_units.get(outlet, {})

        for v in variants:
            variant_name = v.name
            units_allocated = int(variant_units.get(variant_name, 0))
            variant_grams = get_variant_grams(v)

            sell_price = float(sell_price_map.get(variant_name, float(v.sell_price)))
            unit_cost = float(cost_map.get(variant_name, 0.0))
            profit_per_unit = float(profit_map.get(variant_name, sell_price - unit_cost))

            revenue = units_allocated * sell_price
            cost = units_allocated * unit_cost
            profit = units_allocated * profit_per_unit
            five_kg_equivalent = (units_allocated * variant_grams) / FIVE_KG_GRAMS

            rows.append(
                {
                    "Outlet": outlet,
                    "Variant": variant_name,
                    "Variant Size (g)": variant_grams,
                    "Units Allocated": units_allocated,
                    "5kg Packs Equivalent": five_kg_equivalent,
                    "Sell Price / Unit (R)": sell_price,
                    "Cost / Unit (R)": unit_cost,
                    "Profit / Unit (R)": profit_per_unit,
                    "Revenue (R)": revenue,
                    "Cost (R)": cost,
                    "Profit (R)": profit,
                }
            )

    outlet_detail_df = pd.DataFrame(rows)

    if outlet_detail_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    outlet_summary_df = (
        outlet_detail_df
        .groupby("Outlet", as_index=False)
        .agg(
            {
                "Units Allocated": "sum",
                "5kg Packs Equivalent": "sum",
                "Revenue (R)": "sum",
                "Cost (R)": "sum",
                "Profit (R)": "sum",
            }
        )
    )

    variant_allocated_df = (
        outlet_detail_df
        .groupby("Variant", as_index=False)
        .agg(
            {
                "Units Allocated": "sum",
                "5kg Packs Equivalent": "sum",
            }
        )
    )

    variant_check_rows = []

    for v in variants:
        variant_name = v.name
        available_units = int(available_units_map.get(variant_name, 0))

        allocated_units_series = variant_allocated_df.loc[
            variant_allocated_df["Variant"] == variant_name,
            "Units Allocated",
        ]

        allocated_units = (
            int(allocated_units_series.iloc[0])
            if not allocated_units_series.empty
            else 0
        )

        remaining_units = available_units - allocated_units

        variant_grams = get_variant_grams(v)
        allocated_5kg_equivalent = (allocated_units * variant_grams) / FIVE_KG_GRAMS
        available_5kg_equivalent = (available_units * variant_grams) / FIVE_KG_GRAMS
        remaining_5kg_equivalent = (remaining_units * variant_grams) / FIVE_KG_GRAMS

        if remaining_units < 0:
            status = "❌ Over-allocated"
        elif remaining_units == 0:
            status = "✅ Fully allocated"
        else:
            status = "⚠️ Remaining stock"

        variant_check_rows.append(
            {
                "Variant": variant_name,
                "Available Units": available_units,
                "Allocated Units": allocated_units,
                "Remaining Units": remaining_units,
                "Available 5kg Equivalent": available_5kg_equivalent,
                "Allocated 5kg Equivalent": allocated_5kg_equivalent,
                "Remaining 5kg Equivalent": remaining_5kg_equivalent,
                "Status": status,
            }
        )

    variant_check_df = pd.DataFrame(variant_check_rows)

    return outlet_detail_df, outlet_summary_df, variant_check_df


# ---------------------------------------------------------------------------
# Sidebar: session controls
# ---------------------------------------------------------------------------

sidebar_logo_path = get_logo_path()

if sidebar_logo_path is not None:
    st.sidebar.image(str(sidebar_logo_path), width=160)
else:
    st.sidebar.warning(f"Logo not found. Add an image to: {ASSETS_DIR}")

st.sidebar.title("⚙️ Model Inputs")

st.sidebar.subheader("Session")

scol1, scol2, scol3 = st.sidebar.columns(3)

if scol1.button("💾 Save"):
    save_current_session()
    st.sidebar.success("Saved")

if scol2.button("📂 Load"):
    loaded = load_saved_session()

    if loaded:
        for key, value in loaded.items():
            st.session_state[key] = value

        st.rerun()
    else:
        st.sidebar.warning("No saved session found")

if scol3.button("🧹 Clear"):
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()

    st.sidebar.success("Saved session cleared")


# ---------------------------------------------------------------------------
# Sidebar: marketing campaign setup
# ---------------------------------------------------------------------------

st.sidebar.subheader("Marketing Campaign")

campaign_options = get_campaign_options(campaigns)
today = date.today()


def safe_widget_key(value: str) -> str:
    """Create a safe Streamlit widget suffix from a campaign name."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip())
    return cleaned[:80] if cleaned else "new_campaign"


if campaign_options:
    selected_campaign_option = st.sidebar.selectbox(
        "Load saved campaign",
        ["➕ Create new campaign"] + campaign_options,
        key="selected_campaign_to_load",
        help="Select an existing campaign, or create a new one.",
    )
else:
    selected_campaign_option = "➕ Create new campaign"
    st.sidebar.caption("No saved campaigns yet.")


using_saved_campaign = (
    selected_campaign_option != "➕ Create new campaign"
    and selected_campaign_option in campaigns
)

if using_saved_campaign:
    campaign_name = selected_campaign_option.strip()
    selected_campaign_data = campaigns.get(campaign_name, {})

    st.sidebar.text_input(
        "Campaign name",
        value=campaign_name,
        key=f"campaign_name_readonly_{safe_widget_key(campaign_name)}",
        disabled=True,
        help="Loaded saved campaign. To create a new campaign, choose Create new campaign above.",
    )

    default_start = iso_to_date(
        selected_campaign_data.get("start_date"),
        today,
    )
    default_end = iso_to_date(
        selected_campaign_data.get("end_date"),
        today,
    )
    date_widget_suffix = safe_widget_key(campaign_name)

else:
    init_state(
        "new_campaign_name",
        "Peony Fresh Launch Campaign",
        saved_session,
    )

    campaign_name = st.sidebar.text_input(
        "Campaign name",
        key="new_campaign_name",
        help="Create a campaign name such as Peony Fresh Soweto Launch.",
    ).strip()

    default_start = today
    default_end = today

    if campaign_name in campaigns:
        default_start = iso_to_date(
            campaigns[campaign_name].get("start_date"),
            today,
        )
        default_end = iso_to_date(
            campaigns[campaign_name].get("end_date"),
            today,
        )

    date_widget_suffix = "new_campaign"


campaign_start_date = st.sidebar.date_input(
    "Campaign start date",
    value=default_start,
    key=f"campaign_start_date_{date_widget_suffix}",
)

campaign_end_date = st.sidebar.date_input(
    "Campaign end date",
    value=default_end,
    key=f"campaign_end_date_{date_widget_suffix}",
)

campaign_days = max(
    1,
    (campaign_end_date - campaign_start_date).days + 1,
)

st.sidebar.caption(
    f"Campaign duration: **{campaign_days} day(s)**"
)

if campaign_end_date < campaign_start_date:
    st.sidebar.error("Campaign end date cannot be before the start date.")

if st.sidebar.button("💾 Save Campaign"):
    if not campaign_name:
        st.sidebar.error("Enter a campaign name first.")
    elif campaign_end_date < campaign_start_date:
        st.sidebar.error("Fix the campaign dates first.")
    else:
        campaigns = upsert_campaign(
            campaigns=campaigns,
            campaign_name=campaign_name,
            start_date=campaign_start_date,
            end_date=campaign_end_date,
        )
        save_campaigns(campaigns)
        st.sidebar.success("Campaign saved")
        st.rerun()



# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------

st.sidebar.subheader("Supplier & Stock")

init_state("bag_cost", 95.0, saved_session)
bag_cost = st.sidebar.number_input(
    "Bag cost from supplier (R / 5kg bag)",
    min_value=1.0,
    step=1.0,
    key="bag_cost",
    help="Base price you pay Peony Trading per 5kg bag.",
)

init_state("free_mode", "Percentage", saved_session)
free_mode = st.sidebar.radio(
    "Free stock entry mode",
    ["Percentage", "X free per Y ordered"],
    horizontal=False,
    key="free_mode",
)

if free_mode == "Percentage":
    init_state("free_stock_pct", 10.0, saved_session)
    free_stock_pct = st.sidebar.number_input(
        "Free stock %",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key="free_stock_pct",
        help="Percentage of paid bags received free as promotion.",
    )
else:
    c1, c2 = st.sidebar.columns(2)

    init_state("free_x", 5, saved_session)
    init_state("per_y", 50, saved_session)

    free_x = c1.number_input(
        "Free bags",
        min_value=0,
        step=1,
        key="free_x",
    )

    per_y = c2.number_input(
        "Per ordered",
        min_value=1,
        step=1,
        key="per_y",
    )

    free_stock_pct = (free_x / per_y) * 100.0
    st.sidebar.caption(f"➡️ Effective free stock: **{free_stock_pct:.1f}%**")


st.sidebar.subheader("Order & Budget")

init_state("budget", 7000.0, saved_session)
budget = st.sidebar.number_input(
    "Budget (R)",
    min_value=0.0,
    step=100.0,
    key="budget",
    help="Total cash available for the first order.",
)

init_state("order_qty_bags", 60, saved_session)
order_qty_bags = st.sidebar.number_input(
    "Order quantity paid bags",
    min_value=1,
    step=1,
    key="order_qty_bags",
    help="For example: 60 paid bags plus 10% free stock gives 66 total 5kg buckets.",
)


st.sidebar.subheader("Variable Costs")

init_state("transport_cost", 500.0, saved_session)
transport_cost = st.sidebar.number_input(
    "Transport / collection cost (R per order)",
    min_value=0.0,
    step=10.0,
    key="transport_cost",
    help="Fuel, delivery, or collection cost for the entire order.",
)

init_state("other_variable_cost", 300.0, saved_session)
other_variable_cost = st.sidebar.number_input(
    "Other variable costs (R per order)",
    min_value=0.0,
    step=10.0,
    key="other_variable_cost",
    help="Any other variable costs per order, such as labour or storage.",
)

total_variable_cost = transport_cost + other_variable_cost


st.sidebar.subheader("Payment Terms")

TERM_DAYS = {
    "Cash on Delivery": 0,
    "7-Day": 7,
    "14-Day": 14,
    "30-Day": 30,
}

init_state("payment_term", "Cash on Delivery", saved_session)
payment_term = st.sidebar.selectbox(
    "Supplier payment term",
    options=list(TERM_DAYS.keys()),
    key="payment_term",
    help="When payment to the supplier is due.",
)

term_days = TERM_DAYS[payment_term]

init_state("customer_term", "Cash on Delivery", saved_session)
customer_term = st.sidebar.selectbox(
    "Customer payment term receivables",
    options=list(TERM_DAYS.keys()),
    key="customer_term",
    help="When your customers pay you.",
)

customer_term_days = TERM_DAYS[customer_term]


st.sidebar.subheader("Selling Prices & Packaging")

variants = logic.default_variants()

for v in variants:
    with st.sidebar.expander(v.name, expanded=False):
        init_state(f"sell_{v.name}", float(v.sell_price), saved_session)
        v.sell_price = st.number_input(
            f"Sell price (R) — {v.name}",
            min_value=0.0,
            step=0.5,
            key=f"sell_{v.name}",
        )

        if v.name != "5kg Bulk":
            init_state(f"pkg_{v.name}", float(v.packaging_cost), saved_session)
            v.packaging_cost = st.number_input(
                f"Packaging cost (R) — {v.name}",
                min_value=0.0,
                step=0.1,
                key=f"pkg_{v.name}",
            )


# ---------------------------------------------------------------------------
# Sidebar: dynamic competitor pricing
# ---------------------------------------------------------------------------

st.sidebar.subheader("Competitor Pricing")

st.sidebar.caption(
    "Add one or more competitors. Enter R0 if a competitor does not sell a specific variant."
)

init_state("number_of_competitors", 3, saved_session)
number_of_competitors = st.sidebar.number_input(
    "Number of competitors",
    min_value=1,
    max_value=10,
    step=1,
    key="number_of_competitors",
)

competitor_names = []
competitor_prices: dict[str, dict[str, float]] = {}

default_competitor_names = [
    "OMO",
    "Sunlight",
    "MAQ",
    "Surf",
    "Skip",
    "Ariel",
    "No Name",
    "House Brand",
    "Local Brand 1",
    "Local Brand 2",
]

for competitor_index in range(number_of_competitors):
    default_competitor_name = (
        default_competitor_names[competitor_index]
        if competitor_index < len(default_competitor_names)
        else f"Competitor {competitor_index + 1}"
    )

    with st.sidebar.expander(
        f"Competitor {competitor_index + 1}",
        expanded=False,
    ):
        init_state(
            f"competitor_name_{competitor_index}",
            default_competitor_name,
            saved_session,
        )

        competitor_name = st.text_input(
            f"Competitor name {competitor_index + 1}",
            key=f"competitor_name_{competitor_index}",
        ).strip()

        if not competitor_name:
            competitor_name = f"Competitor {competitor_index + 1}"

        competitor_names.append(competitor_name)
        competitor_prices[competitor_name] = {}

        for v in variants:
            price_key = f"competitor_{competitor_index}_price_{v.name}"
            init_state(price_key, 0.0, saved_session)

            competitor_prices[competitor_name][v.name] = st.number_input(
                f"{competitor_name} price (R) — {v.name}",
                min_value=0.0,
                step=0.5,
                key=price_key,
                help="Enter 0 if this competitor does not sell this exact pack size.",
            )


# ---------------------------------------------------------------------------
# Sidebar: First Order Mix with preset buttons
# ---------------------------------------------------------------------------

st.sidebar.subheader("First Order Mix (%)")

st.sidebar.caption(
    "Use the buttons to auto-fill the mix sliders. The model will normalise the values."
)

mix_button_1, mix_button_2, mix_button_3 = st.sidebar.columns(3)

if mix_button_1.button("🎲 Random"):
    set_mix_preset(variants, "random")

if mix_button_2.button("🛡️ Conservative"):
    set_mix_preset(variants, "conservative")

if mix_button_3.button("🔄 Reset"):
    set_mix_preset(variants, "reset")

default_mix = {
    "100g Mini Sachet": 20,
    "200g Sachet": 40,
    "500g Pack": 15,
    "1kg Pack": 10,
    "2kg Pack": 10,
    "5kg Bulk": 5,
}

mix_weights = {}

for v in variants:
    mix_key = f"mix_{v.name}"
    init_state(mix_key, int(default_mix.get(v.name, 0)), saved_session)

    mix_weights[v.name] = st.sidebar.slider(
        v.name,
        0,
        100,
        key=mix_key,
    )


# ---------------------------------------------------------------------------
# Early computations needed for outlet suggestions
# ---------------------------------------------------------------------------

ue_df = logic.unit_economics(
    variants,
    bag_cost,
    free_stock_pct,
)

order = logic.first_order_mix(
    variants,
    bag_cost,
    free_stock_pct,
    budget,
    order_qty_bags,
    mix_weights,
    variable_cost=total_variable_cost,
)

order_df = add_5kg_equivalent_column(
    order_df=order["table"],
    variants=variants,
)

summ = order["summary"]
total_units = int(order_df["Units"].sum())
net_profit_after_variable_costs = summ["total_profit"] - total_variable_cost


# ---------------------------------------------------------------------------
# Sidebar: Sales plan settings
# ---------------------------------------------------------------------------

st.sidebar.subheader("Sales Plan Settings")

init_state("plan_weeks", 5, saved_session)
plan_weeks = st.sidebar.slider(
    "Sales plan duration weeks",
    min_value=1,
    max_value=12,
    step=1,
    key="plan_weeks",
    help="Choose how many weeks you want the sales plan to cover.",
)

init_state("sales_pattern", "Slow Start / Ramp Up", saved_session)
sales_pattern = st.sidebar.selectbox(
    "Sales pattern",
    options=[
        "Even Split",
        "Slow Start / Ramp Up",
        "Fast Start",
        "Custom Weekly %",
    ],
    key="sales_pattern",
    help="Choose how the stock should be sold over the selected period.",
)

custom_weekly_weights = []

if sales_pattern == "Custom Weekly %":
    st.sidebar.caption(
        "Set the sales weight for each week. These do not need to total 100%; "
        "the app will normalise them."
    )

    for week in range(1, plan_weeks + 1):
        custom_week_key = f"custom_week_{week}"
        init_state(custom_week_key, round(100 / plan_weeks, 1), saved_session)

        custom_weekly_weights.append(
            st.sidebar.number_input(
                f"Week {week} sales weight",
                min_value=0.0,
                step=1.0,
                key=custom_week_key,
            )
        )


# ---------------------------------------------------------------------------
# Sidebar: Outlet allocation settings
# ---------------------------------------------------------------------------

st.sidebar.subheader("Outlet Allocation")

st.sidebar.caption(
    "Allocate exact units per outlet and per variant. "
    "Use 0 where an outlet will not receive that variant."
)

init_state("number_of_outlets", 3, saved_session)
number_of_outlets = st.sidebar.number_input(
    "Number of outlets / channels",
    min_value=1,
    max_value=10,
    step=1,
    key="number_of_outlets",
    help="Add outlets or sales channels that will receive stock allocation.",
)

outlet_names = []
default_outlets = [
    "IML Convenience Store",
    "Opi Hoeki Store",
    "Direct Household Sales",
]

for outlet_index in range(number_of_outlets):
    default_name = (
        default_outlets[outlet_index]
        if outlet_index < len(default_outlets)
        else f"Outlet {outlet_index + 1}"
    )

    outlet_name_key = f"outlet_name_{outlet_index}"
    init_state(outlet_name_key, default_name, saved_session)

    outlet_name_value = str(st.session_state.get(outlet_name_key, default_name)).strip()

    if not outlet_name_value:
        outlet_name_value = f"Outlet {outlet_index + 1}"

    outlet_names.append(outlet_name_value)


outlet_action_1, outlet_action_2 = st.sidebar.columns(2)

if outlet_action_1.button("💡 Suggest Allocation"):
    suggest_profitable_outlet_allocation(
        outlet_names=outlet_names,
        variants=variants,
        order_df=order_df,
        ue_df=ue_df,
    )
    st.rerun()

if outlet_action_2.button("🛠️ Fix Allocation"):
    fix_outlet_allocation(
        outlet_names=outlet_names,
        variants=variants,
        order_df=order_df,
        ue_df=ue_df,
    )
    st.rerun()


outlet_names = []
outlet_variant_units: dict[str, dict[str, int]] = {}

for outlet_index in range(number_of_outlets):
    default_name = (
        default_outlets[outlet_index]
        if outlet_index < len(default_outlets)
        else f"Outlet {outlet_index + 1}"
    )

    with st.sidebar.expander(
        f"Outlet / Channel {outlet_index + 1}",
        expanded=False,
    ):
        outlet_name_key = f"outlet_name_{outlet_index}"
        init_state(outlet_name_key, default_name, saved_session)

        outlet_name = st.text_input(
            f"Outlet name {outlet_index + 1}",
            key=outlet_name_key,
        ).strip()

        if not outlet_name:
            outlet_name = f"Outlet {outlet_index + 1}"

        outlet_names.append(outlet_name)
        outlet_variant_units[outlet_name] = {}

        st.caption("Enter units allocated to this outlet per variant.")

        for v in variants:
            unit_key = f"outlet_{outlet_index}_units_{v.name}"
            init_state(unit_key, 0, saved_session)

            outlet_variant_units[outlet_name][v.name] = st.number_input(
                f"{outlet_name} units — {v.name}",
                min_value=0,
                step=1,
                key=unit_key,
                help="Number of units of this variant allocated to this outlet.",
            )


# ---------------------------------------------------------------------------
# Main computations
# ---------------------------------------------------------------------------

mix_explanation_df = build_mix_explanation(
    order_df=order_df,
    variants=variants,
)

plan_df = adjustable_sales_plan(
    total_units=total_units,
    total_revenue=summ["total_revenue"],
    total_profit=net_profit_after_variable_costs,
    weeks=plan_weeks,
    sales_pattern=sales_pattern,
    custom_weights=custom_weekly_weights,
)

outlet_detail_df, outlet_summary_df, outlet_variant_check_df = build_outlet_variant_allocation(
    outlet_names=outlet_names,
    outlet_variant_units=outlet_variant_units,
    variants=variants,
    order_df=order_df,
    ue_df=ue_df,
)

competitor_df = build_competitor_pricing(
    variants=variants,
    competitor_names=competitor_names,
    competitor_prices=competitor_prices,
)

competitor_chart_df = build_competitor_chart_df(
    variants=variants,
    competitor_names=competitor_names,
    competitor_prices=competitor_prices,
)

current_campaign = campaigns.get(campaign_name, {})
campaign_sales_df = build_campaign_sales_df(current_campaign)
campaign_variant_progress_df, campaign_outlet_progress_df = build_campaign_progress(
    campaign=current_campaign,
    order_df=order_df,
    outlet_detail_df=outlet_detail_df,
)

eff_cpg = logic.cost_per_gram(
    bag_cost,
    free_stock_pct,
)

days_cash_tied = max(0, customer_term_days - term_days)
cash_at_risk = summ["investment"] + total_variable_cost


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def build_excel() -> bytes:
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        ue_df.to_excel(writer, sheet_name="Unit Economics", index=False)
        order_df.to_excel(writer, sheet_name="First Order Mix", index=False)
        mix_explanation_df.to_excel(writer, sheet_name="Mix Explanation", index=False)
        pd.DataFrame([summ]).to_excel(writer, sheet_name="Order Summary", index=False)
        plan_df.to_excel(writer, sheet_name=f"{plan_weeks}-Week Plan", index=False)

        outlet_summary_df.to_excel(writer, sheet_name="Outlet Summary", index=False)
        outlet_detail_df.to_excel(writer, sheet_name="Outlet Detail", index=False)
        outlet_variant_check_df.to_excel(writer, sheet_name="Outlet Variant Check", index=False)

        competitor_df.to_excel(writer, sheet_name="Competitor Pricing", index=False)
        campaign_sales_df.to_excel(writer, sheet_name="Campaign Sales", index=False)
        campaign_variant_progress_df.to_excel(writer, sheet_name="Campaign Progress", index=False)
        campaign_outlet_progress_df.to_excel(writer, sheet_name="Campaign Outlet Progress", index=False)

        pd.DataFrame(
            [
                {
                    "Supplier Term": payment_term,
                    "Customer Term": customer_term,
                    "Cash Gap (days)": days_cash_tied,
                    "Transport Cost (R)": transport_cost,
                    "Other Variable Cost (R)": other_variable_cost,
                    "Total Variable Cost (R)": total_variable_cost,
                    "Net Profit after Var. Costs (R)": round(
                        net_profit_after_variable_costs,
                        2,
                    ),
                    "Total Investment incl. Var. Costs (R)": round(
                        summ["investment"] + total_variable_cost,
                        2,
                    ),
                }
            ]
        ).to_excel(writer, sheet_name="Cash Flow & Terms", index=False)

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Header & KPIs
# ---------------------------------------------------------------------------

main_logo_path = get_logo_path()

if main_logo_path is not None:
    st.image(str(main_logo_path), width=220)
else:
    st.warning(f"Logo not found. Add an image to: {ASSETS_DIR}")

st.title("💰 Peony Washing Powder Pricing & Margin Model")

st.caption(
    "Buy 5kg bags • receive promotional free stock • repackage into retail "
    "variants • compare competitor prices • allocate exact stock units to outlets • "
    "save and reload sessions • track campaigns, sales movement, cash turnover and sales plans."
)

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric(
    "Effective Bag Cost",
    money(summ["effective_bag_cost"]),
    delta=money(summ["effective_bag_cost"] - bag_cost),
)

k2.metric("Cost / gram", money(eff_cpg))

k3.metric(
    "Total Investment",
    money(summ["investment"] + total_variable_cost),
    help="Stock cost + transport + other variable costs.",
)

k4.metric("Projected Profit", money(net_profit_after_variable_costs))

k5.metric(
    "ROI after var. costs",
    (
        f"{(net_profit_after_variable_costs / (summ['investment'] + total_variable_cost) * 100):.1f}%"
        if (summ["investment"] + total_variable_cost)
        else "0.0%"
    ),
)

k6.metric(
    "Cash Gap days",
    f"{days_cash_tied}d",
    help="Days between paying supplier and receiving customer payment.",
)

st.divider()


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "📊 Unit Economics",
        "📦 First Order Mix",
        f"📅 {plan_weeks}-Week Sales Plan",
        "🏪 Outlet Allocation",
        "🏷️ Competitor Pricing",
        "💳 Cash Flow & Terms",
        "🎯 Campaign Sales",
    ]
)


# ---------------------------------------------------------------------------
# Tab 1: Unit Economics
# ---------------------------------------------------------------------------

with tab1:
    st.subheader("Cost Breakdown & Margins per Variant")

    st.dataframe(
        ue_df.style.format(
            {
                "Product Cost (R)": "{:.2f}",
                "Packaging Cost (R)": "{:.2f}",
                "Total Cost (R)": "{:.2f}",
                "Sell Price (R)": "{:.2f}",
                "Profit / Unit (R)": "{:.2f}",
                "Margin %": "{:.1f}",
                "Markup %": "{:.1f}",
            }
        ).background_gradient(
            subset=["Margin %"],
            cmap="Greens",
        ),
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        fig = px.bar(
            ue_df,
            x="Variant",
            y="Profit / Unit (R)",
            color="Margin %",
            color_continuous_scale="Tealgrn",
            title="Profit per Unit by Variant",
            text="Profit / Unit (R)",
        )
        fig.update_traces(texttemplate="R%{text:.2f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig2 = go.Figure()
        fig2.add_bar(
            name="Total Cost",
            x=ue_df["Variant"],
            y=ue_df["Total Cost (R)"],
        )
        fig2.add_bar(
            name="Profit",
            x=ue_df["Variant"],
            y=ue_df["Profit / Unit (R)"],
        )
        fig2.update_layout(barmode="stack", title="Cost vs Profit Sell Price")
        st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.line(
        ue_df,
        x="Variant",
        y="Margin %",
        markers=True,
        title="Margin % Comparison",
        range_y=[0, 100],
    )
    st.plotly_chart(fig3, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 2: First Order Mix
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("Recommended First Order Mix")

    s1, s2, s3, s4, s5 = st.columns(5)

    s1.metric("Paid Bags", f"{summ['paid_bags']}")
    s2.metric("Free Bags", f"{summ['free_bags']}")
    s3.metric("Total 5kg Buckets", f"{summ['paid_bags'] + summ['free_bags']}")
    s4.metric("Total Revenue", money(summ["total_revenue"]))
    s5.metric("Total Profit before var. costs", money(summ["total_profit"]))

    if summ["paid_bags"] < order_qty_bags:
        st.warning(
            f"Budget of {money(budget)} only covers {summ['paid_bags']} bags "
            f"but you requested {order_qty_bags}."
        )

    st.dataframe(
        order_df.style.format(
            {
                "Mix %": "{:.1f}",
                "5kg Packs Equivalent": "{:.1f}",
                "Revenue (R)": "{:.2f}",
                "Cost (R)": "{:.2f}",
                "Profit (R)": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    total_5kg_equivalent = order_df["5kg Packs Equivalent"].sum()

    st.info(
        f"Grams available: **{summ['grams_available']:,} g** • "
        f"Grams used: **{summ['grams_used']:,} g** • "
        f"Utilisation: **{(summ['grams_used'] / summ['grams_available'] * 100) if summ['grams_available'] else 0:.1f}%** • "
        f"Total units: **{total_units:,}** • "
        f"Total 5kg pack equivalent used: **{total_5kg_equivalent:.1f}**"
    )

    with st.expander("How the total units are calculated", expanded=True):
        st.write(
            "Each line converts allocated grams into units. "
            "For example, 25,500g allocated to 500g packs gives 51 units."
        )

        st.dataframe(
            mix_explanation_df.style.format(
                {
                    "Variant Size (g)": "{:.0f}",
                    "5kg Packs Equivalent": "{:.1f}",
                    "Derived Grams Used": "{:.0f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    c1, c2 = st.columns(2)

    with c1:
        fig = px.pie(
            order_df[order_df["Units"] > 0],
            names="Variant",
            values="Units",
            title="Unit Distribution",
            hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = px.bar(
            order_df,
            x="Variant",
            y=["Cost (R)", "Profit (R)"],
            title="Revenue Composition Cost + Profit",
            barmode="stack",
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 3: Adjustable Sales Plan
# ---------------------------------------------------------------------------

with tab3:
    st.subheader(f"{plan_weeks}-Week Sales Target Plan")
    st.caption(f"Sales pattern: **{sales_pattern}**")

    st.dataframe(
        plan_df.style.format(
            {
                "Sales %": "{:.1f}%",
                "Revenue (R)": "{:.2f}",
                "Profit (R)": "{:.2f}",
                "Cumulative Revenue (R)": "{:.2f}",
                "Cumulative Profit (R)": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        fig = px.bar(
            plan_df,
            x="Week",
            y="Revenue (R)",
            title="Weekly Revenue Target",
            text="Revenue (R)",
            color="Revenue (R)",
            color_continuous_scale="Blues",
        )
        fig.update_traces(texttemplate="R%{text:.2f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = go.Figure()
        fig.add_scatter(
            x=plan_df["Week"],
            y=plan_df["Cumulative Profit (R)"],
            mode="lines+markers",
            name="Cumulative Profit",
            fill="tozeroy",
        )
        fig.add_scatter(
            x=plan_df["Week"],
            y=plan_df["Cumulative Revenue (R)"],
            mode="lines+markers",
            name="Cumulative Revenue",
        )
        fig.update_layout(title="Cumulative Profit & Revenue Progression")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Break-even Analysis")

    investment_required = summ["investment"] + total_variable_cost
    break_even_week = None

    for _, row in plan_df.iterrows():
        if row["Cumulative Profit (R)"] >= investment_required:
            break_even_week = row["Week"]
            break

    be1, be2, be3 = st.columns(3)
    be1.metric("Investment Required", money(investment_required))
    be2.metric("Net Profit Target", money(investment_required))

    if break_even_week:
        be3.metric("Break-even Week", break_even_week)
        st.success(f"You are projected to recover your investment by **{break_even_week}**.")
    else:
        be3.metric("Break-even Week", "Not reached")
        st.warning(
            "The selected plan does not recover the full investment within the selected period."
        )

    st.divider()
    st.subheader("Stock Movement View")

    stock_df = plan_df[["Week", "Units Target", "Cumulative Units"]].copy()
    stock_df["Opening Units"] = total_units - stock_df["Cumulative Units"].shift(fill_value=0)
    stock_df["Closing Units"] = total_units - stock_df["Cumulative Units"]

    if total_units:
        stock_df["Remaining Stock %"] = stock_df["Closing Units"] / total_units * 100
    else:
        stock_df["Remaining Stock %"] = 0

    stock_df = stock_df[
        [
            "Week",
            "Opening Units",
            "Units Target",
            "Closing Units",
            "Remaining Stock %",
        ]
    ]

    st.dataframe(
        stock_df.style.format({"Remaining Stock %": "{:.1f}%"}),
        use_container_width=True,
        hide_index=True,
    )

    final_stock_pct = (
        float(stock_df["Remaining Stock %"].iloc[-1])
        if not stock_df.empty
        else 0
    )

    if final_stock_pct <= 20:
        st.warning(
            "Stock is projected to fall below 20%. Prepare the next order or supplier collection."
        )
    else:
        st.info(f"Projected closing stock after {plan_weeks} weeks: **{final_stock_pct:.1f}%**.")


# ---------------------------------------------------------------------------
# Tab 4: Outlet Allocation
# ---------------------------------------------------------------------------

with tab4:
    st.subheader("🏪 Outlet / Channel Allocation")

    st.caption(
        "Allocate exact units by outlet and variant. "
        "Use **Suggest Allocation** in the sidebar to allocate stock dynamically by profit priority, "
        "or **Fix Allocation** to correct over-allocation and fill remaining stock."
    )

    if outlet_detail_df.empty:
        st.warning("No outlet allocation entered yet. Add outlet units in the sidebar.")
    else:
        total_allocated_units = int(outlet_detail_df["Units Allocated"].sum())
        total_allocated_5kg_equiv = outlet_detail_df["5kg Packs Equivalent"].sum()
        total_allocated_profit = outlet_detail_df["Profit (R)"].sum()

        total_available_units = int(order_df["Units"].sum())
        total_available_5kg_equiv = order_df["5kg Packs Equivalent"].sum()

        remaining_units = total_available_units - total_allocated_units
        remaining_5kg_equiv = total_available_5kg_equiv - total_allocated_5kg_equiv

        o1, o2, o3, o4, o5 = st.columns(5)

        o1.metric("Available Units", f"{total_available_units:,}")
        o2.metric("Allocated Units", f"{total_allocated_units:,}")
        o3.metric("Remaining Units", f"{remaining_units:,}")
        o4.metric("Allocated 5kg Equiv.", f"{total_allocated_5kg_equiv:.1f}")
        o5.metric("Projected Profit", money(total_allocated_profit))

        if remaining_units < 0:
            st.error(
                "You have allocated more units than are available. "
                "Click **Fix Allocation** in the sidebar."
            )
        elif remaining_units == 0:
            st.success("All available units have been fully allocated.")
        else:
            st.warning(
                f"You still have **{remaining_units:,} units** remaining, "
                f"equal to **{remaining_5kg_equiv:.1f} × 5kg packs**. "
                "Click **Fix Allocation** in the sidebar to allocate the remainder."
            )

        st.divider()
        st.subheader("Outlet Summary")

        st.dataframe(
            outlet_summary_df.style.format(
                {
                    "5kg Packs Equivalent": "{:.1f}",
                    "Revenue (R)": "{:.2f}",
                    "Cost (R)": "{:.2f}",
                    "Profit (R)": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            fig_outlet_units = px.bar(
                outlet_summary_df,
                x="Outlet",
                y="Units Allocated",
                title="Units Allocated by Outlet",
                text="Units Allocated",
            )
            fig_outlet_units.update_traces(textposition="outside")
            st.plotly_chart(fig_outlet_units, use_container_width=True)

        with c2:
            fig_outlet_profit = px.bar(
                outlet_summary_df,
                x="Outlet",
                y="Profit (R)",
                title="Projected Profit by Outlet",
                text="Profit (R)",
            )
            fig_outlet_profit.update_traces(
                texttemplate="R%{text:.2f}",
                textposition="outside",
            )
            st.plotly_chart(fig_outlet_profit, use_container_width=True)

        st.divider()
        st.subheader("Detailed Outlet × Variant Allocation")

        st.dataframe(
            outlet_detail_df.style.format(
                {
                    "Variant Size (g)": "{:.0f}",
                    "5kg Packs Equivalent": "{:.1f}",
                    "Sell Price / Unit (R)": "{:.2f}",
                    "Cost / Unit (R)": "{:.2f}",
                    "Profit / Unit (R)": "{:.2f}",
                    "Revenue (R)": "{:.2f}",
                    "Cost (R)": "{:.2f}",
                    "Profit (R)": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Variant Allocation Check")

        st.caption(
            "This table compares the units generated in the First Order Mix "
            "against the units allocated to outlets."
        )

        st.dataframe(
            outlet_variant_check_df.style.format(
                {
                    "Available 5kg Equivalent": "{:.1f}",
                    "Allocated 5kg Equivalent": "{:.1f}",
                    "Remaining 5kg Equivalent": "{:.1f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        over_allocated = outlet_variant_check_df[
            outlet_variant_check_df["Remaining Units"] < 0
        ]

        if not over_allocated.empty:
            st.error(
                "Some variants are over-allocated. Click **Fix Allocation** in the sidebar."
            )

        remaining_stock = outlet_variant_check_df[
            outlet_variant_check_df["Remaining Units"] > 0
        ]

        if not remaining_stock.empty:
            st.info(
                "Some variants still have remaining stock. Click **Fix Allocation** "
                "to allocate the remainder automatically."
            )


# ---------------------------------------------------------------------------
# Tab 5: Competitor Pricing
# ---------------------------------------------------------------------------

with tab5:
    st.subheader("🏷️ Competitor Pricing Comparison")

    st.caption(
        "Compare Peony selling prices against one or more competitors. "
        "Competitor prices entered as R0 are treated as not selling that variant."
    )

    format_dict = {
        "Peony Price (R)": "{:.2f}",
        "Competitor Avg Price (R)": "{:.2f}",
        "Peony vs Competitor Avg Gap (R)": "{:.2f}",
        "Peony vs Competitor Avg Gap %": "{:.1f}%",
    }

    for competitor_name in competitor_names:
        clean_name = competitor_name.strip()

        if not clean_name:
            continue

        format_dict[f"{clean_name} Price (R)"] = "{:.2f}"
        format_dict[f"Peony vs {clean_name} Gap (R)"] = "{:.2f}"
        format_dict[f"Peony vs {clean_name} Gap %"] = "{:.1f}%"

    st.dataframe(
        competitor_df.style.format(format_dict),
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        if competitor_chart_df.empty:
            st.warning("No competitor chart data available yet.")
        else:
            fig_comp_prices = px.bar(
                competitor_chart_df,
                x="Variant",
                y="Price (R)",
                color="Brand",
                barmode="group",
                title="Peony vs Competitor Prices by Variant",
                text="Price (R)",
            )
            fig_comp_prices.update_traces(
                texttemplate="R%{text:.2f}",
                textposition="outside",
            )
            st.plotly_chart(fig_comp_prices, use_container_width=True)

    with c2:
        fig_avg_gap = px.bar(
            competitor_df,
            x="Variant",
            y="Peony vs Competitor Avg Gap (R)",
            title="Peony Price Gap vs Competitor Average",
            text="Peony vs Competitor Avg Gap (R)",
        )
        fig_avg_gap.update_traces(
            texttemplate="R%{text:.2f}",
            textposition="outside",
        )
        st.plotly_chart(fig_avg_gap, use_container_width=True)

    st.divider()
    st.subheader("Pricing Position Summary")

    below_avg_count = competitor_df[
        competitor_df["Position vs Competitor Avg"] == "Below competitor average"
    ].shape[0]

    above_avg_count = competitor_df[
        competitor_df["Position vs Competitor Avg"] == "Above competitor average"
    ].shape[0]

    equal_avg_count = competitor_df[
        competitor_df["Position vs Competitor Avg"] == "Equal to competitor average"
    ].shape[0]

    no_price_count = competitor_df[
        competitor_df["Position vs Competitor Avg"] == "No competitor price available"
    ].shape[0]

    p1, p2, p3, p4 = st.columns(4)

    p1.metric("Below Competitor Avg", below_avg_count)
    p2.metric("Above Competitor Avg", above_avg_count)
    p3.metric("Equal to Avg", equal_avg_count)
    p4.metric("No Competitor Price", no_price_count)

    st.info(
        "Use this tab to test whether Peony is positioned as a budget, "
        "value-for-money, or premium-priced product versus the competitors you enter."
    )


# ---------------------------------------------------------------------------
# Tab 6: Cash Flow & Terms
# ---------------------------------------------------------------------------

with tab6:
    st.subheader("💳 Cash Flow & Payment Terms Analysis")

    cf1, cf2, cf3, cf4 = st.columns(4)

    cf1.metric(
        "Supplier Term",
        payment_term,
        help="Days before you must pay supplier.",
    )

    cf2.metric(
        "Customer Term",
        customer_term,
        help="Days before customers pay you.",
    )

    cf3.metric(
        "Cash Gap",
        f"{days_cash_tied} days",
        delta=f"{'-' if days_cash_tied == 0 else '+'}{days_cash_tied}d",
        delta_color="inverse",
    )

    cf4.metric(
        "Cash at Risk",
        money(cash_at_risk),
        help="Total outlay before any revenue is collected.",
    )

    st.divider()
    st.subheader("Variable Cost Breakdown")

    vc1, vc2, vc3 = st.columns(3)

    vc1.metric("Transport / Collection", money(transport_cost))
    vc2.metric("Other Variable Costs", money(other_variable_cost))
    vc3.metric("Total Variable Costs", money(total_variable_cost))

    total_investment_with_vc = summ["investment"] + total_variable_cost

    roi_after_vc = (
        net_profit_after_variable_costs / total_investment_with_vc * 100
    ) if total_investment_with_vc else 0

    cost_breakdown_df = pd.DataFrame(
        {
            "Cost Component": [
                "Stock Cost",
                "Transport / Collection",
                "Other Variable Costs",
                "Packaging all variants",
            ],
            "Amount (R)": [
                summ["investment"],
                transport_cost,
                other_variable_cost,
                order_df["Cost (R)"].sum() - summ["investment"],
            ],
        }
    )

    cost_breakdown_df = cost_breakdown_df[
        cost_breakdown_df["Amount (R)"] > 0
    ]

    c1, c2 = st.columns(2)

    with c1:
        fig_vc = px.pie(
            cost_breakdown_df,
            names="Cost Component",
            values="Amount (R)",
            title="Total Cost Composition",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig_vc, use_container_width=True)

    with c2:
        profit_waterfall = go.Figure(
            go.Waterfall(
                name="Profit Waterfall",
                orientation="v",
                measure=[
                    "absolute",
                    "relative",
                    "relative",
                    "total",
                ],
                x=[
                    "Revenue",
                    "Stock Cost",
                    "Variable Costs",
                    "Net Profit",
                ],
                y=[
                    summ["total_revenue"],
                    -summ["investment"],
                    -total_variable_cost,
                    0,
                ],
                connector={
                    "line": {
                        "color": "rgb(63, 63, 63)"
                    }
                },
                decreasing={
                    "marker": {
                        "color": "#EF553B"
                    }
                },
                increasing={
                    "marker": {
                        "color": "#00CC96"
                    }
                },
                totals={
                    "marker": {
                        "color": "#636EFA"
                    }
                },
            )
        )

        profit_waterfall.update_layout(title="Revenue to Net Profit Waterfall")
        st.plotly_chart(profit_waterfall, use_container_width=True)

    st.divider()
    st.subheader("Payment Terms Scenario Comparison")

    scenarios = []

    for sup_term, sup_days in TERM_DAYS.items():
        for cust_term, cust_days in TERM_DAYS.items():
            gap = max(0, cust_days - sup_days)

            scenarios.append(
                {
                    "Supplier Term": sup_term,
                    "Customer Term": cust_term,
                    "Cash Gap (days)": gap,
                    "Cash at Risk (R)": cash_at_risk if gap > 0 else 0,
                    "Net Profit (R)": round(net_profit_after_variable_costs, 2),
                    "ROI %": round(roi_after_vc, 1),
                    "Favourable?": "✅ Yes"
                    if gap == 0
                    else ("⚠️ Neutral" if gap <= 7 else "❌ No"),
                }
            )

    scenarios_df = pd.DataFrame(scenarios)

    st.dataframe(
        scenarios_df.style.map(
            lambda v: "color: green"
            if v == "✅ Yes"
            else ("color: orange" if v == "⚠️ Neutral" else "color: red"),
            subset=["Favourable?"],
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        f"**Current scenario:** Supplier = **{payment_term}** | "
        f"Customer = **{customer_term}** | "
        f"Cash gap = **{days_cash_tied} days** | "
        f"Net profit after variable costs = **{money(net_profit_after_variable_costs)}** | "
        f"ROI = **{roi_after_vc:.1f}%**"
    )


# ---------------------------------------------------------------------------
# Tab 7: Campaign Sales
# ---------------------------------------------------------------------------

with tab7:
    st.subheader("🎯 Marketing Campaign Sales Tracker")

    if not campaign_name:
        st.warning("Enter and save a campaign name in the sidebar first.")
    elif campaign_end_date < campaign_start_date:
        st.error("Campaign end date cannot be before the start date.")
    elif campaign_name not in campaigns:
        st.info(
            "This campaign has not been saved yet. "
            "Click **Save Campaign** in the sidebar before recording sales."
        )
    else:
        current_campaign = campaigns[campaign_name]
        campaign_start = iso_to_date(current_campaign.get("start_date"), campaign_start_date)
        campaign_end = iso_to_date(current_campaign.get("end_date"), campaign_end_date)

        st.caption(
            f"Campaign period: **{campaign_start.isoformat()}** to "
            f"**{campaign_end.isoformat()}**"
        )

        campaign_days = max(1, (campaign_end - campaign_start).days + 1)
        days_elapsed = min(
            campaign_days,
            max(0, (date.today() - campaign_start).days + 1),
        )

        # Always rebuild from the current campaign so add/delete actions reflect correctly.
        campaign_sales_df = build_campaign_sales_df(current_campaign)
        campaign_variant_progress_df, campaign_outlet_progress_df = build_campaign_progress(
            campaign=current_campaign,
            order_df=order_df,
            outlet_detail_df=outlet_detail_df,
        )

        actual_units_sold = (
            int(campaign_sales_df["units_sold"].sum())
            if not campaign_sales_df.empty and "units_sold" in campaign_sales_df.columns
            else 0
        )

        actual_revenue = (
            float(campaign_sales_df["revenue"].sum())
            if not campaign_sales_df.empty and "revenue" in campaign_sales_df.columns
            else 0.0
        )

        projected_campaign_revenue = float(summ["total_revenue"])
        projected_units = int(total_units)

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Campaign Days", campaign_days)
        c2.metric("Days Elapsed", days_elapsed)
        c3.metric("Actual Units Sold", f"{actual_units_sold:,}")
        c4.metric("Actual Revenue", money(actual_revenue))
        c5.metric(
            "Sell-through",
            f"{(actual_units_sold / projected_units * 100) if projected_units else 0:.1f}%",
        )

        st.divider()
        st.subheader("Record a Sale")

        sale_col1, sale_col2, sale_col3, sale_col4 = st.columns(4)

        with sale_col1:
            sale_date = st.date_input(
                "Sale date",
                value=min(max(date.today(), campaign_start), campaign_end),
                min_value=campaign_start,
                max_value=campaign_end,
                key="sale_date",
            )

        with sale_col2:
            sale_outlet = st.selectbox(
                "Outlet / channel",
                options=outlet_names if outlet_names else ["Direct Sales"],
                key="sale_outlet",
            )

        with sale_col3:
            sale_variant = st.selectbox(
                "Variant",
                options=[v.name for v in variants],
                key="sale_variant",
            )

        with sale_col4:
            sale_units = st.number_input(
                "Units sold",
                min_value=1,
                step=1,
                key="sale_units",
            )

        selected_variant = next(
            (v for v in variants if v.name == sale_variant),
            None,
        )

        default_sale_price = (
            float(selected_variant.sell_price)
            if selected_variant is not None
            else 0.0
        )

        sale_price_col, sale_note_col = st.columns([1, 3])

        with sale_price_col:
            sale_price = st.number_input(
                "Selling price per unit (R)",
                min_value=0.0,
                step=0.5,
                value=default_sale_price,
                key="sale_price",
            )

        with sale_note_col:
            sale_notes = st.text_input(
                "Notes",
                placeholder="Optional: cash sale, promo sale, customer name, etc.",
                key="sale_notes",
            )

        if st.button("➕ Add Sale to Campaign"):
            campaigns = add_campaign_sale(
                campaigns=campaigns,
                campaign_name=campaign_name,
                sale_date=sale_date,
                outlet=sale_outlet,
                variant=sale_variant,
                units_sold=int(sale_units),
                sell_price=float(sale_price),
                notes=sale_notes,
            )
            save_campaigns(campaigns)
            st.success("Sale recorded")
            st.rerun()

        st.divider()
        st.subheader("Campaign Sales Records")

        if campaign_sales_df.empty:
            st.warning("No sales recorded for this campaign yet.")
        else:
            display_sales_df = campaign_sales_df.copy().reset_index()
            display_sales_df["index"] = display_sales_df["index"].astype(int)
            display_sales_df["Record #"] = display_sales_df["index"] + 1

            display_sales_df = display_sales_df.rename(
                columns={
                    "sale_date": "Sale Date",
                    "outlet": "Outlet",
                    "variant": "Variant",
                    "units_sold": "Units Sold",
                    "sell_price": "Sell Price / Unit (R)",
                    "revenue": "Revenue (R)",
                    "notes": "Notes",
                    "recorded_at": "Recorded At",
                }
            )

            visible_columns = [
                "Record #",
                "Sale Date",
                "Outlet",
                "Variant",
                "Units Sold",
                "Sell Price / Unit (R)",
                "Revenue (R)",
                "Notes",
                "Recorded At",
            ]

            visible_columns = [
                col for col in visible_columns
                if col in display_sales_df.columns
            ]

            st.dataframe(
                display_sales_df[visible_columns].style.format(
                    {
                        "Sell Price / Unit (R)": "{:.2f}",
                        "Revenue (R)": "{:.2f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader("Delete Campaign Sales")

            delete_sales_df = campaign_sales_df.copy().reset_index()
            delete_sales_df["record_index"] = delete_sales_df["index"].astype(int)
            delete_sales_df["Record #"] = delete_sales_df["record_index"] + 1

            def build_delete_label(row: pd.Series) -> str:
                sale_date_value = row.get("sale_date", "")
                outlet_value = row.get("outlet", "")
                variant_value = row.get("variant", "")
                units_value = int(row.get("units_sold", 0))
                revenue_value = float(row.get("revenue", 0.0))

                return (
                    f"Record {int(row['Record #'])} | "
                    f"{sale_date_value} | "
                    f"{outlet_value} | "
                    f"{variant_value} | "
                    f"{units_value} units | "
                    f"{money(revenue_value)}"
                )

            delete_sales_df["Delete Label"] = delete_sales_df.apply(
                build_delete_label,
                axis=1,
            )

            delete_col1, delete_col2 = st.columns([3, 1])

            with delete_col1:
                selected_delete_label = st.selectbox(
                    "Select sale record to delete",
                    options=delete_sales_df["Delete Label"].tolist(),
                    key="selected_campaign_sale_to_delete",
                )

            selected_delete_row = delete_sales_df[
                delete_sales_df["Delete Label"] == selected_delete_label
            ].iloc[0]

            selected_delete_index = int(selected_delete_row["record_index"])

            with delete_col2:
                confirm_delete_sale = st.checkbox(
                    "Confirm delete",
                    key="confirm_delete_campaign_sale",
                )

            delete_button_col1, delete_button_col2 = st.columns(2)

            with delete_button_col1:
                if st.button("🗑️ Delete Selected Sale"):
                    if not confirm_delete_sale:
                        st.error("Tick **Confirm delete** before deleting the sale record.")
                    else:
                        campaigns = delete_campaign_sale_at_index(
                            campaigns=campaigns,
                            campaign_name=campaign_name,
                            record_index=selected_delete_index,
                        )
                        save_campaigns(campaigns)
                        st.success("Sale record deleted")
                        st.rerun()

            with delete_button_col2:
                confirm_clear_all_sales = st.checkbox(
                    "Confirm clear all",
                    key="confirm_clear_all_campaign_sales",
                )

                if st.button("🧹 Clear All Campaign Sales"):
                    if not confirm_clear_all_sales:
                        st.error("Tick **Confirm clear all** before clearing campaign sales.")
                    else:
                        campaigns = clear_campaign_sales(
                            campaigns=campaigns,
                            campaign_name=campaign_name,
                        )
                        save_campaigns(campaigns)
                        st.success("All sales records cleared for this campaign")
                        st.rerun()

        st.divider()
        st.subheader("Campaign Progress by Variant")

        if campaign_variant_progress_df.empty:
            st.warning("No campaign progress available yet.")
        else:
            st.dataframe(
                campaign_variant_progress_df.style.format(
                    {
                        "Actual Revenue (R)": "{:.2f}",
                        "Sell-through %": "{:.1f}%",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            fig_campaign_variant = px.bar(
                campaign_variant_progress_df,
                x="Variant",
                y=["Units Sold", "Remaining Units"],
                title="Campaign Units Sold vs Remaining Units",
                barmode="stack",
            )
            st.plotly_chart(fig_campaign_variant, use_container_width=True)

        st.divider()
        st.subheader("Campaign Progress by Outlet")

        if campaign_outlet_progress_df.empty:
            st.warning("No outlet campaign progress available yet.")
        else:
            st.dataframe(
                campaign_outlet_progress_df.style.format(
                    {
                        "Projected Revenue (R)": "{:.2f}",
                        "Projected Profit (R)": "{:.2f}",
                        "Actual Revenue (R)": "{:.2f}",
                        "Sell-through %": "{:.1f}%",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            fig_campaign_outlet = px.bar(
                campaign_outlet_progress_df,
                x="Outlet",
                y="Actual Revenue (R)",
                color="Variant",
                title="Actual Campaign Revenue by Outlet and Variant",
            )
            st.plotly_chart(fig_campaign_outlet, use_container_width=True)

        st.divider()
        st.subheader("Campaign Revenue Target")

        target_progress = (
            actual_revenue / projected_campaign_revenue * 100
            if projected_campaign_revenue
            else 0
        )

        st.progress(min(target_progress / 100, 1.0))

        st.info(
            f"Actual revenue: **{money(actual_revenue)}** vs projected campaign revenue: "
            f"**{money(projected_campaign_revenue)}** | Progress: **{target_progress:.1f}%**"
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

st.divider()
st.subheader("⬇️ Export Calculations")

e1, e2, e3, e4, e5, e6, e7, e8 = st.columns(8)

e1.download_button(
    "📗 Excel all sheets",
    build_excel(),
    "pricing_margin_model.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

e2.download_button(
    "📄 Unit Economics CSV",
    ue_df.to_csv(index=False),
    "unit_economics.csv",
    "text/csv",
)

e3.download_button(
    "📄 First Order Mix CSV",
    order_df.to_csv(index=False),
    "first_order_mix.csv",
    "text/csv",
)

e4.download_button(
    "🧮 Mix Explanation CSV",
    mix_explanation_df.to_csv(index=False),
    "mix_explanation.csv",
    "text/csv",
)

e5.download_button(
    f"📄 {plan_weeks}-Week Plan CSV",
    plan_df.to_csv(index=False),
    f"{plan_weeks}_week_plan.csv",
    "text/csv",
)

e6.download_button(
    "🏪 Outlet Detail CSV",
    outlet_detail_df.to_csv(index=False),
    "outlet_detail_allocation.csv",
    "text/csv",
)

e7.download_button(
    "🏷️ Competitor Pricing CSV",
    competitor_df.to_csv(index=False),
    "competitor_pricing.csv",
    "text/csv",
)

e8.download_button(
    "🎯 Campaign Sales CSV",
    campaign_sales_df.to_csv(index=False),
    "campaign_sales.csv",
    "text/csv",
)

st.caption("Built with Streamlit • All values in South African Rand R")