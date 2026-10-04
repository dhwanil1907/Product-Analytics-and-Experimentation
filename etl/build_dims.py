"""Derive dim_*, fct_sessions, and fct_events from raw_events."""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "sql" / "01_schema.sql"

# Run in order: parents before children because of foreign keys.
SQL_STEPS: list[tuple[str, str]] = [
    (
        "dim_users",
        """
        INSERT INTO dim_users (user_id, first_seen, first_purchase, cohort_week)
        SELECT
            user_id,
            MIN(event_time) AS first_seen,
            MIN(event_time) FILTER (WHERE event_type = 'purchase') AS first_purchase,
            DATE_TRUNC('week', MIN(event_time))::date AS cohort_week
        FROM raw_events
        GROUP BY user_id
        """,
    ),
    (
        "dim_products",
        """
        INSERT INTO dim_products (product_id, brand, category, price_band)
        SELECT
            product_id,
            brand,
            NULLIF(SPLIT_PART(category_code, '.', 1), '') AS category,
            CASE
                WHEN price < 50 THEN 'under_50'
                WHEN price < 200 THEN '50_to_200'
                WHEN price < 500 THEN '200_to_500'
                ELSE 'over_500'
            END AS price_band
        FROM (
            SELECT DISTINCT ON (product_id)
                product_id,
                brand,
                category_code,
                price
            FROM raw_events
            WHERE price > 0
            ORDER BY product_id, event_time DESC
        ) latest_positive_price
        """,
    ),
    (
        "fct_sessions",
        """
        INSERT INTO fct_sessions (
            session_id,
            user_id,
            session_start,
            session_duration,
            event_count,
            converted
        )
        SELECT
            user_session AS session_id,
            MIN(user_id) AS user_id,
            MIN(event_time) AS session_start,
            MAX(event_time) - MIN(event_time) AS session_duration,
            COUNT(*)::integer AS event_count,
            BOOL_OR(event_type = 'purchase') AS converted
        FROM raw_events
        WHERE user_session IS NOT NULL
        GROUP BY user_session
        """,
    ),
    (
        "fct_events",
        """
        INSERT INTO fct_events (
            event_time,
            event_type,
            product_id,
            category_id,
            category_code,
            brand,
            price,
            user_id,
            user_session
        )
        SELECT
            d.event_time,
            d.event_type,
            d.product_id,
            d.category_id,
            d.category_code,
            d.brand,
            d.price,
            d.user_id,
            d.user_session
        FROM (
            SELECT DISTINCT ON (
                user_id,
                product_id,
                event_type,
                date_trunc('second', event_time)
            )
                event_time,
                event_type,
                product_id,
                category_id,
                category_code,
                brand,
                price,
                user_id,
                user_session
            FROM raw_events
            WHERE user_session IS NOT NULL
            ORDER BY
                user_id,
                product_id,
                event_type,
                date_trunc('second', event_time),
                event_time
        ) d
        INNER JOIN dim_products p ON p.product_id = d.product_id
        INNER JOIN dim_users u ON u.user_id = d.user_id
        INNER JOIN fct_sessions s ON s.session_id = d.user_session
        """,
    ),
]


def run_sql_file(conn, path: Path) -> None:
    """Execute a .sql file as one script (psql-style)."""
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def run_build(db_url: str) -> None:
    """Recreate derived tables and reload them from raw_events."""
    if not SCHEMA_SQL.is_file():
        sys.exit(f"Missing {SCHEMA_SQL}. Add sql/01_schema.sql first.")

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw_events")
            row = cur.fetchone()
            if row is None or int(row[0]) == 0:
                sys.exit("raw_events is empty. Run etl/load.py first.")

        print(f"Running {SCHEMA_SQL.name} …")
        run_sql_file(conn, SCHEMA_SQL)
        conn.commit()

        for label, sql in SQL_STEPS:
            print(f"Loading {label} …")
            with conn.cursor() as cur:
                cur.execute(sql)
                print(f"  {cur.rowcount:,} rows")
            conn.commit()

        with conn.cursor() as cur:
            for table in ("dim_users", "dim_products", "fct_sessions", "fct_events"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()
                print(f"{table}: {int(count[0]):,} rows" if count else f"{table}: ?")


def main() -> None:
    load_dotenv(ROOT / ".env")
    db_url = os.getenv("DB_URL")
    if not db_url:
        sys.exit("DB_URL is missing. Add it to .env at the repo root.")
    run_build(db_url)


if __name__ == "__main__":
    main()
