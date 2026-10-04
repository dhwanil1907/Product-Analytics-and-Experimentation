"""
E-Commerce Product Analytics Dashboard
Run with: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Allow `from queries import ...` when run from project root or dashboard/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries as q

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="E-Commerce Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Colour palette (consistent across all charts)
# ---------------------------------------------------------------------------

PALETTE = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]
BAND_LABELS = {
    "under_50": "< $50",
    "50_to_200": "$50–$200",
    "200_to_500": "$200–$500",
    "over_500": "> $500",
}
BAND_ORDER = ["under_50", "50_to_200", "200_to_500", "over_500"]
DOW_LABELS = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_how, tab_funnel, tab_cohorts, tab_retention, tab_revenue = st.tabs(
    ["📈 Overview", "⚙️ How It Works", "🔽 Funnel", "📅 Cohorts", "🔁 Retention", "💰 Revenue"]
)


# ===========================================================================
# TAB 1 — OVERVIEW
# ===========================================================================

with tab_overview:
    st.title("E-Commerce Product Analytics")
    st.caption("Kaggle dataset · Sep 2020 – Feb 2021 · 885K events · PostgreSQL + Python")

    ov = q.get_overview().iloc[0]
    funnel = q.get_funnel_overall().iloc[0]

    st.markdown("### Key Metrics")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Users", f"{int(ov['total_users']):,}")
    c2.metric("Buyers", f"{int(ov['buyers']):,}")
    c3.metric("Total Revenue", f"${float(ov['total_revenue']):,.0f}")
    c4.metric("Events (clean)", f"{int(ov['total_events']):,}")
    c5.metric("Sessions", f"{int(ov['total_sessions']):,}")
    c6.metric("Products", f"{int(ov['products']):,}")

    st.divider()
    st.markdown("### Conversion Funnel at a Glance")
    ca, cb, cc, cd = st.columns(4)
    ca.metric("View → Cart", f"{float(funnel['view_to_cart_pct'])}%")
    cb.metric("Cart → Purchase", f"{float(funnel['cart_to_purchase_pct'])}%")
    cc.metric("Overall CVR (Conversion Rate)", f"{float(funnel['overall_conversion_pct'])}%")
    cd.metric("Unique Buyers", f"{int(funnel['purchasers']):,}")

    st.divider()
    st.markdown("### Key Insight")
    st.info(
        "**The leakage is at browse-to-cart, not cart-to-checkout.** "
        "57.7% of users who add to cart convert — that's strong. "
        "But 90.9% of viewers never add anything to cart. "
        "The $200–$500 band has the highest browse intent (14.3% view→cart) "
        "yet the lowest cart-close rate (49.7%), pointing to price friction as the barrier."
    )


# ===========================================================================
# TAB 2 — HOW IT WORKS
# ===========================================================================

with tab_how:
    st.title("How This Project Works")
    st.markdown(
        "A full analytics pipeline — from raw CSV data to an interactive dashboard. "
        "Here is how all the pieces connect."
    )

    st.markdown("### Pipeline")
    st.graphviz_chart(
        """
        digraph pipeline {
            rankdir=LR;
            node [fontname="Arial", fontsize=12, style=filled, shape=box, margin="0.3,0.1"]
            edge [fontname="Arial", fontsize=10, color="#64748B"]

            CSV    [label="events.csv\\n885K rows",           fillcolor="#DCFCE7", color="#16A34A"]
            LOAD   [label="etl/load.py\\nLoad raw events",    fillcolor="#DBEAFE", color="#2563EB"]
            RAW    [label="raw_events\\n(Postgres)",           fillcolor="#EDE9FE", color="#7C3AED"]
            PROF   [label="etl/profile.py\\nData quality",    fillcolor="#FEF9C3", color="#CA8A04"]
            BUILD  [label="etl/build_dims.py\\nDedupe + star schema", fillcolor="#DBEAFE", color="#2563EB"]
            DIM_U  [label="dim_users\\n407K rows",             fillcolor="#EDE9FE", color="#7C3AED"]
            DIM_P  [label="dim_products\\n53K rows",           fillcolor="#EDE9FE", color="#7C3AED"]
            FCT_S  [label="fct_sessions\\n490K rows",          fillcolor="#EDE9FE", color="#7C3AED"]
            FCT_E  [label="fct_events\\n884K rows",            fillcolor="#EDE9FE", color="#7C3AED"]
            SQL    [label="SQL Analysis\\n02–05_*.sql",        fillcolor="#FEE2E2", color="#DC2626"]
            DASH   [label="Streamlit\\nDashboard",             fillcolor="#DCFCE7", color="#16A34A"]

            CSV   -> LOAD
            LOAD  -> RAW
            RAW   -> PROF  [style=dashed, label="  audit only"]
            RAW   -> BUILD
            BUILD -> DIM_U
            BUILD -> DIM_P
            BUILD -> FCT_S
            BUILD -> FCT_E
            DIM_U -> SQL
            DIM_P -> SQL
            FCT_S -> SQL
            FCT_E -> SQL
            SQL   -> DASH
        }
        """,
        use_container_width=True,
    )

    st.divider()
    st.markdown("### Star Schema — How the Database Tables Connect")
    st.graphviz_chart(
        """
        digraph schema {
            rankdir=TB;
            node [fontname="Arial", fontsize=11, style=filled, shape=record, margin="0.2,0.1"]
            edge [fontname="Arial", fontsize=10, color="#64748B"]

            fct_events [
                label="{fct_events | event_time\\l event_type\\l product_id FK\\l user_id FK\\l user_session FK\\l price\\l}",
                fillcolor="#EDE9FE", color="#7C3AED"
            ]
            dim_users [
                label="{dim_users | user_id PK\\l first_seen\\l first_purchase\\l cohort_week\\l}",
                fillcolor="#DBEAFE", color="#2563EB"
            ]
            dim_products [
                label="{dim_products | product_id PK\\l brand\\l category\\l price_band\\l}",
                fillcolor="#DBEAFE", color="#2563EB"
            ]
            fct_sessions [
                label="{fct_sessions | session_id PK\\l user_id FK\\l session_start\\l session_duration\\l event_count\\l converted\\l}",
                fillcolor="#FEF9C3", color="#CA8A04"
            ]

            fct_events -> dim_users     [label=" user_id"]
            fct_events -> dim_products  [label=" product_id"]
            fct_events -> fct_sessions  [label=" user_session"]
            fct_sessions -> dim_users   [label=" user_id"]
        }
        """,
        use_container_width=True,
    )

    st.divider()
    st.markdown("### Step-by-Step — click each step to expand")
    steps = [
        ("1. Ingest", "etl/load.py",
         "Reads `data/events.csv` (885K rows) and bulk-inserts into `raw_events` without any cleaning. "
         "Goal: land data as-is before touching it."),
        ("2. Profile", "etl/profile.py",
         "Runs 7 automated checks: null counts per column, exact duplicates, near-duplicates within 1 second, "
         "sessions spanning midnight, price anomalies (zero / negative), event type distribution, date range."),
        ("3. Build Star Schema", "etl/build_dims.py",
         "Deduplicates 837 extra rows, then builds `dim_users` (407K), `dim_products` (53K), "
         "`fct_sessions` (490K), and the analysis-ready `fct_events` (884K)."),
        ("4. Analyse", "sql/02–05_*.sql",
         "Four SQL files: **02** funnel by price band / brand / day of week · "
         "**03** weekly cohort D7/D30/D60 · **04** repeat purchase rates · "
         "**05** ARPU / AOV / Pareto revenue quintiles."),
        ("5. Visualise", "dashboard/app.py",
         "This Streamlit app — queries the star schema live and renders everything as interactive charts."),
    ]
    for title, file, desc in steps:
        with st.expander(f"**{title}** — `{file}`"):
            st.markdown(desc)


# ===========================================================================
# TAB 3 — FUNNEL
# ===========================================================================

with tab_funnel:
    st.title("Conversion Funnel")

    st.markdown("### Overall: View → Cart → Purchase")
    row = q.get_funnel_overall().iloc[0]

    fig_f = go.Figure(go.Funnel(
        y=["Viewed a product", "Added to cart", "Purchased"],
        x=[row["viewers"], row["cart_adders"], row["purchasers"]],
        textinfo="value+percent initial",
        marker=dict(color=["#6366F1", "#10B981", "#F59E0B"]),
        connector=dict(line=dict(color="#CBD5E1", width=1)),
    ))
    fig_f.update_layout(margin=dict(t=20, b=20), height=300)
    st.plotly_chart(fig_f, use_container_width=True)

    st.divider()
    st.markdown("### By Price Band")

    band_df = q.get_funnel_by_price_band().copy()
    band_df["label"] = band_df["price_band"].map(BAND_LABELS).fillna(band_df["price_band"])
    band_df["label"] = pd.Categorical(
        band_df["label"],
        categories=[BAND_LABELS[b] for b in BAND_ORDER if b in band_df["price_band"].values],
        ordered=True,
    )
    band_df = band_df.sort_values("label")

    col1, col2 = st.columns(2)
    with col1:
        fig_vc = px.bar(
            band_df, x="label", y="view_to_cart_pct",
            title="View → Cart %",
            labels={"label": "Price Band", "view_to_cart_pct": "Rate (%)"},
            color="label", color_discrete_sequence=PALETTE, text="view_to_cart_pct",
        )
        fig_vc.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_vc.update_layout(showlegend=False, height=340)
        st.plotly_chart(fig_vc, use_container_width=True)

    with col2:
        fig_cp = px.bar(
            band_df, x="label", y="cart_to_purchase_pct",
            title="Cart → Purchase %",
            labels={"label": "Price Band", "cart_to_purchase_pct": "Rate (%)"},
            color="label", color_discrete_sequence=PALETTE, text="cart_to_purchase_pct",
        )
        fig_cp.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_cp.update_layout(showlegend=False, height=340)
        st.plotly_chart(fig_cp, use_container_width=True)

    st.caption(
        "The $200–$500 band attracts the most intentional browsers (highest view→cart rate) "
        "but closes at the lowest rate — price friction is the likely barrier."
    )

    st.divider()
    st.markdown("### By Day of Week")
    dow_df = q.get_funnel_by_dow().copy()
    dow_df["day"] = dow_df["dow"].map(DOW_LABELS)
    dow_df["day"] = pd.Categorical(dow_df["day"], categories=list(DOW_LABELS.values()), ordered=True)
    dow_df = dow_df.sort_values("day")

    fig_dow = px.line(
        dow_df, x="day", y="view_to_purchase_pct", markers=True,
        labels={"day": "Day of Week", "view_to_purchase_pct": "View → Purchase (%)"},
        color_discrete_sequence=["#6366F1"],
    )
    fig_dow.update_layout(height=300)
    st.plotly_chart(fig_dow, use_container_width=True)
    st.caption("Midweek (Tue–Thu) converts ~0.3 percentage points better than weekends.")


# ===========================================================================
# TAB 4 — COHORTS
# ===========================================================================

with tab_cohorts:
    st.title("Weekly Cohort Retention")
    st.markdown(
        "Each cohort = users who first appeared in a given week. "
        "Retention = share who made a **purchase** within D7 / D30 / D60 of first appearance."
    )

    cohorts_df = q.get_cohorts().copy()
    cohorts_df["cohort_week"] = pd.to_datetime(cohorts_df["cohort_week"]).dt.strftime("%Y-%m-%d")

    st.markdown("### Retention Heatmap")
    heat_df = cohorts_df.rename(columns={
        "d7_rate_pct": "7-Day", "d30_rate_pct": "30-Day", "d60_rate_pct": "60-Day"
    }).set_index("cohort_week")[["7-Day", "30-Day", "60-Day"]].T

    fig_heat = px.imshow(
        heat_df,
        color_continuous_scale="Blues",
        labels=dict(x="Cohort Week", y="Window", color="Rate (%)"),
        aspect="auto",
        text_auto=".2f",
    )
    fig_heat.update_layout(height=260)
    st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()
    st.markdown("### Full Table")
    display_df = cohorts_df[[
        "cohort_week", "cohort_size",
        "returned_d7", "d7_rate_pct",
        "returned_d30", "d30_rate_pct",
        "returned_d60", "d60_rate_pct",
    ]].rename(columns={
        "cohort_week": "Cohort Week", "cohort_size": "Size",
        "returned_d7": "Back in 7d", "d7_rate_pct": "7-Day %",
        "returned_d30": "Back in 30d", "d30_rate_pct": "30-Day %",
        "returned_d60": "Back in 60d", "d60_rate_pct": "60-Day %",
    })
    st.dataframe(
        display_df.style.background_gradient(subset=["7-Day %", "30-Day %", "60-Day %"], cmap="Blues"),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "All cohorts fully observable through D60. "
        "Absolute rates < 1.5% — typical for a broad catalogue with no loyalty programme."
    )


# ===========================================================================
# TAB 5 — RETENTION
# ===========================================================================

with tab_retention:
    st.title("Retention & Repeat Purchase")

    activity = q.get_buyer_activity().iloc[0]

    st.markdown("### Buyer Activity After First Purchase")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("First-Time Buyers", f"{int(activity['first_time_buyers']):,}")
    c2.metric("Active within 7 Days", f"{float(activity['active_d7_pct'])}%")
    c3.metric("Active within 30 Days", f"{float(activity['active_d30_pct'])}%")
    c4.metric("Active within 60 Days", f"{float(activity['active_d60_pct'])}%")

    st.divider()
    st.markdown("### Repeat Purchase Rate by First-Purchase Price Band")

    repeat_df = q.get_repeat_rates().copy()
    repeat_df["label"] = repeat_df["first_purchase_band"].map(BAND_LABELS).fillna(
        repeat_df["first_purchase_band"]
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        fig_r = px.bar(
            repeat_df, x="label", y="repeat_rate_pct",
            color="label", color_discrete_sequence=PALETTE,
            labels={"label": "First Purchase Band", "repeat_rate_pct": "Repeat Rate (%)"},
            text="repeat_rate_pct",
        )
        fig_r.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_r.update_layout(showlegend=False, height=360, yaxis=dict(range=[0, 45]))
        st.plotly_chart(fig_r, use_container_width=True)

    with col2:
        st.dataframe(
            repeat_df[["label", "first_time_buyers", "returned_buyers", "repeat_rate_pct"]].rename(
                columns={
                    "label": "Band", "first_time_buyers": "1st-time",
                    "returned_buyers": "Returned", "repeat_rate_pct": "Rate %",
                }
            ),
            use_container_width=True, hide_index=True,
        )

    st.caption(
        "Mid-price first buyers ($50–$500) return at 36–37%. "
        "Bargain buyers (< $50) have the lowest repeat rate at 31.4%."
    )


# ===========================================================================
# TAB 6 — REVENUE
# ===========================================================================

with tab_revenue:
    st.title("Revenue Segmentation")

    st.markdown("### ARPU & AOV by Price Band")
    st.caption("ARPU = Average Revenue per User (total spend ÷ buyers) · AOV = Average Order Value (total spend ÷ orders)")
    arpu_df = q.get_arpu_by_band().copy()
    arpu_df["label"] = arpu_df["price_band"].map(BAND_LABELS).fillna(arpu_df["price_band"])

    col1, col2 = st.columns(2)
    with col1:
        fig_arpu = px.bar(
            arpu_df, x="label", y="arpu", title="ARPU — Avg. Revenue per User",
            color="label", color_discrete_sequence=PALETTE,
            labels={"label": "Price Band", "arpu": "ARPU ($)"}, text="arpu",
        )
        fig_arpu.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig_arpu.update_layout(showlegend=False, height=340)
        st.plotly_chart(fig_arpu, use_container_width=True)

    with col2:
        fig_aov = px.bar(
            arpu_df, x="label", y="aov", title="AOV — Avg. Order Value",
            color="label", color_discrete_sequence=PALETTE,
            labels={"label": "Price Band", "aov": "AOV ($)"}, text="aov",
        )
        fig_aov.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig_aov.update_layout(showlegend=False, height=340)
        st.plotly_chart(fig_aov, use_container_width=True)

    st.divider()
    st.markdown("### Avg. Revenue per User by Product Category")
    cat_df = q.get_arpu_by_category().copy()
    cat_df = cat_df[cat_df["category"] != "(no category)"].head(10)

    fig_cat = px.bar(
        cat_df.sort_values("arpu", ascending=True),
        x="arpu", y="category", orientation="h",
        color="total_revenue", color_continuous_scale="Blues",
        labels={"arpu": "ARPU ($)", "category": "Category", "total_revenue": "Revenue ($)"},
        text="arpu",
    )
    fig_cat.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
    fig_cat.update_layout(height=380)
    st.plotly_chart(fig_cat, use_container_width=True)

    st.divider()
    st.markdown("### Revenue Concentration — Who Drives the Most Spend?")
    quint_df = q.get_quintiles().copy()
    quint_df["label"] = quint_df["quintile"].map({
        1: "Top 20%", 2: "2nd 20%", 3: "3rd 20%", 4: "4th 20%", 5: "Bottom 20%"
    })

    col1, col2 = st.columns([1, 1])
    with col1:
        fig_pie = px.pie(
            quint_df, values="revenue", names="label",
            color_discrete_sequence=PALETTE, hole=0.45,
        )
        fig_pie.update_traces(textinfo="percent+label")
        fig_pie.update_layout(height=360, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.write("")
        st.write("")
        st.dataframe(
            quint_df[["label", "users", "revenue", "revenue_pct"]].rename(
                columns={
                    "label": "Segment", "users": "Users",
                    "revenue": "Revenue ($)", "revenue_pct": "Share %",
                }
            ),
            use_container_width=True, hide_index=True,
        )
        st.info("Top 20% of buyers drive **67.8%** of total revenue.")
