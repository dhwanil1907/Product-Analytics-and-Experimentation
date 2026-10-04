"""
Data access layer for the Streamlit dashboard.
Queries the live Postgres DB when DB_URL is set; falls back to pre-exported
CSVs in dashboard/data/ when the DB is unavailable (e.g. Streamlit Cloud).
"""

import os
from pathlib import Path

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"

load_dotenv(ROOT / ".env")


def _conn():
    return psycopg2.connect(os.environ["DB_URL"])


def _run(sql: str) -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql(sql, conn)


def _load(name: str, sql: str) -> pd.DataFrame:
    """Try DB first, fall back to CSV."""
    if os.getenv("DB_URL"):
        try:
            return _run(sql)
        except Exception:
            pass
    csv_path = DATA_DIR / f"{name}.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise RuntimeError(
        f"DB_URL not set and no cached CSV at {csv_path}. "
        "Run: python dashboard/export_data.py"
    )


# ---------------------------------------------------------------------------
# Overview KPIs
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_overview() -> pd.DataFrame:
    return _load(
        "overview",
        """
        SELECT
            (SELECT COUNT(DISTINCT user_id) FROM fct_events)                      AS total_users,
            (SELECT COUNT(DISTINCT user_id) FROM fct_events
             WHERE event_type = 'purchase')                                        AS buyers,
            (SELECT ROUND(SUM(price)::numeric, 2) FROM fct_events
             WHERE event_type = 'purchase' AND price > 0)                         AS total_revenue,
            (SELECT COUNT(*) FROM fct_events)                                     AS total_events,
            (SELECT COUNT(*) FROM fct_sessions)                                   AS total_sessions,
            (SELECT COUNT(DISTINCT product_id) FROM fct_events)                  AS products
        """,
    )


# ---------------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_funnel_overall() -> pd.DataFrame:
    return _load(
        "funnel_overall",
        """
        WITH s AS (
            SELECT
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'view')     AS viewers,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'cart')     AS cart_adders,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'purchase') AS purchasers
            FROM fct_events
        )
        SELECT
            viewers, cart_adders, purchasers,
            ROUND(100.0 * cart_adders  / NULLIF(viewers, 0), 2)     AS view_to_cart_pct,
            ROUND(100.0 * purchasers   / NULLIF(cart_adders, 0), 2) AS cart_to_purchase_pct,
            ROUND(100.0 * purchasers   / NULLIF(viewers, 0), 2)     AS overall_conversion_pct
        FROM s
        """,
    )


@st.cache_data(ttl=3600)
def get_funnel_by_price_band() -> pd.DataFrame:
    return _load(
        "funnel_by_price_band",
        """
        WITH f AS (
            SELECT
                p.price_band,
                COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'view')     AS viewers,
                COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'cart')     AS cart_adders,
                COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'purchase') AS purchasers
            FROM fct_events e
            JOIN dim_products p ON p.product_id = e.product_id
            GROUP BY p.price_band
        )
        SELECT
            price_band, viewers, cart_adders, purchasers,
            ROUND(100.0 * cart_adders / NULLIF(viewers, 0), 2)     AS view_to_cart_pct,
            ROUND(100.0 * purchasers  / NULLIF(cart_adders, 0), 2) AS cart_to_purchase_pct
        FROM f
        ORDER BY viewers DESC
        """,
    )


@st.cache_data(ttl=3600)
def get_funnel_by_dow() -> pd.DataFrame:
    return _load(
        "funnel_by_dow",
        """
        WITH f AS (
            SELECT
                EXTRACT(DOW FROM event_time)::int                               AS dow,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'view')     AS viewers,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'cart')     AS cart_adders,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'purchase') AS purchasers
            FROM fct_events
            GROUP BY EXTRACT(DOW FROM event_time)
        )
        SELECT
            dow, viewers, cart_adders, purchasers,
            ROUND(100.0 * purchasers / NULLIF(viewers, 0), 2) AS view_to_purchase_pct
        FROM f
        ORDER BY dow
        """,
    )


# ---------------------------------------------------------------------------
# Cohorts
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_cohorts() -> pd.DataFrame:
    return _load(
        "cohorts",
        """
        WITH user_purchases AS (
            SELECT u.user_id, u.cohort_week, u.first_seen,
                   (e.event_time::date - u.first_seen::date) AS days_since_first
            FROM dim_users u
            JOIN fct_events e
                ON e.user_id = u.user_id
                AND e.event_type = 'purchase'
                AND e.event_time > u.first_seen
        ),
        cohort_sizes AS (
            SELECT cohort_week, COUNT(*) AS cohort_size
            FROM dim_users
            GROUP BY cohort_week
        ),
        cohort_returns AS (
            SELECT cohort_week,
                COUNT(DISTINCT user_id) FILTER (WHERE days_since_first BETWEEN 1 AND 7)  AS returned_d7,
                COUNT(DISTINCT user_id) FILTER (WHERE days_since_first BETWEEN 1 AND 30) AS returned_d30,
                COUNT(DISTINCT user_id) FILTER (WHERE days_since_first BETWEEN 1 AND 60) AS returned_d60
            FROM user_purchases
            GROUP BY cohort_week
        )
        SELECT
            cs.cohort_week,
            cs.cohort_size,
            COALESCE(cr.returned_d7,  0) AS returned_d7,
            COALESCE(cr.returned_d30, 0) AS returned_d30,
            COALESCE(cr.returned_d60, 0) AS returned_d60,
            ROUND(100.0 * COALESCE(cr.returned_d7,  0) / cs.cohort_size, 2) AS d7_rate_pct,
            ROUND(100.0 * COALESCE(cr.returned_d30, 0) / cs.cohort_size, 2) AS d30_rate_pct,
            ROUND(100.0 * COALESCE(cr.returned_d60, 0) / cs.cohort_size, 2) AS d60_rate_pct
        FROM cohort_sizes cs
        LEFT JOIN cohort_returns cr USING (cohort_week)
        ORDER BY cs.cohort_week
        """,
    )


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_repeat_rates() -> pd.DataFrame:
    return _load(
        "repeat_rates",
        """
        WITH first_purchase_events AS (
            SELECT u.user_id, u.first_purchase, p.price_band AS first_purchase_band
            FROM dim_users u
            JOIN fct_events e
                ON e.user_id = u.user_id
                AND e.event_type = 'purchase'
                AND e.event_time = u.first_purchase
                AND e.price > 0
            JOIN dim_products p ON p.product_id = e.product_id
            WHERE u.first_purchase IS NOT NULL
        ),
        second_purchase AS (
            SELECT DISTINCT fp.user_id
            FROM first_purchase_events fp
            JOIN fct_events e
                ON e.user_id = fp.user_id
                AND e.event_type = 'purchase'
                AND e.event_time > fp.first_purchase
        )
        SELECT
            fp.first_purchase_band,
            COUNT(DISTINCT fp.user_id)  AS first_time_buyers,
            COUNT(DISTINCT sp.user_id)  AS returned_buyers,
            ROUND(100.0 * COUNT(DISTINCT sp.user_id) / NULLIF(COUNT(DISTINCT fp.user_id), 0), 2) AS repeat_rate_pct
        FROM first_purchase_events fp
        LEFT JOIN second_purchase sp ON sp.user_id = fp.user_id
        GROUP BY fp.first_purchase_band
        ORDER BY repeat_rate_pct DESC
        """,
    )


@st.cache_data(ttl=3600)
def get_buyer_activity() -> pd.DataFrame:
    return _load(
        "buyer_activity",
        """
        WITH buyers AS (
            SELECT user_id, first_purchase
            FROM dim_users
            WHERE first_purchase IS NOT NULL
        ),
        activity AS (
            SELECT b.user_id,
                   MIN(e.event_time::date - b.first_purchase::date) AS days_to_return
            FROM buyers b
            JOIN fct_events e
                ON e.user_id = b.user_id
                AND e.event_time > b.first_purchase
            GROUP BY b.user_id
        )
        SELECT
            COUNT(*)                                                                              AS first_time_buyers,
            ROUND(100.0 * COUNT(*) FILTER (WHERE days_to_return BETWEEN 1 AND 7)  / NULLIF(COUNT(*), 0), 2) AS active_d7_pct,
            ROUND(100.0 * COUNT(*) FILTER (WHERE days_to_return BETWEEN 1 AND 30) / NULLIF(COUNT(*), 0), 2) AS active_d30_pct,
            ROUND(100.0 * COUNT(*) FILTER (WHERE days_to_return BETWEEN 1 AND 60) / NULLIF(COUNT(*), 0), 2) AS active_d60_pct
        FROM buyers b
        LEFT JOIN activity a ON a.user_id = b.user_id
        """,
    )


# ---------------------------------------------------------------------------
# Revenue segments
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def get_arpu_by_band() -> pd.DataFrame:
    return _load(
        "arpu_by_band",
        """
        SELECT
            p.price_band,
            COUNT(DISTINCT e.user_id)                                              AS buyers,
            ROUND(SUM(e.price), 2)                                                 AS total_revenue,
            ROUND(SUM(e.price) / NULLIF(COUNT(DISTINCT e.user_id), 0), 2)         AS arpu,
            ROUND(SUM(e.price) / NULLIF(COUNT(*), 0), 2)                          AS aov
        FROM fct_events e
        JOIN dim_products p ON p.product_id = e.product_id
        WHERE e.event_type = 'purchase' AND e.price > 0
        GROUP BY p.price_band
        ORDER BY arpu DESC
        """,
    )


@st.cache_data(ttl=3600)
def get_arpu_by_category() -> pd.DataFrame:
    return _load(
        "arpu_by_category",
        """
        SELECT
            COALESCE(p.category, '(no category)') AS category,
            COUNT(DISTINCT e.user_id)              AS buyers,
            ROUND(SUM(e.price), 2)                 AS total_revenue,
            ROUND(SUM(e.price) / NULLIF(COUNT(DISTINCT e.user_id), 0), 2) AS arpu
        FROM fct_events e
        JOIN dim_products p ON p.product_id = e.product_id
        WHERE e.event_type = 'purchase' AND e.price > 0
        GROUP BY COALESCE(p.category, '(no category)')
        ORDER BY total_revenue DESC
        """,
    )


@st.cache_data(ttl=3600)
def get_quintiles() -> pd.DataFrame:
    return _load(
        "quintiles",
        """
        WITH user_revenue AS (
            SELECT user_id, SUM(price) AS total_spend
            FROM fct_events
            WHERE event_type = 'purchase' AND price > 0
            GROUP BY user_id
        ),
        ranked AS (
            SELECT user_id, total_spend,
                   NTILE(5) OVER (ORDER BY total_spend DESC) AS quintile
            FROM user_revenue
        )
        SELECT
            quintile,
            COUNT(*) AS users,
            ROUND(SUM(total_spend), 2) AS revenue,
            ROUND(100.0 * SUM(total_spend) / SUM(SUM(total_spend)) OVER (), 2) AS revenue_pct
        FROM ranked
        GROUP BY quintile
        ORDER BY quintile
        """,
    )
