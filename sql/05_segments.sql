-- sql/05_segments.sql
-- Revenue segments: ARPU, AOV, and concentration (Pareto-style quintiles).
-- Revenue uses purchase events with price > 0 only.

-- ---------------------------------------------------------------------------
-- Query 1: ARPU by price_band
-- ARPU = total revenue / distinct buyers in that band.
-- ---------------------------------------------------------------------------
SELECT
    p.price_band,
    COUNT(DISTINCT e.user_id) AS buyers,
    ROUND(SUM(e.price), 2) AS total_revenue,
    ROUND(SUM(e.price) / NULLIF(COUNT(DISTINCT e.user_id), 0), 2) AS arpu
FROM fct_events e
INNER JOIN dim_products p ON p.product_id = e.product_id
WHERE e.event_type = 'purchase'
  AND e.price > 0
GROUP BY p.price_band
ORDER BY arpu DESC;

-- ---------------------------------------------------------------------------
-- Query 2: ARPU by category (top-level category on dim_products)
-- ---------------------------------------------------------------------------
SELECT
    COALESCE(p.category, '(no category)') AS category,
    COUNT(DISTINCT e.user_id) AS buyers,
    ROUND(SUM(e.price), 2) AS total_revenue,
    ROUND(SUM(e.price) / NULLIF(COUNT(DISTINCT e.user_id), 0), 2) AS arpu
FROM fct_events e
INNER JOIN dim_products p ON p.product_id = e.product_id
WHERE e.event_type = 'purchase'
  AND e.price > 0
GROUP BY COALESCE(p.category, '(no category)')
ORDER BY total_revenue DESC;

-- ---------------------------------------------------------------------------
-- Query 3: AOV by price_band (revenue per order, not per user)
-- ---------------------------------------------------------------------------
SELECT
    p.price_band,
    COUNT(*) AS purchase_events,
    ROUND(SUM(e.price), 2) AS total_revenue,
    ROUND(SUM(e.price) / NULLIF(COUNT(*), 0), 2) AS aov
FROM fct_events e
INNER JOIN dim_products p ON p.product_id = e.product_id
WHERE e.event_type = 'purchase'
  AND e.price > 0
GROUP BY p.price_band
ORDER BY aov DESC;

-- ---------------------------------------------------------------------------
-- Query 4: Revenue concentration by spend quintile
-- Quintile 1 = highest spenders. Shows share of revenue in each fifth.
-- ---------------------------------------------------------------------------
WITH user_revenue AS (
    SELECT user_id, SUM(price) AS total_spend
    FROM fct_events
    WHERE event_type = 'purchase'
      AND price > 0
    GROUP BY user_id
),
ranked AS (
    SELECT
        user_id,
        total_spend,
        NTILE(5) OVER (ORDER BY total_spend DESC) AS quintile
    FROM user_revenue
)
SELECT
    quintile,
    COUNT(*) AS users,
    ROUND(SUM(total_spend), 2) AS revenue,
    ROUND(
        100.0 * SUM(total_spend) / SUM(SUM(total_spend)) OVER (),
        2
    ) AS revenue_pct
FROM ranked
GROUP BY quintile
ORDER BY quintile;
