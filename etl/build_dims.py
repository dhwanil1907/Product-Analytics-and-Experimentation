# etl/build_dims.py
#
# Goal: fill the four derived tables from raw_events.
# Run 01_schema.sql first so the empty tables exist.
# Do the derivation in SQL sent from this script, not with pandas groupby.
# The analysis queries later should not have to recompute these columns.
#
# Make the script safe to rerun: clear each target table before loading it,
# or the second run will violate primary keys.
#
# Order matters because of foreign keys. Dimensions and sessions first,
# fct_events last.
#
# dim_users — one row per user_id. None of these columns exist in the CSV.
# - first_seen: earliest event_time for that user.
# - first_purchase: earliest event_time where the event is a purchase.
#   Null when the user never bought.
# - cohort_week: the Monday of the week containing first_seen.
#   Hint: truncating a timestamp to the week returns that Monday. Every
#   user who first appears Monday through Sunday of the same week shares
#   a cohort.
#
# dim_products — one row per product_id.
# - brand: from the latest event for that product. Null is allowed.
# - category: the first segment of category_code, the text before the
#   first dot. Example shape: electronics.smartphone.phone becomes
#   electronics. Null when category_code is always null.
# - price_band: from the latest price that is greater than zero.
#   Buckets: under 50, 50 up to 200, 200 up to 500, 500 and above.
#   Use those four labels so later queries can group on them.
# - Drop products whose every price is zero or negative. They have no band.
#
# fct_sessions — one row per user_session.
# - session_id is the user_session value.
# - session_start is the earliest event in the session.
# - session_duration is latest event minus earliest event.
# - event_count is how many events the session has.
# - converted is true when any event in the session is a purchase.
# - Keep midnight-spanning sessions as one row.
#
# fct_events — cleaned events, the table analysis should read.
# - Same columns as raw_events, with foreign keys to dim_products,
#   dim_users, and fct_sessions.
# - Remove the duplicate events you defined in the cleaning log.
#   Keep one copy.
# - Keep rows with null category_code or null brand.
# - Keep zero and negative prices in the table. Revenue queries exclude
#   them later. Funnel counts can still use them.
# - If a product was excluded from dim_products, decide explicitly what
#   happens to its events. Hint: a foreign key to dim_products will reject
#   them. Either keep those products in the dimension with a documented
#   band, or leave those events out of fct_events and say so in the log.
#
# Done when: each table has the grain in docs/schema.md (one row per
# product, per user, per session, per cleaned event) and a second run
# of this script succeeds.
