"""Load data/events.csv into Postgres raw_events without cleaning it."""

import io
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "events.csv"

COLUMNS = [
    "event_time",
    "event_type",
    "product_id",
    "category_id",
    "category_code",
    "brand",
    "price",
    "user_id",
    "user_session",
]

# Session ids in this file are 10-character strings, not UUIDs.
CREATE_RAW_EVENTS = """
CREATE TABLE IF NOT EXISTS raw_events (
    event_time timestamptz NOT NULL,
    event_type text NOT NULL,
    product_id bigint NOT NULL,
    category_id bigint NOT NULL,
    category_code text,
    brand text,
    price numeric NOT NULL,
    user_id bigint NOT NULL,
    user_session text NOT NULL
)
"""


def load_events(db_url: str, csv_path: Path) -> int:
    """Replace raw_events with the CSV and return the inserted row count."""
    frame = pd.read_csv(csv_path)
    missing = [name for name in COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"CSV is missing columns: {', '.join(missing)}")

    buffer = io.StringIO()
    frame.loc[:, COLUMNS].to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_RAW_EVENTS)
            cur.execute("TRUNCATE raw_events")
            cur.copy_expert(
                "COPY raw_events FROM STDIN WITH (FORMAT csv)",
                buffer,
            )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM raw_events")
            row = cur.fetchone()
    if row is None:
        raise RuntimeError("raw_events count query returned no row")
    return int(row[0])


def main() -> None:
    load_dotenv(ROOT / ".env")
    db_url = os.getenv("DB_URL")
    if not db_url:
        sys.exit("DB_URL is missing. Add it to .env at the repo root.")
    if not CSV_PATH.is_file():
        sys.exit(f"CSV not found: {CSV_PATH}")

    started = time.perf_counter()
    row_count = load_events(db_url, CSV_PATH)
    elapsed = time.perf_counter() - started
    print(f"Inserted {row_count} rows in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
