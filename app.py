import streamlit as st
import pandas as pd
import plotly.express as px
from utils.bq_client import run_query, TABLES

st.set_page_config(page_title="Revel City - Rehab Costs", layout="wide")
st.title("Revel City Rehab Cost Dashboard")

# ---------- Load data ----------
TABLE = TABLES["am_rehab_costs"]

@st.cache_data(ttl=300)
def load_data():
    query = f"""
        SELECT
            property_address,
            property_walker,
            date_visited,
            above_grade_sqft,
            basement_sqft,
            renovation_level,
            bedroom_num,
            bathroom_num,
            list_price_arv,
            purchase_price,
            holding_days,
            cost_type,
            cost_category,
            area,
            SAFE_CAST(amount AS FLOAT64) AS amount
        FROM `{TABLE}`
        ORDER BY property_address, cost_category, area
    """
    return run_query(query)

df = load_data()

if df.empty:
    st.warning("No data found in AMRehabCalcCosts.")
    st.stop()

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")

properties = sorted(df["property_address"].dropna().unique())
selected_property = st.sidebar.selectbox("Property", ["All"] + properties)

if selected_property != "All":
    df = df[df["property_address"] == selected_property]

walkers = sorted(df["property_walker"].dropna().unique())
selected_walker = st.sidebar.selectbox("Walker", ["All"] + list(walkers))

if selected_walker != "All":
    df = df[df["property_walker"] == selected_walker]

# ---------- Property info header ----------
if selected_property != "All":
    row = df.iloc[0]
    cols = st.columns(6)
    cols[0].metric("Walker", row.get("property_walker", "—"))
    cols[1].metric("Date Visited", str(row.get("date_visited", "—")))
    cols[2].metric("Above Grade SqFt", row.get("above_grade_sqft", "—"))
    cols[3].metric("Basement SqFt", row.get("basement_sqft") or "—")
    cols[4].metric("Bedrooms", row.get("bedroom_num", "—"))
    cols[5].metric("Bathrooms", row.get("bathroom_num", "—"))

    cols2 = st.columns(3)
    arv = row.get("list_price_arv")
    purchase = row.get("purchase_price")
    renovation = row.get("renovation_level") or "—"
    cols2[0].metric("List Price / ARV", f"${arv:,.0f}" if pd.notna(arv) else "—")
    cols2[1].metric("Purchase Price", f"${purchase:,.0f}" if pd.notna(purchase) else "—")
    cols2[2].metric("Renovation Level", renovation)

# ---------- Summary KPIs ----------
st.markdown("---")

total_cost = df["amount"].sum()
num_properties = df["property_address"].nunique()
num_line_items = len(df)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Total Estimated Cost", f"${total_cost:,.2f}")
kpi2.metric("Properties", num_properties)
kpi3.metric("Line Items", num_line_items)

# ---------- Cost by category ----------
st.markdown("---")
st.subheader("Cost by Category")

cat_totals = (
    df.groupby("cost_category", dropna=False)["amount"]
    .sum()
    .reset_index()
    .sort_values("amount", ascending=False)
)

fig_cat = px.bar(
    cat_totals,
    x="cost_category",
    y="amount",
    labels={"cost_category": "Category", "amount": "Amount ($)"},
    text_auto="$,.0f",
)
fig_cat.update_layout(xaxis_tickangle=-45, showlegend=False)
st.plotly_chart(fig_cat, use_container_width=True)

# ---------- Cost breakdown table ----------
st.subheader("Cost Breakdown")

display_df = (
    df[["property_address", "cost_category", "area", "amount"]]
    .copy()
    .rename(columns={
        "property_address": "Property",
        "cost_category": "Category",
        "area": "Line Item",
        "amount": "Amount",
    })
)
display_df["Amount"] = display_df["Amount"].apply(
    lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00"
)

st.dataframe(display_df, use_container_width=True, hide_index=True)

# ---------- Cost by property (multi-property view) ----------
if selected_property == "All" and num_properties > 1:
    st.markdown("---")
    st.subheader("Total Cost by Property")

    prop_totals = (
        df.groupby("property_address", dropna=False)["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )

    fig_prop = px.bar(
        prop_totals,
        x="property_address",
        y="amount",
        labels={"property_address": "Property", "amount": "Total Cost ($)"},
        text_auto="$,.0f",
    )
    fig_prop.update_layout(xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig_prop, use_container_width=True)
