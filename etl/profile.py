# etl/profile.py
#
# Goal: print a data-quality report for raw_events. Do not delete or
# update rows in this script. Every finding gets a row in the cleaning
# log in docs/schema.md (count or percent, decision, reason).
#
# Connect the same way as load.py: DB_URL from .env.
#
# Run these checks and print each result with a label:
#
# 1. Nulls per column.
#    Expect nulls in category_code and brand. Those rows stay.
#    Other columns should be complete. If one is not, stop and look.
#
# 2. Exact duplicate events.
#    Same user, product, event type, and timestamp.
#    Hint: group by those four and keep groups with more than one row.
#    The cleaning log starts from a tighter rule: same user, product,
#    and event type within one second. Adjust that rule if this check
#    shows a different pattern. Count the extras. Do not drop them here.
#
# 3. Sessions that cross midnight.
#    A user_session whose earliest and latest event fall on different
#    calendar dates. Count how many. The default decision is to keep
#    them as one session, because the session id is already the boundary.
#
# 4. Price anomalies.
#    Count price equal to zero and price below zero separately.
#    Zero-price rows stay in the table but must be left out of revenue
#    later. Negative prices, if any, stay out of every calculation.
#
# 5. Event types.
#    Counts by event_type. You should only see view, cart, and purchase.
#    Anything else is a data bug, not a new funnel step.
#
# 6. Date range.
#    Earliest and latest event_time. Expect roughly five months.
#
# Done when: the report prints all six checks and the cleaning log
# no longer says "TBD after profiling".
