"""Print a data-quality report for raw_events. Does not modify any rows."""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

# Each check is (title, SQL). SQL must return one row the script can print.
CHECKS: list[tuple[str, str]] = [
    (
        "1. Null counts per column",
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) - COUNT(event_time) AS null_event_time,
            COUNT(*) - COUNT(event_type) AS null_event_type,
            COUNT(*) - COUNT(product_id) AS null_product_id,
            COUNT(*) - COUNT(category_id) AS null_category_id,
            COUNT(*) - COUNT(category_code) AS null_category_code,
            COUNT(*) - COUNT(brand) AS null_brand,
            COUNT(*) - COUNT(price) AS null_price,
            COUNT(*) - COUNT(user_id) AS null_user_id,
            COUNT(*) - COUNT(user_session) AS null_user_session
        FROM raw_events
        """,
    ),
    (
        "2. Exact duplicate events (same user, product, type, timestamp)",
        """
        WITH dup_groups AS (
            SELECT user_id, product_id, event_type, event_time, COUNT(*) AS n
            FROM raw_events
            GROUP BY 1, 2, 3, 4
            HAVING COUNT(*) > 1
        )
        SELECT
            COALESCE(SUM(n - 1), 0)::bigint AS extra_duplicate_rows,
            COUNT(*)::bigint AS duplicate_groups
        FROM dup_groups
        """,
    ),
    (
        "3. Near-duplicate events (same user, product, type within 1 second)",
        """
        WITH buckets AS (
            SELECT
                user_id,
                product_id,
                event_type,
                date_trunc('second', event_time) AS event_second,
                COUNT(*) AS n
            FROM raw_events
            GROUP BY 1, 2, 3, 4
            HAVING COUNT(*) > 1
        )
        SELECT
            COALESCE(SUM(n - 1), 0)::bigint AS rows_to_deduplicate,
            COUNT(*)::bigint AS bucket_count
        FROM buckets
        """,
    ),
    (
        "4. Sessions spanning midnight (min date != max date)",
        """
        SELECT COUNT(*)::bigint AS midnight_spanning_sessions
        FROM (
            SELECT user_session
            FROM raw_events
            GROUP BY user_session
            HAVING MIN(event_time)::date <> MAX(event_time)::date
        ) s
        """,
    ),
    (
        "5. Price anomalies",
        """
        SELECT
            COUNT(*) FILTER (WHERE price = 0)::bigint AS zero_price_rows,
            COUNT(*) FILTER (WHERE price < 0)::bigint AS negative_price_rows
        FROM raw_events
        """,
    ),
    (
        "6. Event type distribution",
        """
        SELECT event_type, COUNT(*)::bigint AS n
        FROM raw_events
        GROUP BY event_type
        ORDER BY n DESC
        """,
    ),
    (
        "7. Date range",
        """
        SELECT MIN(event_time) AS min_event_time, MAX(event_time) AS max_event_time
        FROM raw_events
        """,
    ),
]


def run_report(db_url: str) -> None:
    """Connect once and run every profiling query."""
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw_events")
            total = cur.fetchone()
            if total is None or int(total[0]) == 0:
                sys.exit("raw_events is empty. Run etl/load.py first.")

            print(f"raw_events row count: {int(total[0]):,}\n")

            for title, sql in CHECKS:
                print(title)
                print("-" * len(title))
                cur.execute(sql)

                # Multi-row result (event types) vs single-row aggregates.
                if cur.description and len(cur.description) == 2 and title.startswith("6."):
                    for row in cur.fetchall():
                        print(f"  {row[0]}: {row[1]:,}")
                else:
                    row = cur.fetchone()
                    if row is None:
                        print("  (no rows)")
                    elif len(row) == 1:
                        print(f"  {row[0]}")
                    else:
                        cols = [desc[0] for desc in cur.description]
                        for col, val in zip(cols, row):
                            print(f"  {col}: {val}")
                print()

    print(
        "Copy counts into docs/schema.md cleaning log. "
        "build_dims.py dedupes using the 1-second rule in check 3."
    )


def main() -> None:
    load_dotenv(ROOT / ".env")
    db_url = os.getenv("DB_URL")
    if not db_url:
        sys.exit("DB_URL is missing. Add it to .env at the repo root.")
    run_report(db_url)


if __name__ == "__main__":
    main()
