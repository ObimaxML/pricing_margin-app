""""
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

st.sidebar.subheader("Variable Costs")
transport_cost = st.sidebar.number_input(
    "Transport / collection cost (R per order)",
    min_value=0.0, value=150.0, step=10.0,
    help="Fuel, delivery, or collection cost for the entire order.",
)
other_variable_cost = st.sidebar.number_input(
    "Other variable costs (R per order)",
    min_value=0.0, value=0.0, step=10.0,
    help="Any other variable costs per order (e.g. labour, storage).",
)
total_variable_cost = transport_cost + other_variable_cost

st.sidebar.subheader("Payment Terms")
payment_term = st.sidebar.selectbox(
    "Supplier payment term",
    options=["Cash on Delivery", "7-Day", "14-Day", "30-Day"],
    index=0,
    help="When payment to the supplier is due.",
)
TERM_DAYS = {"Cash on Delivery": 0, "7-Day": 7, "14-Day": 14, "30-Day": 30}
term_days = TERM_DAYS[payment_term]

customer_term = st.sidebar.selectbox(
    "Customer payment term (receivables)",
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
    variants, bag_cost, free_stock_pct, budget, order_qty_bags, mix_weights,
    variable_cost=total_variable_cost,
)
order_df = order["table"]
summ = order["summary"]
total_units = int(order_df["Units"].sum())
plan_df = logic.weekly_sales_plan(
    total_units, summ["total_revenue"], summ["total_profit"]
)

eff_cpg = logic.cost_per_gram(bag_cost, free_stock_pct)

# Cash-flow timing calculations
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
        pd.DataFrame([summ]).to_excel(writer, sheet_name="Order Summary", index=False)
        plan_df.to_excel(writer, sheet_name="5-Week Plan", index=False)
        pd.DataFrame([{
            "Supplier Term": payment_term,
            "Customer Term": customer_term,
            "Cash Gap (days)": days_cash_tied,
            "Transport Cost (R)": transport_cost,
            "Other Variable Cost (R)": other_variable_cost,
            "Total Variable Cost (R)": total_variable_cost,
            "Net Profit after Var. Costs (R)": round(summ["total_profit"] - total_variable_cost, 2),
            "Total Investment incl. Var. Costs (R)": round(summ["investment"] + total_variable_cost, 2),
        }]).to_excel(writer, sheet_name="Cash Flow & Terms", index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Header & KPIs
# ---------------------------------------------------------------------------

st.title("💰 Peony Washing Powder Pricing & Margin Model")
st.caption(
    "Buy 5kg bags • receive promotional free stock • repackage into retail "
    "variants • track margins, cash turnover and a 5-week plan."
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Effective Bag Cost", money(summ["effective_bag_cost"]),
          delta=money(summ["effective_bag_cost"] - bag_cost))
k2.metric("Cost / gram", money(eff_cpg))
k3.metric("Total Investment", money(summ["investment"] + total_variable_cost),
          help="Stock cost + transport + other variable costs")
k4.metric("Projected Profit", money(summ["total_profit"] - total_variable_cost))
k5.metric("ROI (after var. costs)",
          f"{((summ['total_profit'] - total_variable_cost) / (summ['investment'] + total_variable_cost) * 100) if (summ['investment'] + total_variable_cost) else 0:.1f}%")
k6.metric("Cash Gap (days)", f"{days_cash_tied}d",
          help="Days between paying supplier and receiving customer payment")

st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Unit Economics", "📦 First Order Mix", "📅 5-Week Sales Plan", "💳 Cash Flow & Terms"]
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

with tab4:
    st.subheader("💳 Cash Flow & Payment Terms Analysis")

    # Summary cards
    cf1, cf2, cf3, cf4 = st.columns(4)
    cf1.metric("Supplier Term", payment_term, help="Days before you must pay supplier")
    cf2.metric("Customer Term", customer_term, help="Days before customers pay you")
    cf3.metric("Cash Gap", f"{days_cash_tied} days",
               delta=f"{'-' if days_cash_tied == 0 else '+'}{days_cash_tied}d",
               delta_color="inverse")
    cf4.metric("Cash at Risk", money(cash_at_risk),
               help="Total outlay before any revenue is collected")

    st.divider()

    # Variable cost breakdown
    st.subheader("Variable Cost Breakdown")
    vc1, vc2, vc3 = st.columns(3)
    vc1.metric("Transport / Collection", money(transport_cost))
    vc2.metric("Other Variable Costs", money(other_variable_cost))
    vc3.metric("Total Variable Costs", money(total_variable_cost))

    net_profit_after_vc = summ["total_profit"] - total_variable_cost
    total_investment_with_vc = summ["investment"] + total_variable_cost
    roi_after_vc = (net_profit_after_vc / total_investment_with_vc * 100) if total_investment_with_vc else 0

    cost_breakdown_df = pd.DataFrame({
        "Cost Component": ["Stock Cost", "Transport / Collection", "Other Variable Costs", "Packaging (all variants)"],
        "Amount (R)": [
            summ["investment"],
            transport_cost,
            other_variable_cost,
            order_df["Cost (R)"].sum() - summ["investment"],
        ],
    })
    cost_breakdown_df = cost_breakdown_df[cost_breakdown_df["Amount (R)"] > 0]

    c1, c2 = st.columns(2)
    with c1:
        fig_vc = px.pie(
            cost_breakdown_df, names="Cost Component", values="Amount (R)",
            title="Total Cost Composition", hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig_vc, use_container_width=True)
    with c2:
        profit_waterfall = go.Figure(go.Waterfall(
            name="Profit Waterfall",
            orientation="v",
            measure=["absolute", "relative", "relative", "total"],
            x=["Revenue", "Stock Cost", "Variable Costs", "Net Profit"],
            y=[summ["total_revenue"], -summ["investment"], -total_variable_cost, 0],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            decreasing={"marker": {"color": "#EF553B"}},
            increasing={"marker": {"color": "#00CC96"}},
            totals={"marker": {"color": "#636EFA"}},
        ))
        profit_waterfall.update_layout(title="Revenue → Net Profit Waterfall")
        st.plotly_chart(profit_waterfall, use_container_width=True)

    st.divider()

    # Terms comparison table
    st.subheader("Payment Terms Scenario Comparison")
    scenarios = []
    for sup_term, sup_days in TERM_DAYS.items():
        for cust_term, cust_days in TERM_DAYS.items():
            gap = max(0, cust_days - sup_days)
            scenarios.append({
                "Supplier Term": sup_term,
                "Customer Term": cust_term,
                "Cash Gap (days)": gap,
                "Cash at Risk (R)": cash_at_risk if gap > 0 else 0,
                "Net Profit (R)": round(net_profit_after_vc, 2),
                "ROI %": round(roi_after_vc, 1),
                "Favourable?": "✅ Yes" if gap == 0 else ("⚠️ Neutral" if gap <= 7 else "❌ No"),
            })
    scenarios_df = pd.DataFrame(scenarios)
    st.dataframe(
        scenarios_df.style.map(
            lambda v: "color: green" if v == "✅ Yes" else ("color: orange" if v == "⚠️ Neutral" else "color: red"),
            subset=["Favourable?"]
        ),
        use_container_width=True, hide_index=True,
    )

    st.info(
        f"**Current scenario:** Supplier = **{payment_term}** | Customer = **{customer_term}** | "
        f"Cash gap = **{days_cash_tied} days** | Net profit after variable costs = **{money(net_profit_after_vc)}** | "
        f"ROI = **{roi_after_vc:.1f}%**"
    )

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
