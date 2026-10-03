# etl/load.py
#
# Goal: get the raw CSV into Postgres as raw_events, unchanged.
# This script loads. It does not clean, dedupe, or derive columns.
#
# Before you start:
# - Postgres is running and the ecommerce database exists.
# - DB_URL is in a .env file at the repo root. Read it with python-dotenv.
#   Do not hardcode the connection string.
# - The CSV is data/events.csv. It is gitignored. About 900k rows.
#
# What to build:
# 1. Read the CSV with pandas.
# 2. Connect to Postgres with psycopg2 using DB_URL.
# 3. Create raw_events if it does not exist yet. Column names and types
#    are in docs/schema.md. Load the file as-is: no filters, no renames
#    beyond matching those columns.
# 4. Insert in bulk. Row-by-row inserts will be too slow.
#    Hint: DataFrame.to_sql with a multi-row method, or Postgres COPY.
# 5. Print how many rows landed and how long it took.
#
# Done when: about 900k rows, and a rerun does not silently duplicate
# them. Hint: truncate or replace before inserting.
#
# Expected speed: under a couple of minutes on a laptop.
# Next script: etl/profile.py. Do not clean anything here.
