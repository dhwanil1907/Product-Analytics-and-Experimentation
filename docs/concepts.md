# Analytics Concepts

Reference for the ideas behind this project. Each entry covers what the concept is, why it matters, and how it shows up in this specific dataset. Not exhaustive — just what you need to understand and explain the analysis.

---

## Funnel Analysis

**What it is:**
A funnel tracks how many users complete each step of a defined sequence, and measures the drop-off between steps. The name comes from the shape: wide at the top (many users), narrow at the bottom (fewer complete all steps).

**How it applies here:**
The funnel is view → cart → purchase. Most users who view a product never add it to cart. Most who add to cart never buy. The analysis quantifies each stage and finds where the biggest leak is. See [`sql/02_funnel.sql`](../sql/02_funnel.sql).

**Key terms:**
- *Conversion rate:* % of users who move from one stage to the next
- *Drop-off rate:* 100% - conversion rate — how many fall out at each stage
- *Top-of-funnel:* the first stage (views); *bottom-of-funnel:* the last (purchase)

---

## Session Definition

**What it is:**
A session is a single continuous visit by a user — a group of events that belong together because they happened close in time. Sessions are the unit of engagement analysis: how deep did a user go in one visit?

**How it applies here:**
The dataset provides a `user_session` column, so session boundaries are already defined. Your job is to understand what's in each session (how many events, did it convert?) and flag edge cases — specifically sessions where the first and last event happen on different calendar days. These "midnight-spanning" sessions exist in the data. Document how many there are and how you handle them. See `docs/schema.md` cleaning decisions.

**Key terms:**
- *Session depth:* number of events in a session
- *Session conversion:* whether a session contains a purchase event
- *Bounce:* a session with only one event (single page view, no further action)

---

## Cohort Analysis

**What it is:**
Cohort analysis groups users by a shared characteristic — usually when they first appeared — and then tracks their behavior over time. It answers: "do users who joined in October behave differently than users who joined in November?"

The alternative (looking at all users together) hides cohort effects. If November had a sale, newer cohorts might look more active not because retention improved, but because there were more buyers.

**How it applies here:**
Users are grouped by `cohort_week` — the Monday of the week when they first appeared in the dataset. You then measure what % of each cohort made a second purchase at D7, D30, and D60. The result is a heatmap where rows are cohort weeks and columns are time intervals. See [`sql/03_cohorts.sql`](../sql/03_cohorts.sql).

**Key terms:**
- *Cohort:* a group of users sharing a time-based first event
- *Cohort week:* `DATE_TRUNC('week', first_seen)` — the Monday that starts their first week
- *Retention rate:* % of a cohort who returned and made a repeat purchase by day N

---

## Retention Curves

**What it is:**
A retention curve plots the % of users still active at each point in time after their first event. It shows how quickly a product loses its users. A flat curve means users keep coming back. A steep drop that levels off means there's a retained core. A curve that goes to zero means users don't return.

**How it applies here:**
Electronics is a low-repeat-purchase category. Users buy a laptop once every few years. Your retention curve will drop steeply — that is not a broken analysis, it is the finding. "X% of purchasers never make a second purchase within 90 days" is a real, defensible insight. It directly motivates the recommendation: focus on accessories, warranties, and complementary products to create re-engagement opportunities. See [`sql/04_retention.sql`](../sql/04_retention.sql).

**Key terms:**
- *D7/D30/D60:* shorthand for "7 days / 30 days / 60 days after first event"
- *Repeat purchase rate:* % of users who bought at least twice — the core metric
- *Natural retention ceiling:* in electronics, expect D30 rates in single digits — that's normal

---

## Window Functions

**What it is:**
A window function performs a calculation across a set of rows that are related to the current row, without collapsing those rows into a single output row (unlike GROUP BY). The "window" is defined by `OVER (PARTITION BY ... ORDER BY ...)`.

The three you use in this project:

**ROW_NUMBER()** — assigns a sequential integer to each row within a partition:
```sql
ROW_NUMBER() OVER (PARTITION BY user_session ORDER BY event_time)
-- Result: 1, 2, 3... for each event in a session, in time order
```

**LAG()** — returns a value from a previous row in the same partition:
```sql
LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time)
-- Result: the timestamp of the user's previous event (NULL for first event)
```

**SUM() OVER()** — running total within a partition:
```sql
SUM(price) OVER (PARTITION BY user_id ORDER BY event_time)
-- Result: cumulative spend for each user, updated with each purchase
```

**How it applies here:**
- `ROW_NUMBER()` orders events within a session — used to identify what happens first and last in a session
- `LAG()` computes time between events — used to measure how long users spend browsing before buying
- `SUM() OVER()` builds running revenue per user — used for LTV analysis

**Why not just GROUP BY?**
GROUP BY collapses rows — you get one row per group. Window functions keep all rows and add a computed column. For session analysis, you need both the individual events and the session-level calculation on the same row.

---

## CTEs + Conditional Aggregation

**What it is:**

A **CTE (Common Table Expression)** is a named subquery defined with `WITH`. It makes complex queries readable by breaking them into named steps:
```sql
WITH step_one AS (
    SELECT ...
),
step_two AS (
    SELECT ... FROM step_one
)
SELECT * FROM step_two;
```

**Conditional aggregation** uses `CASE WHEN` inside an aggregate function to count or sum only rows that meet a condition:
```sql
COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END)
-- Counts distinct user_ids, but only for purchase events
```

**How it applies here:**
The funnel query chains both techniques: a CTE computes counts for each event type using conditional aggregation, then the outer query computes conversion rates from those counts. This is the standard SQL pattern for funnel analysis — knowing it by memory is worth something in an interview. See [`sql/02_funnel.sql`](../sql/02_funnel.sql).

---

## ARPU / AOV

**What they are:**

**AOV (Average Order Value):** total revenue ÷ number of orders (transactions). Answers: how much does a typical transaction generate?
```sql
SUM(price) / COUNT(*) -- where event_type = 'purchase'
```

**ARPU (Average Revenue Per User):** total revenue ÷ number of distinct users. Answers: how much does a typical user generate over a period?
```sql
SUM(price) / COUNT(DISTINCT user_id) -- where event_type = 'purchase'
```

**The difference matters:**
A user who makes one $500 purchase vs. five users who each make one $100 purchase have the same total revenue, but different AOV (same) and different ARPU ($500 vs $100). ARPU is more useful for understanding user value; AOV is more useful for understanding product/pricing.

**How it applies here:**
ARPU by price band reveals which segment drives the most revenue per user. Revenue concentration (top quintile) shows whether revenue is broadly distributed or dominated by a few high-value users. Both inform the recommendation. See [`sql/05_segments.sql`](../sql/05_segments.sql).

---

## Price Band Segmentation

**What it is:**
Price band segmentation converts a continuous numeric variable (price) into ordered categorical buckets. Instead of grouping by exact price (useless — thousands of unique values), you group by range:

| Band | Range |
|------|-------|
| under_50 | price < $50 |
| 50_to_200 | $50 ≤ price < $200 |
| 200_to_500 | $200 ≤ price < $500 |
| over_500 | price ≥ $500 |

**Why it matters:**
`GROUP BY price` on a continuous variable produces noise. `GROUP BY price_band` produces four interpretable groups you can compare, chart, and talk about in a presentation. The bands here are defined by natural product categories in electronics: accessories (<$50), mid-range peripherals ($50–$200), main devices ($200–$500), premium devices (>$500).

**How it applies here:**
`dim_products.price_band` is derived in `etl/build_dims.py` and used in funnel slicing (which price band converts best?), cohort/retention analysis (which first-purchase band predicts a return?), and ARPU analysis. It's the primary segmentation variable in this project. See [`sql/05_segments.sql`](../sql/05_segments.sql).

---

## Revenue Concentration

**What it is:**
Revenue concentration measures how unevenly revenue is distributed across users. The most common framing is the Pareto principle: in many markets, roughly 20% of customers generate 80% of revenue. The exact numbers vary, but the pattern — a small group of high-value users disproportionately driving revenue — is common in eCommerce.

In SQL, you measure this with `NTILE()` to split users into equal groups (quintiles, deciles) by spend, then sum revenue per group:
```sql
NTILE(5) OVER (ORDER BY total_spend DESC) AS quintile
```

**How it applies here:**
In electronics, revenue concentration tends to be high — one person buying a $2000 laptop contributes more than 40 people buying $50 accessories. Running the concentration query tells you whether to focus retention efforts on all buyers or specifically on high-value first-time buyers. This directly informs the recommendation. See [`sql/05_segments.sql`](../sql/05_segments.sql).

---

## North Star Metric

**What it is:**
A North Star metric is the single number that best captures whether the product is delivering long-term value. It should:
- Reflect genuine value (not just activity)
- Be actionable (something the team can influence)
- Be resistant to gaming (hard to inflate with one-off events)
- Connect to revenue over time

**How it applies here:**
The recommended North Star for this analysis is **Repeat Purchase Rate within 90 days** — the % of first-time buyers who make a second purchase within 90 days.

Why this one over the alternatives:
- *Conversion rate* (view → purchase): measures acquisition efficiency, not retention. A company could improve this by running a sale — doesn't tell you if customers come back.
- *ARPU*: inflatable by a single high-value purchase. One $2000 transaction moves the number without indicating sustainable engagement.
- *Repeat Purchase Rate*: requires a user to voluntarily return and buy again. Low in electronics by category nature — but variation across segments and cohorts still reveals actionable differences.

In Week 3, you'll write a paragraph in the README justifying your North Star choice. The reasoning matters more than the number — it shows you understand the business context.
