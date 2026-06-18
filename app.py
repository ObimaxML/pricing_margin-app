"""
Pricing & Margin Model - Streamlit Web App
===========================================
Interactive calculator for a repackaging business that buys 5kg bags from a
supplier, receives promotional free stock, and resells smaller variants.

Run with: python -m streamlit run app.py
"""

from __future__ import annotations

import io
import random
import re
import base64
from pathlib import Path

from PIL import Image

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import logic


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
        .main .block-container {
            padding-top: 1rem;
        }

        h1, h2, h3 {
            color: #1f2a44;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.6rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            background: #f0f2f6;
            border-radius: 8px 8px 0 0;
            padding: 10px 18px;
        }

        .stTabs [aria-selected="true"] {
            background: #1f77b4;
            color: white;
        }

        .peony-header {
            width: 100%;
            margin-bottom: 1rem;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(31, 42, 68, 0.16);
            background: #ffffff;
        }

        .peony-header-img {
            width: 100%;
            display: block;
            object-fit: cover;
        }

        .sidebar-logo-wrap {
            width: 100%;
            text-align: center;
            padding: 0.6rem 0 1rem 0;
            margin-bottom: 0.5rem;
        }

        .sidebar-logo-img {
            width: 100%;
            max-width: 260px;
            border-radius: 12px;
            background: white;
            padding: 6px;
            box-shadow: 0 4px 14px rgba(31, 42, 68, 0.12);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

CURRENCY = "R"
FIVE_KG_GRAMS = 5000

ASSETS_DIR = Path(__file__).parent / "assets"
PEONY_BANNER_PATH = ASSETS_DIR / "peony_fresh_banner.png"


def image_to_base64(image_path: Path) -> str:
    """Converts an image file into a base64 string for HTML/CSS rendering."""

    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()


def crop_logo_from_banner(
    banner_path: Path,
    output_path: Path,
) -> Path:
    """
    Crops the central Peony Fresh logo from the full banner image
    for use in the sidebar.
    """

    if output_path.exists():
        return output_path

    image = Image.open(banner_path)
    width, height = image.size

    # Crop central logo area from the Peony Fresh banner.
    left = int(width * 0.27)
    top = int(height * 0.05)
    right = int(width * 0.73)
    bottom = int(height * 0.95)

    logo = image.crop((left, top, right, bottom))
    logo.save(output_path)

    return output_path


def render_peony_header() -> None:
    """Renders the full Peony Fresh banner at the top of the main app."""

    if not PEONY_BANNER_PATH.exists():
        st.warning(
            "Peony Fresh banner image not found. "
            "Please save it as assets/peony_fresh_banner.png"
        )
        return

    banner_base64 = image_to_base64(PEONY_BANNER_PATH)

    st.markdown(
        f"""
        <div class="peony-header">
            <img src="data:image/png;base64,{banner_base64}" class="peony-header-img" />
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_logo() -> None:
    """Renders only the Peony Fresh logo in the sidebar."""

    if not PEONY_BANNER_PATH.exists():
        return

    logo_path = ASSETS_DIR / "peony_fresh_logo.png"

    try:
        crop_logo_from_banner(
            banner_path=PEONY_BANNER_PATH,
            output_path=logo_path,
        )

        logo_base64 = image_to_base64(logo_path)

        st.sidebar.markdown(
            f"""
            <div class="sidebar-logo-wrap">
                <img src="data:image/png;base64,{logo_base64}" class="sidebar-logo-img" />
            </div>
            """,
            unsafe_allow_html=True,
        )

    except Exception:
        st.sidebar.image(
            str(PEONY_BANNER_PATH),
            use_container_width=True,
        )


def money(x: float) -> str:
    return f"{CURRENCY}{x:,.2f}"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_variant_grams(variant) -> float:
    """
    Determines variant size in grams.

    Examples:
    - 100g Mini Sachet -> 100
    - 200g Sachet -> 200
    - 500g Pack -> 500
    - 1kg Pack -> 1000
    - 2kg Pack -> 2000
    - 5kg Bulk -> 5000
    """

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


def add_5kg_equivalent_column(
    order_df: pd.DataFrame,
    variants,
) -> pd.DataFrame:
    """
    Adds a '5kg Packs Equivalent' column immediately after 'Units'.

    Formula:
    Units × variant grams / 5000
    """

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


def build_mix_explanation(
    order_df: pd.DataFrame,
    variants,
) -> pd.DataFrame:
    """
    Shows how total units are derived from grams and variant size.
    """

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
    """
    Builds an adjustable weekly sales plan.
    """

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

        if total_weight == 0:
            weights = [1 / weeks] * weeks
        else:
            weights = [w / total_weight for w in custom_weights]

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


def build_outlet_variant_allocation(
    outlet_names: list[str],
    outlet_variant_units: dict[str, dict[str, int]],
    variants,
    order_df: pd.DataFrame,
    ue_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Builds detailed outlet allocation by outlet, variant and number of units.

    Returns:
    1. outlet_detail_df  - outlet x variant allocation
    2. outlet_summary_df - summary by outlet
    3. variant_check_df  - available vs allocated by variant
    """

    clean_outlets = [
        outlet.strip()
        for outlet in outlet_names
        if outlet.strip()
    ]

    if not clean_outlets:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    available_units_map = {}

    if "Variant" in order_df.columns and "Units" in order_df.columns:
        available_units_map = dict(
            zip(
                order_df["Variant"],
                order_df["Units"],
            )
        )

    cost_map = {}
    sell_price_map = {}
    profit_map = {}

    if "Variant" in ue_df.columns:
        if "Total Cost (R)" in ue_df.columns:
            cost_map = dict(
                zip(
                    ue_df["Variant"],
                    ue_df["Total Cost (R)"],
                )
            )

        if "Sell Price (R)" in ue_df.columns:
            sell_price_map = dict(
                zip(
                    ue_df["Variant"],
                    ue_df["Sell Price (R)"],
                )
            )

        if "Profit / Unit (R)" in ue_df.columns:
            profit_map = dict(
                zip(
                    ue_df["Variant"],
                    ue_df["Profit / Unit (R)"],
                )
            )

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


def build_competitor_pricing(
    variants,
    competitor_names: list[str],
    competitor_prices: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """
    Compares Peony selling prices against one or more competitors.

    R0 means that competitor does not sell that variant.
    """

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
    """
    Builds a long-form dataframe for grouped competitor price charts.
    """

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


def set_mix_preset(
    variants,
    preset_name: str,
) -> None:
    """
    Updates Streamlit session_state for first order mix sliders.
    """

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


# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------

render_sidebar_logo()

st.sidebar.title("⚙️ Model Inputs")

st.sidebar.subheader("Supplier & Stock")

bag_cost = st.sidebar.number_input(
    "Bag cost from supplier (R / 5kg bag)",
    min_value=1.0,
    value=95.0,
    step=1.0,
    help="Base price you pay Peony Trading per 5kg bag.",
)

free_mode = st.sidebar.radio(
    "Free stock entry mode",
    ["Percentage", "X free per Y ordered"],
    horizontal=False,
)

if free_mode == "Percentage":
    free_stock_pct = st.sidebar.number_input(
        "Free stock %",
        min_value=0.0,
        max_value=100.0,
        value=10.0,
        step=1.0,
        help="Percentage of paid bags received free as promotion.",
    )
else:
    c1, c2 = st.sidebar.columns(2)

    free_x = c1.number_input(
        "Free bags",
        min_value=0,
        value=5,
        step=1,
    )

    per_y = c2.number_input(
        "Per ordered",
        min_value=1,
        value=50,
        step=1,
    )

    free_stock_pct = (free_x / per_y) * 100.0
    st.sidebar.caption(f"➡️ Effective free stock: **{free_stock_pct:.1f}%**")


st.sidebar.subheader("Order & Budget")

budget = st.sidebar.number_input(
    "Budget (R)",
    min_value=0.0,
    value=5000.0,
    step=100.0,
    help="Total cash available for the first order.",
)

order_qty_bags = st.sidebar.number_input(
    "Order quantity paid bags",
    min_value=1,
    value=60,
    step=1,
    help="For example: 60 paid bags plus 10% free stock gives 66 total 5kg buckets.",
)


st.sidebar.subheader("Variable Costs")

transport_cost = st.sidebar.number_input(
    "Transport / collection cost (R per order)",
    min_value=0.0,
    value=150.0,
    step=10.0,
    help="Fuel, delivery, or collection cost for the entire order.",
)

other_variable_cost = st.sidebar.number_input(
    "Other variable costs (R per order)",
    min_value=0.0,
    value=0.0,
    step=10.0,
    help="Any other variable costs per order, such as labour or storage.",
)

total_variable_cost = transport_cost + other_variable_cost


st.sidebar.subheader("Payment Terms")

payment_term = st.sidebar.selectbox(
    "Supplier payment term",
    options=["Cash on Delivery", "7-Day", "14-Day", "30-Day"],
    index=0,
    help="When payment to the supplier is due.",
)

TERM_DAYS = {
    "Cash on Delivery": 0,
    "7-Day": 7,
    "14-Day": 14,
    "30-Day": 30,
}

term_days = TERM_DAYS[payment_term]

customer_term = st.sidebar.selectbox(
    "Customer payment term receivables",
    options=["Cash on Delivery", "7-Day", "14-Day", "30-Day"],
    index=0,
    help="When your customers pay you.",
)

customer_term_days = TERM_DAYS[customer_term]


st.sidebar.subheader("Selling Prices & Packaging")

variants = logic.default_variants()

for v in variants:
    with st.sidebar.expander(v.name, expanded=False):
        v.sell_price = st.number_input(
            f"Sell price (R) — {v.name}",
            min_value=0.0,
            value=float(v.sell_price),
            step=0.5,
            key=f"sell_{v.name}",
        )

        if v.name != "5kg Bulk":
            v.packaging_cost = st.number_input(
                f"Packaging cost (R) — {v.name}",
                min_value=0.0,
                value=float(v.packaging_cost),
                step=0.1,
                key=f"pkg_{v.name}",
            )


# ---------------------------------------------------------------------------
# Dynamic competitor pricing sidebar settings
# ---------------------------------------------------------------------------

st.sidebar.subheader("Competitor Pricing")

st.sidebar.caption(
    "Add one or more competitors. Enter R0 if a competitor does not sell a specific variant."
)

number_of_competitors = st.sidebar.number_input(
    "Number of competitors",
    min_value=1,
    max_value=10,
    value=3,
    step=1,
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
        competitor_name = st.text_input(
            f"Competitor name {competitor_index + 1}",
            value=default_competitor_name,
            key=f"competitor_name_{competitor_index}",
        ).strip()

        if not competitor_name:
            competitor_name = f"Competitor {competitor_index + 1}"

        competitor_names.append(competitor_name)
        competitor_prices[competitor_name] = {}

        for v in variants:
            competitor_prices[competitor_name][v.name] = st.number_input(
                f"{competitor_name} price (R) — {v.name}",
                min_value=0.0,
                value=0.0,
                step=0.5,
                key=f"competitor_{competitor_index}_price_{v.name}",
                help="Enter 0 if this competitor does not sell this exact pack size.",
            )


# ---------------------------------------------------------------------------
# First Order Mix with preset buttons
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
    "100g Mini Sachet": 30,
    "200g Sachet": 25,
    "500g Pack": 20,
    "1kg Pack": 15,
    "2kg Pack": 7,
    "5kg Bulk": 3,
}

mix_weights = {}

for v in variants:
    mix_key = f"mix_{v.name}"

    if mix_key not in st.session_state:
        st.session_state[mix_key] = int(default_mix.get(v.name, 0))

    mix_weights[v.name] = st.sidebar.slider(
        v.name,
        0,
        100,
        key=mix_key,
    )


# ---------------------------------------------------------------------------
# Sales plan sidebar settings
# ---------------------------------------------------------------------------

st.sidebar.subheader("Sales Plan Settings")

plan_weeks = st.sidebar.slider(
    "Sales plan duration weeks",
    min_value=1,
    max_value=12,
    value=5,
    step=1,
    help="Choose how many weeks you want the sales plan to cover.",
)

sales_pattern = st.sidebar.selectbox(
    "Sales pattern",
    options=[
        "Even Split",
        "Slow Start / Ramp Up",
        "Fast Start",
        "Custom Weekly %",
    ],
    index=1,
    help="Choose how the stock should be sold over the selected period.",
)

custom_weekly_weights = []

if sales_pattern == "Custom Weekly %":
    st.sidebar.caption(
        "Set the sales weight for each week. These do not need to total 100%; "
        "the app will normalise them."
    )

    for week in range(1, plan_weeks + 1):
        custom_weekly_weights.append(
            st.sidebar.number_input(
                f"Week {week} sales weight",
                min_value=0.0,
                value=round(100 / plan_weeks, 1),
                step=1.0,
                key=f"custom_week_{week}",
            )
        )


# ---------------------------------------------------------------------------
# Outlet allocation sidebar settings
# ---------------------------------------------------------------------------

st.sidebar.subheader("Outlet Allocation")

st.sidebar.caption(
    "Allocate exact units per outlet and per variant. "
    "Use 0 where an outlet will not receive that variant."
)

number_of_outlets = st.sidebar.number_input(
    "Number of outlets / channels",
    min_value=1,
    max_value=10,
    value=3,
    step=1,
    help="Add outlets or sales channels that will receive stock allocation.",
)

outlet_names = []
outlet_variant_units: dict[str, dict[str, int]] = {}

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

    with st.sidebar.expander(
        f"Outlet / Channel {outlet_index + 1}",
        expanded=False,
    ):
        outlet_name = st.text_input(
            f"Outlet name {outlet_index + 1}",
            value=default_name,
            key=f"outlet_name_{outlet_index}",
        ).strip()

        if not outlet_name:
            outlet_name = f"Outlet {outlet_index + 1}"

        outlet_names.append(outlet_name)
        outlet_variant_units[outlet_name] = {}

        st.caption("Enter units allocated to this outlet per variant.")

        for v in variants:
            outlet_variant_units[outlet_name][v.name] = st.number_input(
                f"{outlet_name} units — {v.name}",
                min_value=0,
                value=0,
                step=1,
                key=f"outlet_{outlet_index}_units_{v.name}",
                help="Number of units of this variant allocated to this outlet.",
            )


# ---------------------------------------------------------------------------
# Computations
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

order_df = order["table"]

order_df = add_5kg_equivalent_column(
    order_df=order_df,
    variants=variants,
)

mix_explanation_df = build_mix_explanation(
    order_df=order_df,
    variants=variants,
)

summ = order["summary"]

total_units = int(order_df["Units"].sum())

net_profit_after_variable_costs = summ["total_profit"] - total_variable_cost

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
        ue_df.to_excel(
            writer,
            sheet_name="Unit Economics",
            index=False,
        )

        order_df.to_excel(
            writer,
            sheet_name="First Order Mix",
            index=False,
        )

        mix_explanation_df.to_excel(
            writer,
            sheet_name="Mix Explanation",
            index=False,
        )

        pd.DataFrame([summ]).to_excel(
            writer,
            sheet_name="Order Summary",
            index=False,
        )

        plan_df.to_excel(
            writer,
            sheet_name=f"{plan_weeks}-Week Plan",
            index=False,
        )

        outlet_summary_df.to_excel(
            writer,
            sheet_name="Outlet Summary",
            index=False,
        )

        outlet_detail_df.to_excel(
            writer,
            sheet_name="Outlet Detail",
            index=False,
        )

        outlet_variant_check_df.to_excel(
            writer,
            sheet_name="Outlet Variant Check",
            index=False,
        )

        competitor_df.to_excel(
            writer,
            sheet_name="Competitor Pricing",
            index=False,
        )

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
        ).to_excel(
            writer,
            sheet_name="Cash Flow & Terms",
            index=False,
        )

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Header & KPIs
# ---------------------------------------------------------------------------

render_peony_header()

st.title("💰 Peony Washing Powder Pricing & Margin Model")

st.caption(
    "Buy 5kg bags • receive promotional free stock • repackage into retail "
    "variants • compare competitor prices • allocate exact stock units to outlets • "
    "track cash turnover and an adjustable weekly sales plan."
)

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric(
    "Effective Bag Cost",
    money(summ["effective_bag_cost"]),
    delta=money(summ["effective_bag_cost"] - bag_cost),
)

k2.metric(
    "Cost / gram",
    money(eff_cpg),
)

k3.metric(
    "Total Investment",
    money(summ["investment"] + total_variable_cost),
    help="Stock cost + transport + other variable costs.",
)

k4.metric(
    "Projected Profit",
    money(net_profit_after_variable_costs),
)

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

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "📊 Unit Economics",
        "📦 First Order Mix",
        f"📅 {plan_weeks}-Week Sales Plan",
        "🏪 Outlet Allocation",
        "🏷️ Competitor Pricing",
        "💳 Cash Flow & Terms",
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

        fig.update_traces(
            texttemplate="R%{text:.2f}",
            textposition="outside",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

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

        fig2.update_layout(
            barmode="stack",
            title="Cost vs Profit Sell Price",
        )

        st.plotly_chart(
            fig2,
            use_container_width=True,
        )

    fig3 = px.line(
        ue_df,
        x="Variant",
        y="Margin %",
        markers=True,
        title="Margin % Comparison",
        range_y=[0, 100],
    )

    st.plotly_chart(
        fig3,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Tab 2: First Order Mix
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("Recommended First Order Mix")

    s1, s2, s3, s4, s5 = st.columns(5)

    s1.metric(
        "Paid Bags",
        f"{summ['paid_bags']}",
    )

    s2.metric(
        "Free Bags",
        f"{summ['free_bags']}",
    )

    s3.metric(
        "Total 5kg Buckets",
        f"{summ['paid_bags'] + summ['free_bags']}",
    )

    s4.metric(
        "Total Revenue",
        money(summ["total_revenue"]),
    )

    s5.metric(
        "Total Profit before var. costs",
        money(summ["total_profit"]),
    )

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

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    with c2:
        fig = px.bar(
            order_df,
            x="Variant",
            y=["Cost (R)", "Profit (R)"],
            title="Revenue Composition Cost + Profit",
            barmode="stack",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Tab 3: Adjustable Sales Plan
# ---------------------------------------------------------------------------

with tab3:
    st.subheader(f"{plan_weeks}-Week Sales Target Plan")

    st.caption(
        f"Sales pattern: **{sales_pattern}**"
    )

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

        fig.update_traces(
            texttemplate="R%{text:.2f}",
            textposition="outside",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

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

        fig.update_layout(
            title="Cumulative Profit & Revenue Progression",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    st.divider()

    st.subheader("Break-even Analysis")

    investment_required = summ["investment"] + total_variable_cost

    break_even_week = None

    for _, row in plan_df.iterrows():
        if row["Cumulative Profit (R)"] >= investment_required:
            break_even_week = row["Week"]
            break

    be1, be2, be3 = st.columns(3)

    be1.metric(
        "Investment Required",
        money(investment_required),
    )

    be2.metric(
        "Net Profit Target",
        money(investment_required),
    )

    if break_even_week:
        be3.metric(
            "Break-even Week",
            break_even_week,
        )

        st.success(
            f"You are projected to recover your investment by **{break_even_week}**."
        )
    else:
        be3.metric(
            "Break-even Week",
            "Not reached",
        )

        st.warning(
            "The selected plan does not recover the full investment within the selected period."
        )

    st.divider()

    st.subheader("Stock Movement View")

    stock_df = plan_df[
        [
            "Week",
            "Units Target",
            "Cumulative Units",
        ]
    ].copy()

    stock_df["Opening Units"] = total_units - stock_df[
        "Cumulative Units"
    ].shift(
        fill_value=0
    )

    stock_df["Closing Units"] = total_units - stock_df["Cumulative Units"]

    if total_units:
        stock_df["Remaining Stock %"] = (
            stock_df["Closing Units"] / total_units * 100
        )
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
        stock_df.style.format(
            {
                "Remaining Stock %": "{:.1f}%",
            }
        ),
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
        st.info(
            f"Projected closing stock after {plan_weeks} weeks: **{final_stock_pct:.1f}%**."
        )


# ---------------------------------------------------------------------------
# Tab 4: Outlet Allocation
# ---------------------------------------------------------------------------

with tab4:
    st.subheader("🏪 Outlet / Channel Allocation")

    st.caption(
        "Allocate exact units by outlet and variant. "
        "This section checks whether you have under-allocated or over-allocated stock."
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

        o1.metric(
            "Available Units",
            f"{total_available_units:,}",
        )

        o2.metric(
            "Allocated Units",
            f"{total_allocated_units:,}",
        )

        o3.metric(
            "Remaining Units",
            f"{remaining_units:,}",
        )

        o4.metric(
            "Allocated 5kg Equiv.",
            f"{total_allocated_5kg_equiv:.1f}",
        )

        o5.metric(
            "Projected Profit",
            money(total_allocated_profit),
        )

        if remaining_units < 0:
            st.error(
                "You have allocated more units than are available. "
                "Check the variant allocation table below."
            )
        elif remaining_units == 0:
            st.success("All available units have been fully allocated.")
        else:
            st.warning(
                f"You still have **{remaining_units:,} units** remaining, "
                f"equal to **{remaining_5kg_equiv:.1f} × 5kg packs**."
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

            fig_outlet_units.update_traces(
                textposition="outside",
            )

            st.plotly_chart(
                fig_outlet_units,
                use_container_width=True,
            )

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

            st.plotly_chart(
                fig_outlet_profit,
                use_container_width=True,
            )

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
                "Some variants are over-allocated. Reduce outlet units for the variants marked ❌."
            )

        remaining_stock = outlet_variant_check_df[
            outlet_variant_check_df["Remaining Units"] > 0
        ]

        if not remaining_stock.empty:
            st.info(
                "Some variants still have remaining stock. You can allocate them to outlets "
                "or keep them as reserve stock."
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

            st.plotly_chart(
                fig_comp_prices,
                use_container_width=True,
            )

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

        st.plotly_chart(
            fig_avg_gap,
            use_container_width=True,
        )

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

    p1.metric(
        "Below Competitor Avg",
        below_avg_count,
    )

    p2.metric(
        "Above Competitor Avg",
        above_avg_count,
    )

    p3.metric(
        "Equal to Avg",
        equal_avg_count,
    )

    p4.metric(
        "No Competitor Price",
        no_price_count,
    )

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

    vc1.metric(
        "Transport / Collection",
        money(transport_cost),
    )

    vc2.metric(
        "Other Variable Costs",
        money(other_variable_cost),
    )

    vc3.metric(
        "Total Variable Costs",
        money(total_variable_cost),
    )

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

        st.plotly_chart(
            fig_vc,
            use_container_width=True,
        )

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

        profit_waterfall.update_layout(
            title="Revenue to Net Profit Waterfall",
        )

        st.plotly_chart(
            profit_waterfall,
            use_container_width=True,
        )

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
# Export
# ---------------------------------------------------------------------------

st.divider()

st.subheader("⬇️ Export Calculations")

e1, e2, e3, e4, e5, e6, e7 = st.columns(7)

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

st.caption("Built with Streamlit • All values in South African Rand R")