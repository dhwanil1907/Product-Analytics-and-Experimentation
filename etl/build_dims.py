# etl/build_dims.py
# Derives and populates dim_users, dim_products, fct_sessions, fct_events.
# See docs/guide.md — Days 3-5 for the derivation logic, especially dim_users.
# Run after load.py and after 01_schema.sql has been executed.
