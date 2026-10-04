-- sql/03_cohorts.sql
-- Weekly signup cohorts from dim_users.cohort_week.
-- Repeat purchase = purchase after first_seen, within D7 / D30 / D60 windows.

-- ---------------------------------------------------------------------------
-- Cohort table: size and repeat-purchase counts at 7, 30, 60 days
-- Denominator is all users in the cohort, not just buyers.
-- ---------------------------------------------------------------------------
WITH user_purchases AS (
    SELECT
        u.user_id,
        u.cohort_week,
        u.first_seen,
        e.event_time AS purchase_time,
        (e.event_time::date - u.first_seen::date) AS days_since_first
    FROM dim_users u
    INNER JOIN fct_events e
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
    SELECT
        cohort_week,
        COUNT(DISTINCT user_id) FILTER (
            WHERE days_since_first BETWEEN 1 AND 7
        ) AS returned_d7,
        COUNT(DISTINCT user_id) FILTER (
            WHERE days_since_first BETWEEN 1 AND 30
        ) AS returned_d30,
        COUNT(DISTINCT user_id) FILTER (
            WHERE days_since_first BETWEEN 1 AND 60
        ) AS returned_d60
    FROM user_purchases
    GROUP BY cohort_week
)
SELECT
    cs.cohort_week,
    cs.cohort_size,
    COALESCE(cr.returned_d7, 0) AS returned_d7,
    COALESCE(cr.returned_d30, 0) AS returned_d30,
    COALESCE(cr.returned_d60, 0) AS returned_d60,
    ROUND(100.0 * COALESCE(cr.returned_d7, 0) / cs.cohort_size, 2) AS d7_rate_pct,
    ROUND(100.0 * COALESCE(cr.returned_d30, 0) / cs.cohort_size, 2) AS d30_rate_pct,
    ROUND(100.0 * COALESCE(cr.returned_d60, 0) / cs.cohort_size, 2) AS d60_rate_pct
FROM cohort_sizes cs
LEFT JOIN cohort_returns cr USING (cohort_week)
ORDER BY cs.cohort_week;

-- ---------------------------------------------------------------------------
-- Data boundary: cohorts that cannot complete a full 60-day window
-- Compare cohort week + 60 days to the latest event in the dataset.
-- ---------------------------------------------------------------------------
WITH bounds AS (
    SELECT MAX(event_time)::date AS max_event_date FROM fct_events
)
SELECT
    u.cohort_week,
    COUNT(*) AS cohort_size,
    b.max_event_date,
    (u.cohort_week + INTERVAL '60 days')::date AS d60_eligible_through,
    CASE
        WHEN (u.cohort_week + INTERVAL '60 days')::date > b.max_event_date
            THEN 'incomplete_d60'
        ELSE 'complete_d60'
    END AS d60_status
FROM dim_users u
CROSS JOIN bounds b
GROUP BY u.cohort_week, b.max_event_date
ORDER BY u.cohort_week;
