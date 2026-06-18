"""
Pricing & Margin Model - Streamlit Web App
===========================================
Interactive calculator for a repackaging business that buys 5kg bags from a
supplier, receives promotional free stock, and resells smaller variants.

Run with: python -m streamlit run app.py
"""

from __future__ import annotations

import io

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

CURRENCY = "R"


def money(x: float) -> str:
    return f"{CURRENCY}{x:,.2f}"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

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

    Supports:
    - Even Split
    - Slow Start / Ramp Up
    - Fast Start
    - Custom Weekly %
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

    # Fix small rounding differences so total units match exactly
    if not plan_df.empty:
        unit_difference = total_units - int(plan_df["Units Target"].sum())
        plan_df.loc[plan_df.index[-1], "Units Target"] += unit_difference
        plan_df["Cumulative Units"] = plan_df["Units Target"].cumsum()

    return plan_df


def build_outlet_allocation(
    outlet_names: list[str],
    allocation_weights: list[float],
    total_units: int,
    total_revenue: float,
    total_profit: float,
) -> pd.DataFrame:
    """
    Allocates total units, revenue and profit across outlets/channels.
    """

    clean_rows = [
        (name.strip(), weight)
        for name, weight in zip(outlet_names, allocation_weights)
        if name.strip()
    ]

    if not clean_rows:
        return pd.DataFrame()

    clean_outlet_names = [row[0] for row in clean_rows]
    clean_weights = [row[1] for row in clean_rows]

    total_weight = sum(clean_weights)

    if total_weight == 0:
        weights = [1 / len(clean_outlet_names)] * len(clean_outlet_names)
    else:
        weights = [w / total_weight for w in clean_weights]

    rows = []

    for outlet, weight in zip(clean_outlet_names, weights):
        allocated_units = round(total_units * weight)
        allocated_revenue = total_revenue * weight
        allocated_profit = total_profit * weight

        rows.append(
            {
                "Outlet": outlet,
                "Allocation %": weight * 100,
                "Units Allocated": allocated_units,
                "Revenue (R)": allocated_revenue,
                "Profit (R)": allocated_profit,
            }
        )

    outlet_df = pd.DataFrame(rows)

    # Fix rounding difference so total units match exactly
    if not outlet_df.empty:
        unit_difference = total_units - int(outlet_df["Units Allocated"].sum())
        outlet_df.loc[outlet_df.index[-1], "Units Allocated"] += unit_difference

    return outlet_df


def build_competitor_pricing(
    variants,
    omo_prices: dict[str, float],
    avg_market_prices: dict[str, float],
) -> pd.DataFrame:
    """
    Compares Peony selling prices against OMO and market average prices.
    """

    rows = []

    for v in variants:
        peony_price = float(v.sell_price)
        omo_price = float(omo_prices.get(v.name, 0))
        avg_price = float(avg_market_prices.get(v.name, 0))

        omo_gap = peony_price - omo_price if omo_price > 0 else 0
        avg_gap = peony_price - avg_price if avg_price > 0 else 0

        omo_gap_pct = (omo_gap / omo_price * 100) if omo_price > 0 else 0
        avg_gap_pct = (avg_gap / avg_price * 100) if avg_price > 0 else 0

        if omo_price <= 0:
            omo_position = "No OMO price"
        elif peony_price < omo_price:
            omo_position = "Cheaper than OMO"
        elif peony_price == omo_price:
            omo_position = "Same as OMO"
        else:
            omo_position = "More expensive than OMO"

        if avg_price <= 0:
            avg_position = "No market avg"
        elif peony_price < avg_price:
            avg_position = "Below market avg"
        elif peony_price == avg_price:
            avg_position = "At market avg"
        else:
            avg_position = "Above market avg"

        rows.append(
            {
                "Variant": v.name,
                "Peony Price (R)": peony_price,
                "OMO Price (R)": omo_price,
                "Market Avg Price (R)": avg_price,
                "Peony vs OMO Gap (R)": omo_gap,
                "Peony vs OMO Gap %": omo_gap_pct,
                "Peony vs Market Avg Gap (R)": avg_gap,
                "Peony vs Market Avg Gap %": avg_gap_pct,
                "OMO Position": omo_position,
                "Market Position": avg_position,
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------

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
    "Order quantity (paid bags)",
    min_value=1,
    value=50,
    step=1,
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
# Competitor pricing sidebar settings
# ---------------------------------------------------------------------------

st.sidebar.subheader("Competitor Pricing")

st.sidebar.caption(
    "Enter competitor prices for each variant. Use 0 if a competitor does not sell that exact size."
)

omo_prices = {}
avg_market_prices = {}

default_omo_prices = {
    "100g Mini Sachet": 0.0,
    "200g Sachet": 0.0,
    "500g Pack": 25.0,
    "1kg Pack": 45.0,
    "2kg Pack": 85.0,
    "5kg Bulk": 180.0,
}

default_avg_market_prices = {
    "100g Mini Sachet": 6.0,
    "200g Sachet": 10.0,
    "500g Pack": 22.0,
    "1kg Pack": 40.0,
    "2kg Pack": 75.0,
    "5kg Bulk": 150.0,
}

for v in variants:
    with st.sidebar.expander(f"Competitor Prices — {v.name}", expanded=False):
        omo_prices[v.name] = st.number_input(
            f"OMO price (R) — {v.name}",
            min_value=0.0,
            value=float(default_omo_prices.get(v.name, 0.0)),
            step=0.5,
            key=f"omo_price_{v.name}",
            help="Enter 0 if OMO does not sell this exact pack size.",
        )

        avg_market_prices[v.name] = st.number_input(
            f"Average market price (R) — {v.name}",
            min_value=0.0,
            value=float(default_avg_market_prices.get(v.name, 0.0)),
            step=0.5,
            key=f"avg_market_price_{v.name}",
            help="Average selling price across competing brands or nearby outlets.",
        )


st.sidebar.subheader("First Order Mix (%)")

mix_weights = {}

default_mix = {
    "100g Mini Sachet": 30,
    "200g Sachet": 25,
    "500g Pack": 20,
    "1kg Pack": 15,
    "2kg Pack": 7,
    "5kg Bulk": 3,
}

for v in variants:
    mix_weights[v.name] = st.sidebar.slider(
        v.name,
        0,
        100,
        default_mix.get(v.name, 0),
        key=f"mix_{v.name}",
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

number_of_outlets = st.sidebar.number_input(
    "Number of outlets / channels",
    min_value=1,
    max_value=10,
    value=3,
    step=1,
    help="Add outlets or sales channels that will receive stock allocation.",
)

outlet_names = []
outlet_allocation_weights = []

default_outlets = [
    "IML Convenience Store",
    "Opi Hoeki Store",
    "Direct Household Sales",
]

for i in range(number_of_outlets):
    default_name = (
        default_outlets[i]
        if i < len(default_outlets)
        else f"Outlet {i + 1}"
    )

    with st.sidebar.expander(f"Outlet / Channel {i + 1}", expanded=False):
        outlet_name = st.text_input(
            f"Outlet name {i + 1}",
            value=default_name,
            key=f"outlet_name_{i}",
        )

        outlet_weight = st.number_input(
            f"Allocation weight {i + 1}",
            min_value=0.0,
            max_value=100.0,
            value=round(100 / number_of_outlets, 1),
            step=1.0,
            key=f"outlet_weight_{i}",
            help=(
                "This does not need to total 100%. "
                "The app will normalise all outlet weights."
            ),
        )

        outlet_names.append(outlet_name)
        outlet_allocation_weights.append(outlet_weight)


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

outlet_df = build_outlet_allocation(
    outlet_names=outlet_names,
    allocation_weights=outlet_allocation_weights,
    total_units=total_units,
    total_revenue=summ["total_revenue"],
    total_profit=net_profit_after_variable_costs,
)

competitor_df = build_competitor_pricing(
    variants=variants,
    omo_prices=omo_prices,
    avg_market_prices=avg_market_prices,
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

        outlet_df.to_excel(
            writer,
            sheet_name="Outlet Allocation",
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

st.title("💰 Peony Washing Powder Pricing & Margin Model")

st.caption(
    "Buy 5kg bags • receive promotional free stock • repackage into retail "
    "variants • compare competitor prices • track outlet allocation, cash turnover "
    "and an adjustable weekly sales plan."
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

    s1, s2, s3, s4 = st.columns(4)

    s1.metric(
        "Paid Bags",
        f"{summ['paid_bags']}",
    )

    s2.metric(
        "Free Bags",
        f"{summ['free_bags']}",
    )

    s3.metric(
        "Total Revenue",
        money(summ["total_revenue"]),
    )

    s4.metric(
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

    st.info(
        f"Grams available: **{summ['grams_available']:,} g** • "
        f"Grams used: **{summ['grams_used']:,} g** • "
        f"Utilisation: **{(summ['grams_used'] / summ['grams_available'] * 100) if summ['grams_available'] else 0:.1f}%**"
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
        "Allocate stock, revenue and profit across outlets or sales channels. "
        "The allocation weights are normalised automatically."
    )

    if outlet_df.empty:
        st.warning("No outlet allocation available.")
    else:
        o1, o2, o3 = st.columns(3)

        o1.metric(
            "Total Outlets / Channels",
            len(outlet_df),
        )

        o2.metric(
            "Total Units Allocated",
            f"{int(outlet_df['Units Allocated'].sum()):,}",
        )

        o3.metric(
            "Total Projected Profit",
            money(outlet_df["Profit (R)"].sum()),
        )

        st.dataframe(
            outlet_df.style.format(
                {
                    "Allocation %": "{:.1f}%",
                    "Revenue (R)": "{:.2f}",
                    "Profit (R)": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            fig_outlet_units = px.pie(
                outlet_df,
                names="Outlet",
                values="Units Allocated",
                title="Units Allocated by Outlet",
                hole=0.4,
            )

            st.plotly_chart(
                fig_outlet_units,
                use_container_width=True,
            )

        with c2:
            fig_outlet_profit = px.bar(
                outlet_df,
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

        st.info(
            f"Current allocation total: **{outlet_df['Allocation %'].sum():.1f}%** "
            "after normalisation."
        )


# ---------------------------------------------------------------------------
# Tab 5: Competitor Pricing
# ---------------------------------------------------------------------------

with tab5:
    st.subheader("🏷️ Competitor Pricing Comparison")

    st.caption(
        "Compare Peony selling prices against OMO and average market selling prices."
    )

    st.dataframe(
        competitor_df.style.format(
            {
                "Peony Price (R)": "{:.2f}",
                "OMO Price (R)": "{:.2f}",
                "Market Avg Price (R)": "{:.2f}",
                "Peony vs OMO Gap (R)": "{:.2f}",
                "Peony vs OMO Gap %": "{:.1f}%",
                "Peony vs Market Avg Gap (R)": "{:.2f}",
                "Peony vs Market Avg Gap %": "{:.1f}%",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        fig_comp_prices = go.Figure()

        fig_comp_prices.add_bar(
            name="Peony",
            x=competitor_df["Variant"],
            y=competitor_df["Peony Price (R)"],
        )

        fig_comp_prices.add_bar(
            name="OMO",
            x=competitor_df["Variant"],
            y=competitor_df["OMO Price (R)"],
        )

        fig_comp_prices.add_bar(
            name="Market Avg",
            x=competitor_df["Variant"],
            y=competitor_df["Market Avg Price (R)"],
        )

        fig_comp_prices.update_layout(
            title="Peony vs OMO vs Market Average Price",
            barmode="group",
            yaxis_title="Selling Price (R)",
        )

        st.plotly_chart(
            fig_comp_prices,
            use_container_width=True,
        )

    with c2:
        fig_gap = px.bar(
            competitor_df,
            x="Variant",
            y=[
                "Peony vs OMO Gap (R)",
                "Peony vs Market Avg Gap (R)",
            ],
            title="Price Gap: Peony vs Competitors",
            barmode="group",
        )

        st.plotly_chart(
            fig_gap,
            use_container_width=True,
        )

    st.divider()

    st.subheader("Pricing Position Summary")

    cheaper_than_omo = competitor_df[
        competitor_df["OMO Position"] == "Cheaper than OMO"
    ].shape[0]

    more_expensive_than_omo = competitor_df[
        competitor_df["OMO Position"] == "More expensive than OMO"
    ].shape[0]

    cheaper_than_market = competitor_df[
        competitor_df["Market Position"] == "Below market avg"
    ].shape[0]

    p1, p2, p3, p4 = st.columns(4)

    p1.metric(
        "Cheaper than OMO",
        cheaper_than_omo,
    )

    p2.metric(
        "More Expensive than OMO",
        more_expensive_than_omo,
    )

    p3.metric(
        "Below Market Avg",
        cheaper_than_market,
    )

    p4.metric(
        "Total Variants Compared",
        len(competitor_df),
    )

    st.info(
        "Use this tab to decide whether Peony should be positioned as a budget, "
        "value-for-money, or direct competitor to premium brands like OMO."
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

e1, e2, e3, e4, e5, e6 = st.columns(6)

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
    f"📄 {plan_weeks}-Week Plan CSV",
    plan_df.to_csv(index=False),
    f"{plan_weeks}_week_plan.csv",
    "text/csv",
)

e5.download_button(
    "🏪 Outlet Allocation CSV",
    outlet_df.to_csv(index=False),
    "outlet_allocation.csv",
    "text/csv",
)

e6.download_button(
    "🏷️ Competitor Pricing CSV",
    competitor_df.to_csv(index=False),
    "competitor_pricing.csv",
    "text/csv",
)

st.caption("Built with Streamlit • All values in South African Rand R")