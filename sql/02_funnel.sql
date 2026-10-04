-- sql/02_funnel.sql
-- Funnel: view → cart → purchase. Uses distinct users per stage.
-- Run against fct_events (deduped) joined to dim_products for slices.

-- ---------------------------------------------------------------------------
-- Query 1: Overall funnel
-- Count how many unique users reached each stage, then conversion rates.
-- ---------------------------------------------------------------------------
WITH stage_users AS (
    SELECT
        COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'view') AS viewers,
        COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'cart') AS cart_adders,
        COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'purchase') AS purchasers
    FROM fct_events
)
SELECT
    viewers,
    cart_adders,
    purchasers,
    ROUND(100.0 * cart_adders / NULLIF(viewers, 0), 2) AS view_to_cart_pct,
    ROUND(100.0 * purchasers / NULLIF(cart_adders, 0), 2) AS cart_to_purchase_pct,
    ROUND(100.0 * purchasers / NULLIF(viewers, 0), 2) AS overall_conversion_pct
FROM stage_users;

-- ---------------------------------------------------------------------------
-- Query 2: Funnel by price_band
-- Same logic, one row per band from dim_products.
-- ---------------------------------------------------------------------------
WITH funnel AS (
    SELECT
        p.price_band,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'view') AS viewers,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'cart') AS cart_adders,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'purchase') AS purchasers
    FROM fct_events e
    INNER JOIN dim_products p ON p.product_id = e.product_id
    GROUP BY p.price_band
)
SELECT
    price_band,
    viewers,
    cart_adders,
    purchasers,
    ROUND(100.0 * cart_adders / NULLIF(viewers, 0), 2) AS view_to_cart_pct,
    ROUND(100.0 * purchasers / NULLIF(cart_adders, 0), 2) AS cart_to_purchase_pct
FROM funnel
ORDER BY viewers DESC;

-- ---------------------------------------------------------------------------
-- Query 3: Funnel by brand (brands with at least 500 viewers)
-- Filters out tiny brands whose rates bounce around.
-- ---------------------------------------------------------------------------
WITH funnel AS (
    SELECT
        COALESCE(p.brand, '(no brand)') AS brand,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'view') AS viewers,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'cart') AS cart_adders,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'purchase') AS purchasers
    FROM fct_events e
    INNER JOIN dim_products p ON p.product_id = e.product_id
    GROUP BY COALESCE(p.brand, '(no brand)')
)
SELECT
    brand,
    viewers,
    cart_adders,
    purchasers,
    ROUND(100.0 * cart_adders / NULLIF(viewers, 0), 2) AS view_to_cart_pct,
    ROUND(100.0 * purchasers / NULLIF(cart_adders, 0), 2) AS cart_to_purchase_pct
FROM funnel
WHERE viewers >= 500
ORDER BY cart_to_purchase_pct ASC NULLS LAST, viewers DESC;

-- ---------------------------------------------------------------------------
-- Query 4: Funnel by day of week (Postgres DOW: 0 = Sunday)
-- Uses the event timestamp, not session start.
-- ---------------------------------------------------------------------------
WITH funnel AS (
    SELECT
        EXTRACT(DOW FROM e.event_time)::integer AS day_of_week,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'view') AS viewers,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'cart') AS cart_adders,
        COUNT(DISTINCT e.user_id) FILTER (WHERE e.event_type = 'purchase') AS purchasers
    FROM fct_events e
    GROUP BY EXTRACT(DOW FROM e.event_time)
)
SELECT
    day_of_week,
    viewers,
    cart_adders,
    purchasers,
    ROUND(100.0 * purchasers / NULLIF(viewers, 0), 2) AS view_to_purchase_pct
FROM funnel
ORDER BY day_of_week;
