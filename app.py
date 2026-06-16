"""
Pricing & Margin Model - Streamlit Web App
===========================================
Interactive calculator for a repackaging business that buys 5kg bags from a
supplier, receives promotional free stock, and resells smaller variants.

Run with:  streamlit run app.py
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
            background: #f0f2f6; border-radius: 8px 8px 0 0; padding: 10px 18px;
        }
        .stTabs [aria-selected="true"] {background: #1f77b4; color: white;}
    </style>
    """,
    unsafe_allow_html=True,
)

CURRENCY = "R"


def money(x: float) -> str:
    return f"{CURRENCY}{x:,.2f}"


# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Model Inputs")

st.sidebar.subheader("Supplier & Stock")
bag_cost = st.sidebar.number_input(
    "Bag cost from supplier (R / 5kg bag)",
    min_value=1.0, value=95.0, step=1.0,
    help="Base price you pay Peony Trading per 5kg bag.",
)

free_mode = st.sidebar.radio(
    "Free stock entry mode", ["Percentage", "X free per Y ordered"], horizontal=False
)
if free_mode == "Percentage":
    free_stock_pct = st.sidebar.number_input(
        "Free stock %", min_value=0.0, max_value=100.0, value=10.0, step=1.0,
        help="Percentage of paid bags received free as promotion.",
    )
else:
    c1, c2 = st.sidebar.columns(2)
    free_x = c1.number_input("Free bags", min_value=0, value=5, step=1)
    per_y = c2.number_input("Per ordered", min_value=1, value=50, step=1)
    free_stock_pct = (free_x / per_y) * 100.0
    st.sidebar.caption(f"➡️ Effective free stock: **{free_stock_pct:.1f}%**")

st.sidebar.subheader("Order & Budget")
budget = st.sidebar.number_input(
    "Budget (R)", min_value=0.0, value=5000.0, step=100.0,
    help="Total cash available for the first order.",
)
order_qty_bags = st.sidebar.number_input(
    "Order quantity (paid bags)", min_value=1, value=50, step=1,
)

st.sidebar.subheader("Selling Prices & Packaging")
variants = logic.default_variants()
for v in variants:
    with st.sidebar.expander(v.name, expanded=False):
        v.sell_price = st.number_input(
            f"Sell price (R) — {v.name}", min_value=0.0,
            value=float(v.sell_price), step=0.5, key=f"sell_{v.name}",
        )
        if v.name != "5kg Bulk":
            v.packaging_cost = st.number_input(
                f"Packaging cost (R) — {v.name}", min_value=0.0,
                value=float(v.packaging_cost), step=0.1, key=f"pkg_{v.name}",
            )

st.sidebar.subheader("First Order Mix (%)")
mix_weights = {}
default_mix = {
    "100g Mini Sachet": 30, "200g Sachet": 25, "500g Pack": 20,
    "1kg Pack": 15, "2kg Pack": 7, "5kg Bulk": 3,
}
for v in variants:
    mix_weights[v.name] = st.sidebar.slider(
        v.name, 0, 100, default_mix.get(v.name, 0), key=f"mix_{v.name}"
    )

# ---------------------------------------------------------------------------
# Computations
# ---------------------------------------------------------------------------

ue_df = logic.unit_economics(variants, bag_cost, free_stock_pct)
order = logic.first_order_mix(
    variants, bag_cost, free_stock_pct, budget, order_qty_bags, mix_weights
)
order_df = order["table"]
summ = order["summary"]
total_units = int(order_df["Units"].sum())
plan_df = logic.weekly_sales_plan(
    total_units, summ["total_revenue"], summ["total_profit"]
)

eff_cpg = logic.cost_per_gram(bag_cost, free_stock_pct)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def build_excel() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        ue_df.to_excel(writer, sheet_name="Unit Economics", index=False)
        order_df.to_excel(writer, sheet_name="First Order Mix", index=False)
        pd.DataFrame([summ]).to_excel(writer, sheet_name="Order Summary", index=False)
        plan_df.to_excel(writer, sheet_name="5-Week Plan", index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Header & KPIs
# ---------------------------------------------------------------------------

st.title("💰 Peony Washing Powder Pricing & Margin Model")
st.caption(
    "Buy 5kg bags • receive promotional free stock • repackage into retail "
    "variants • track margins, cash turnover and a 5-week plan."
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Effective Bag Cost", money(summ["effective_bag_cost"]),
          delta=money(summ["effective_bag_cost"] - bag_cost))
k2.metric("Cost / gram", money(eff_cpg))
k3.metric("Investment", money(summ["investment"]))
k4.metric("Projected Profit", money(summ["total_profit"]))
k5.metric("ROI", f"{summ['roi_pct']:.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(
    ["📊 Unit Economics", "📦 First Order Mix", "📅 5-Week Sales Plan"]
)

with tab1:
    st.subheader("Cost Breakdown & Margins per Variant")
    st.dataframe(
        ue_df.style.format({
            "Product Cost (R)": "{:.2f}", "Packaging Cost (R)": "{:.2f}",
            "Total Cost (R)": "{:.2f}", "Sell Price (R)": "{:.2f}",
            "Profit / Unit (R)": "{:.2f}", "Margin %": "{:.1f}",
            "Markup %": "{:.1f}",
        }).background_gradient(subset=["Margin %"], cmap="Greens"),
        use_container_width=True, hide_index=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            ue_df, x="Variant", y="Profit / Unit (R)", color="Margin %",
            color_continuous_scale="Tealgrn", title="Profit per Unit by Variant",
            text="Profit / Unit (R)",
        )
        fig.update_traces(texttemplate="R%{text:.2f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = go.Figure()
        fig2.add_bar(name="Total Cost", x=ue_df["Variant"], y=ue_df["Total Cost (R)"])
        fig2.add_bar(name="Profit", x=ue_df["Variant"], y=ue_df["Profit / Unit (R)"])
        fig2.update_layout(barmode="stack", title="Cost vs Profit (Sell Price)")
        st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.line(
        ue_df, x="Variant", y="Margin %", markers=True,
        title="Margin % Comparison", range_y=[0, 100],
    )
    st.plotly_chart(fig3, use_container_width=True)

with tab2:
    st.subheader("Recommended First Order Mix")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Paid Bags", f"{summ['paid_bags']}")
    s2.metric("Free Bags", f"{summ['free_bags']}")
    s3.metric("Total Revenue", money(summ["total_revenue"]))
    s4.metric("Total Profit", money(summ["total_profit"]))

    if summ["paid_bags"] < order_qty_bags:
        st.warning(
            f"Budget of {money(budget)} only covers {summ['paid_bags']} bags "
            f"(you requested {order_qty_bags})."
        )

    st.dataframe(
        order_df.style.format({
            "Mix %": "{:.1f}", "Revenue (R)": "{:.2f}",
            "Cost (R)": "{:.2f}", "Profit (R)": "{:.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        fig = px.pie(
            order_df[order_df["Units"] > 0], names="Variant", values="Units",
            title="Unit Distribution", hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(
            order_df, x="Variant", y=["Cost (R)", "Profit (R)"],
            title="Revenue Composition (Cost + Profit)", barmode="stack",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.info(
        f"Grams available: **{summ['grams_available']:,} g** • "
        f"Grams used: **{summ['grams_used']:,} g** • "
        f"Utilisation: **{(summ['grams_used']/summ['grams_available']*100) if summ['grams_available'] else 0:.1f}%**"
    )

with tab3:
    st.subheader("5-Week Sales Target Plan")
    st.dataframe(
        plan_df.style.format({
            "Revenue (R)": "{:.2f}", "Profit (R)": "{:.2f}",
            "Cumulative Revenue (R)": "{:.2f}", "Cumulative Profit (R)": "{:.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            plan_df, x="Week", y="Revenue (R)", title="Weekly Revenue Target",
            text="Revenue (R)", color="Revenue (R)", color_continuous_scale="Blues",
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure()
        fig.add_scatter(x=plan_df["Week"], y=plan_df["Cumulative Profit (R)"],
                        mode="lines+markers", name="Cumulative Profit", fill="tozeroy")
        fig.add_scatter(x=plan_df["Week"], y=plan_df["Cumulative Revenue (R)"],
                        mode="lines+markers", name="Cumulative Revenue")
        fig.update_layout(title="Cumulative Profit & Revenue Progression")
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

st.divider()
st.subheader("⬇️ Export Calculations")
e1, e2, e3, e4 = st.columns(4)
e1.download_button("📗 Excel (all sheets)", build_excel(),
                   "pricing_margin_model.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
e2.download_button("📄 Unit Economics CSV", ue_df.to_csv(index=False),
                   "unit_economics.csv", "text/csv")
e3.download_button("📄 First Order Mix CSV", order_df.to_csv(index=False),
                   "first_order_mix.csv", "text/csv")
e4.download_button("📄 5-Week Plan CSV", plan_df.to_csv(index=False),
                   "weekly_plan.csv", "text/csv")

st.caption("Built with Streamlit • All values in South African Rand (R)")
