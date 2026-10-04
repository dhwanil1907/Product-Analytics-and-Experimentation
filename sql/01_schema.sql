-- sql/01_schema.sql
-- Creates dimension and fact tables used for analysis.
-- raw_events is created by etl/load.py when you load the CSV.
-- Run this after load.py, before etl/build_dims.py.

-- Drop child tables first so foreign keys do not block the drop.
DROP TABLE IF EXISTS fct_events;
DROP TABLE IF EXISTS fct_sessions;
DROP TABLE IF EXISTS dim_products;
DROP TABLE IF EXISTS dim_users;

-- One row per product. price_band comes from the latest non-zero price in build_dims.
CREATE TABLE dim_products (
    product_id bigint PRIMARY KEY,
    brand text,
    category text,
    price_band text NOT NULL
);

-- One row per user. first_seen and cohort_week are derived from event history.
CREATE TABLE dim_users (
    user_id bigint PRIMARY KEY,
    first_seen timestamptz NOT NULL,
    first_purchase timestamptz,
    cohort_week date NOT NULL
);

-- One row per session (user_session in the CSV). session_id is text, not a UUID.
CREATE TABLE fct_sessions (
    session_id text PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES dim_users (user_id),
    session_start timestamptz NOT NULL,
    session_duration interval NOT NULL,
    event_count integer NOT NULL,
    converted boolean NOT NULL
);

-- Cleaned events with foreign keys. Analysis queries should read this table.
CREATE TABLE fct_events (
    event_time timestamptz NOT NULL,
    event_type text NOT NULL,
    product_id bigint NOT NULL REFERENCES dim_products (product_id),
    category_id bigint NOT NULL,
    category_code text,
    brand text,
    price numeric NOT NULL,
    user_id bigint NOT NULL REFERENCES dim_users (user_id),
    user_session text NOT NULL REFERENCES fct_sessions (session_id)
);

CREATE INDEX idx_fct_events_user ON fct_events (user_id);
CREATE INDEX idx_fct_events_product ON fct_events (product_id);
CREATE INDEX idx_fct_events_type ON fct_events (event_type);
CREATE INDEX idx_fct_events_time ON fct_events (event_time);
