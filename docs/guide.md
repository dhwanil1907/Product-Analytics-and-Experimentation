# Build Guide — eCommerce Analytics Portfolio Project

Three weeks. One dataset. One defensible finding. This guide tells you what to do each day, what to look for, and what good output looks like. You write all the code.

---

## Prerequisites

Before Day 1:

- PostgreSQL installed locally (`psql --version` to confirm)
- Python 3.9+ with: `psycopg2-binary`, `pandas`, `python-dotenv`
- Dataset downloaded: [eCommerce Events History in Electronics Store](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-electronics-store) — ~900K rows, one CSV file
- A `.env` file at the repo root with your Postgres connection string:
  ```
  DB_URL=postgresql://localhost:5432/ecommerce
  ```
- A database created: `createdb ecommerce`

---

## Week 1 — Foundation

### Days 1–2: Load + Profile

**Goal:** Raw data in Postgres. Every data quality issue documented.

#### Step 1: Load the data

Write `etl/load.py`. It should:

1. Read the CSV with pandas
2. Connect to Postgres using `DB_URL` from `.env`
3. Create the `raw_events` table if it doesn't exist (see `sql/01_schema.sql`)
4. Insert rows in bulk — use `DataFrame.to_sql()` with `method='multi'` or `copy_from` for speed
5. Print: total rows inserted, time taken

Expected output: ~900K rows in under 2 minutes on a modern laptop.

#### Step 2: Profile the data

Write `etl/profile.py`. Run each of these checks and print the results:

| Check | Query to run | What to look for |
|-------|-------------|-----------------|
| Null counts | `SELECT COUNT(*) - COUNT(col) FROM raw_events` for each column | `category_code` and `brand` will have nulls — that's expected |
| Duplicate events | `SELECT user_id, product_id, event_type, event_time, COUNT(*) FROM raw_events GROUP BY 1,2,3,4 HAVING COUNT(*) > 1` | Count how many exact duplicates exist |
| Sessions spanning midnight | `SELECT user_session, MIN(event_time)::date, MAX(event_time)::date FROM raw_events GROUP BY 1 HAVING MIN(event_time)::date != MAX(event_time)::date` | Count affected sessions |
| Price anomalies | `SELECT COUNT(*) FROM raw_events WHERE price <= 0` | Rows with zero or negative price |
| Event type distribution | `SELECT event_type, COUNT(*) FROM raw_events GROUP BY 1` | Confirm only view/cart/purchase |
| Date range | `SELECT MIN(event_time), MAX(event_time) FROM raw_events` | Confirm ~5 months |

#### Step 3: Document cleaning decisions

Open `docs/schema.md` and fill in the Cleaning Decisions Log as you go. For every issue you find, record: what it is, how many rows are affected, what you decided to do, and why.

Do not silently drop rows. Every decision goes in the log.

---

### Days 3–5: Model + First Queries

**Goal:** Four clean tables. Five working window-function queries.

#### Step 1: Create the schema

Run `sql/01_schema.sql`. It should create all five tables:
- `raw_events` (already loaded)
- `dim_products`
- `dim_users`
- `fct_sessions`
- `fct_events`

See `docs/schema.md` for the full column definitions.

#### Step 2: Derive the dimension tables

Write `etl/build_dims.py`. This is the most important Python script — it derives columns that don't exist in the raw data.

**dim_users** — the hard one:
```python
# Pseudocode — implement this in SQL via psycopg2
INSERT INTO dim_users (user_id, first_seen, first_purchase, cohort_week)
SELECT
    user_id,
    MIN(event_time)                                                    AS first_seen,
    MIN(CASE WHEN event_type = 'purchase' THEN event_time END)        AS first_purchase,
    DATE_TRUNC('week', MIN(event_time))                               AS cohort_week
FROM raw_events
GROUP BY user_id
```

**dim_products** — simpler:
```python
# One row per product_id, with price_band derived from median price
INSERT INTO dim_products (product_id, brand, category, price_band)
SELECT DISTINCT ON (product_id)
    product_id,
    brand,
    SPLIT_PART(category_code, '.', 1)   AS category,
    CASE
        WHEN price < 50    THEN 'under_50'
        WHEN price < 200   THEN '50_to_200'
        WHEN price < 500   THEN '200_to_500'
        ELSE               'over_500'
    END                                  AS price_band
FROM raw_events
WHERE price > 0
ORDER BY product_id, event_time DESC
```

#### Step 3: Write your first window-function queries

These are not analysis queries — they are exercises to confirm you understand window functions before you need them in Week 2.

Write each of these in `psql` or a SQL file, understand what each row of output means, and keep them somewhere you can reference later.

**Query 1 — Event order within a session:**
```sql
SELECT
    user_session,
    event_time,
    event_type,
    ROW_NUMBER() OVER (PARTITION BY user_session ORDER BY event_time) AS event_rank
FROM raw_events
LIMIT 50;
```
What it does: numbers each event within its session, starting from 1. Used later to identify session-opening and session-closing events.

**Query 2 — Time between a user's events:**
```sql
SELECT
    user_id,
    event_time,
    event_type,
    LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS prev_event_time,
    event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS time_since_last
FROM raw_events
LIMIT 50;
```
What it does: for each event, shows when the user's previous event was. Useful for identifying gaps between sessions and measuring engagement.

**Query 3 — Running revenue per user:**
```sql
SELECT
    user_id,
    event_time,
    price,
    SUM(price) OVER (PARTITION BY user_id ORDER BY event_time) AS cumulative_revenue
FROM raw_events
WHERE event_type = 'purchase'
ORDER BY user_id, event_time
LIMIT 50;
```
What it does: running total of purchase revenue for each user, in order. Used later for LTV curves.

**Query 4 — Rank products by views:**
```sql
SELECT
    product_id,
    COUNT(*) AS views,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS view_rank
FROM raw_events
WHERE event_type = 'view'
GROUP BY product_id
LIMIT 20;
```

**Query 5 — Session conversion flag:**
```sql
SELECT
    user_session,
    user_id,
    COUNT(*) AS total_events,
    MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS converted
FROM raw_events
GROUP BY user_session, user_id
LIMIT 20;
```

**Deliverable check for Week 1:**
- [ ] `raw_events` loaded, ~900K rows
- [ ] `profile.py` output printed and reviewed
- [ ] All cleaning decisions logged in `docs/schema.md`
- [ ] All 5 tables created and populated
- [ ] 5 window-function queries running and understood

---

## Week 2 — Analysis

### Days 6–8: Funnel Analysis

**Goal:** Know exactly where users drop off. Know which segment drops off worst.

Write `sql/02_funnel.sql`.

#### The core funnel query

The standard pattern for funnel analysis in SQL uses conditional aggregation inside a CTE chain:

```sql
WITH event_counts AS (
    SELECT
        COUNT(DISTINCT CASE WHEN event_type = 'view'     THEN user_id END) AS viewers,
        COUNT(DISTINCT CASE WHEN event_type = 'cart'     THEN user_id END) AS cart_adders,
        COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) AS purchasers
    FROM raw_events
)
SELECT
    viewers,
    cart_adders,
    purchasers,
    ROUND(100.0 * cart_adders  / viewers,    2) AS view_to_cart_pct,
    ROUND(100.0 * purchasers   / cart_adders, 2) AS cart_to_purchase_pct,
    ROUND(100.0 * purchasers   / viewers,    2) AS overall_conversion_pct
FROM event_counts;
```

Why `COUNT(DISTINCT user_id)` and not `COUNT(*)`? Because the same user can view 10 products. You want to know how many unique users reached each stage, not how many times events happened.

#### Slice the funnel

After you have the overall numbers, slice by each of these dimensions. The goal is to find the segment with the worst drop-off:

**By price band:**
```sql
WITH funnel AS (
    SELECT
        p.price_band,
        COUNT(DISTINCT CASE WHEN e.event_type = 'view'     THEN e.user_id END) AS viewers,
        COUNT(DISTINCT CASE WHEN e.event_type = 'cart'     THEN e.user_id END) AS cart_adders,
        COUNT(DISTINCT CASE WHEN e.event_type = 'purchase' THEN e.user_id END) AS purchasers
    FROM raw_events e
    JOIN dim_products p USING (product_id)
    GROUP BY p.price_band
)
SELECT
    price_band,
    viewers,
    ROUND(100.0 * cart_adders / NULLIF(viewers, 0),    2) AS view_to_cart_pct,
    ROUND(100.0 * purchasers  / NULLIF(cart_adders, 0), 2) AS cart_to_purchase_pct
FROM funnel
ORDER BY viewers DESC;
```

Run the same pattern grouped by `brand` and by `EXTRACT(DOW FROM event_time)` (day of week, 0=Sunday).

#### What to look for

- **Biggest drop-off:** Is it view→cart or cart→purchase? This is your funnel finding.
- **Worst-performing segment:** Which price band or brand has the lowest cart→purchase rate? This is a hypothesis to investigate in Days 11–12.
- **Day-of-week pattern:** Do weekends convert differently? Worth one sentence in the README.

**Link to concepts:** [Funnel Analysis](concepts.md#funnel-analysis), [CTEs + Conditional Aggregation](concepts.md#ctes--conditional-aggregation)

---

### Days 9–10: Cohort Analysis

**Goal:** Weekly cohort table. Repeat-purchase rate at D7/D30/D60.

Write `sql/03_cohorts.sql`.

#### Build the cohort table

```sql
WITH cohort_purchases AS (
    SELECT
        u.user_id,
        u.cohort_week,
        e.event_time AS purchase_time,
        (e.event_time::date - u.first_seen::date) AS days_since_first
    FROM dim_users u
    JOIN raw_events e ON e.user_id = u.user_id AND e.event_type = 'purchase'
),
cohort_sizes AS (
    SELECT cohort_week, COUNT(DISTINCT user_id) AS cohort_size
    FROM dim_users
    GROUP BY cohort_week
)
SELECT
    cp.cohort_week,
    cs.cohort_size,
    SUM(CASE WHEN cp.days_since_first BETWEEN 1  AND 7  THEN 1 ELSE 0 END) AS returned_d7,
    SUM(CASE WHEN cp.days_since_first BETWEEN 1  AND 30 THEN 1 ELSE 0 END) AS returned_d30,
    SUM(CASE WHEN cp.days_since_first BETWEEN 1  AND 60 THEN 1 ELSE 0 END) AS returned_d60,
    ROUND(100.0 * SUM(CASE WHEN cp.days_since_first BETWEEN 1 AND 7  THEN 1 ELSE 0 END) / cs.cohort_size, 2) AS d7_rate,
    ROUND(100.0 * SUM(CASE WHEN cp.days_since_first BETWEEN 1 AND 30 THEN 1 ELSE 0 END) / cs.cohort_size, 2) AS d30_rate,
    ROUND(100.0 * SUM(CASE WHEN cp.days_since_first BETWEEN 1 AND 60 THEN 1 ELSE 0 END) / cs.cohort_size, 2) AS d60_rate
FROM cohort_purchases cp
JOIN cohort_sizes cs USING (cohort_week)
GROUP BY cp.cohort_week, cs.cohort_size
ORDER BY cp.cohort_week;
```

#### How to read the output

Each row is a cohort (users who first appeared in that week). The D7/D30/D60 rates tell you what % of that cohort made a second purchase within 7, 30, or 60 days.

In electronics, these numbers will be low — that's fine. Look for:
- **Variation across cohorts:** Did one cohort retain significantly better than others? If yes, investigate what was different about that week.
- **Overall D60 rate:** This becomes your cohort finding in the README.
- **Trend over time:** Are later cohorts retaining better or worse than earlier ones?

**Link to concepts:** [Cohort Analysis](concepts.md#cohort-analysis)

---

### Days 11–12: Retention + Segments

**Goal:** Your one defensible finding with a number in it.

Write `sql/04_retention.sql` and `sql/05_segments.sql`.

#### Which first purchase predicts a second?

This is your best finding candidate. The query compares repeat-purchase rate by first-purchase price band:

```sql
WITH first_purchases AS (
    SELECT
        u.user_id,
        u.first_purchase,
        p.price_band AS first_purchase_band
    FROM dim_users u
    JOIN raw_events e ON e.user_id = u.user_id
                      AND e.event_time = u.first_purchase
                      AND e.event_type = 'purchase'
    JOIN dim_products p USING (product_id)
    WHERE u.first_purchase IS NOT NULL
),
second_purchases AS (
    SELECT DISTINCT user_id
    FROM raw_events e
    JOIN dim_users u USING (user_id)
    WHERE e.event_type = 'purchase'
      AND e.event_time > u.first_purchase
)
SELECT
    fp.first_purchase_band,
    COUNT(DISTINCT fp.user_id)                                                    AS first_time_buyers,
    COUNT(DISTINCT sp.user_id)                                                    AS returned_buyers,
    ROUND(100.0 * COUNT(DISTINCT sp.user_id) / COUNT(DISTINCT fp.user_id), 2)   AS repeat_rate_pct
FROM first_purchases fp
LEFT JOIN second_purchases sp USING (user_id)
GROUP BY fp.first_purchase_band
ORDER BY repeat_rate_pct DESC;
```

When you run this, you will get a table showing which price band has the highest repeat-purchase rate. That number — "users whose first purchase was in [band X] return at [Y]% vs [Z]% for [band W]" — is your key insight.

#### ARPU and revenue concentration

```sql
-- ARPU by price band
SELECT
    p.price_band,
    COUNT(DISTINCT e.user_id)                                 AS buyers,
    SUM(e.price)                                              AS total_revenue,
    ROUND(SUM(e.price) / COUNT(DISTINCT e.user_id), 2)       AS arpu
FROM raw_events e
JOIN dim_products p USING (product_id)
WHERE e.event_type = 'purchase'
GROUP BY p.price_band
ORDER BY arpu DESC;

-- Revenue concentration: top 20% of users by spend → what % of revenue?
WITH user_revenue AS (
    SELECT user_id, SUM(price) AS total_spend
    FROM raw_events
    WHERE event_type = 'purchase'
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
    COUNT(*)                                           AS users,
    SUM(total_spend)                                   AS revenue,
    ROUND(100.0 * SUM(total_spend) / SUM(SUM(total_spend)) OVER (), 2) AS revenue_pct
FROM ranked
GROUP BY quintile
ORDER BY quintile;
```

**Deliverable check for Week 2:**
- [ ] Funnel conversion rates computed — biggest drop-off identified
- [ ] Funnel sliced by at least 2 dimensions
- [ ] Cohort table built — D7/D30/D60 rates for each weekly cohort
- [ ] First-purchase predictor query run — result in hand
- [ ] ARPU by segment computed
- [ ] Revenue concentration computed
- [ ] **One sentence you didn't know on Day 1, with a number in it**

---

## Week 3 — Package

### Days 13–15: Metrics Framework

**Goal:** A North Star you can defend in an interview.

Write this section in `README.md` before you write the findings. Defining the metric first forces you to be honest about what you're measuring.

#### Recommended North Star: Repeat Purchase Rate (90-day)

**Definition:** % of first-time buyers who make a second purchase within 90 days.

**Why this one:**
- It's honest about electronics' weakness — low numbers are a real finding, not a failure
- It's directly actionable: a company can run re-engagement campaigns, post-purchase email sequences, accessory recommendations
- It's not gameable by one big purchase (unlike ARPU) or by traffic spikes (unlike conversion rate)
- It connects directly to the cohort and segment analyses you've already done

**Supporting metrics** (these appear in the analysis but are not the North Star):
- Funnel conversion rate (view → purchase)
- Average Order Value (AOV) by category
- ARPU per cohort
- Session depth (events per session)
- Revenue concentration (top quintile's share)

You don't need to track all of these — they support the story. In your README, state the North Star, then use the others as evidence.

---

### Days 16–18: README

**Goal:** A document a recruiter can read in 3 minutes and understand what you found and why it matters.

Use this template — fill in your actual numbers:

```markdown
# eCommerce Funnel & Cohort Analysis

**Dataset:** eCommerce Events History in Electronics Store (Kaggle, mkechinov) — ~900K events, [date range]
**Tools:** PostgreSQL, Python (pandas, psycopg2)

---

## Business Question

[One sentence. Example: "What drives repeat purchases in an electronics store, and what does the purchase funnel reveal about where users drop off?"]

---

## Data & Cleaning

- [X] events across [Y] users and [Z] sessions
- Removed [N] rows with price ≤ 0 ([%] of dataset)
- [N] sessions spanning midnight — kept as single sessions
- [N] rows with missing category_code — kept (brand and price intact)
- [N] duplicate events removed (same user + product + event type within 1 second)

---

## Funnel Findings

Overall conversion: [X]% of viewers add to cart; [Y]% of cart-adders purchase.

The biggest drop-off is at [view→cart / cart→purchase]. [One sentence on the worst-performing segment].

---

## Cohort Findings

D30 repeat-purchase rate across all cohorts: [X]%.

[One sentence on any cohort that stood out — better or worse than average.]

---

## Key Insight

[Your one finding. Example: "Users whose first purchase was under $50 return at 2.3× the rate of users whose first purchase was over $200 — suggesting a low-cost entry strategy could improve long-term retention."]

---

## Recommendation

[One concrete action tied directly to your key insight. Example: "Prioritize post-purchase re-engagement for high-value first buyers (>$200). Despite lower repeat rates, this segment drives [X]% of total revenue — even a modest lift in repeat rate would have outsized impact."]

---

## Limitations

- Electronics is a low-repeat-purchase category by nature; retention numbers are expected to be low
- Dataset covers ~5 months — insufficient to capture annual purchase cycles
- No demographic data — segmentation limited to behavioral signals
- No A/B test data — all findings are observational
```

---

### Days 19–21: Tableau (optional)

Build three views in Tableau Public and link from README. Skip if you're behind — the SQL + README is what matters.

**View 1 — Funnel bar chart:**
Export the funnel query result as CSV. Build a bar chart: stages on X axis, conversion % on Y. Add a reference line at the overall rate.

**View 2 — Cohort heatmap:**
Export the cohort table. Rows = cohort week, columns = D7/D30/D60. Color by retention rate. This is the visual most likely to appear in an interview conversation.

**View 3 — Segment revenue breakdown:**
Export ARPU by price band. Bar chart ordered by ARPU descending, colored by segment. Add total buyers as a label.

To publish: Tableau Public → File → Save to Tableau Public. Copy the share link and paste into README under a `## Dashboard` section.

---

## Final Deliverable Checklist

- [ ] `etl/load.py` runs cleanly from a fresh clone
- [ ] `etl/profile.py` prints a readable data quality report
- [ ] `etl/build_dims.py` populates all dimension tables correctly
- [ ] All 5 SQL files run without errors
- [ ] `docs/schema.md` cleaning log is complete
- [ ] README leads with the business question, not the tech stack
- [ ] Key insight has a number in it
- [ ] Recommendation is tied to the finding (not generic advice)
- [ ] Limitations section is honest
- [ ] `.gitignore` excludes `.env`, `*.csv`, `__pycache__`
