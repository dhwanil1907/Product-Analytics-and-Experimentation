-- sql/04_retention.sql
-- Key insight query: repeat purchase rate by first-purchase price band.
-- Also: return curve after first purchase (any event).

-- ---------------------------------------------------------------------------
-- Query 1: Second purchase rate by first-purchase price band
-- Band comes from the product on the user's first_purchase timestamp.
-- ---------------------------------------------------------------------------
WITH first_purchase_events AS (
    SELECT
        u.user_id,
        u.first_purchase,
        p.price_band AS first_purchase_band
    FROM dim_users u
    INNER JOIN fct_events e
        ON e.user_id = u.user_id
        AND e.event_type = 'purchase'
        AND e.event_time = u.first_purchase
        AND e.price > 0
    INNER JOIN dim_products p ON p.product_id = e.product_id
    WHERE u.first_purchase IS NOT NULL
),
second_purchase AS (
    SELECT DISTINCT fp.user_id
    FROM first_purchase_events fp
    INNER JOIN fct_events e
        ON e.user_id = fp.user_id
        AND e.event_type = 'purchase'
        AND e.event_time > fp.first_purchase
)
SELECT
    fp.first_purchase_band,
    COUNT(DISTINCT fp.user_id) AS first_time_buyers,
    COUNT(DISTINCT sp.user_id) AS returned_buyers,
    ROUND(
        100.0 * COUNT(DISTINCT sp.user_id) / NULLIF(COUNT(DISTINCT fp.user_id), 0),
        2
    ) AS repeat_rate_pct
FROM first_purchase_events fp
LEFT JOIN second_purchase sp ON sp.user_id = fp.user_id
GROUP BY fp.first_purchase_band
ORDER BY repeat_rate_pct DESC;

-- ---------------------------------------------------------------------------
-- Query 2: Activity after first purchase (any event type)
-- Share of buyers who show any activity within 7 / 30 / 60 days.
-- ---------------------------------------------------------------------------
WITH buyers AS (
    SELECT user_id, first_purchase
    FROM dim_users
    WHERE first_purchase IS NOT NULL
),
activity AS (
    SELECT
        b.user_id,
        MIN((e.event_time::date - b.first_purchase::date)) AS days_to_return
    FROM buyers b
    INNER JOIN fct_events e
        ON e.user_id = b.user_id
        AND e.event_time > b.first_purchase
    GROUP BY b.user_id
)
SELECT
    COUNT(*) AS first_time_buyers,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE days_to_return BETWEEN 1 AND 7)
        / NULLIF(COUNT(*), 0),
        2
    ) AS active_d7_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE days_to_return BETWEEN 1 AND 30)
        / NULLIF(COUNT(*), 0),
        2
    ) AS active_d30_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE days_to_return BETWEEN 1 AND 60)
        / NULLIF(COUNT(*), 0),
        2
    ) AS active_d60_pct
FROM buyers b
LEFT JOIN activity a ON a.user_id = b.user_id;
