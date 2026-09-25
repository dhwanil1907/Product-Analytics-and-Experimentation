# eCommerce Analytics Portfolio Project — Design Spec

**Date:** 2026-09-19
**Author:** Dhwanil
**Target roles:** Data Analyst, Data Scientist

---

## Overview

A three-week solo portfolio project built on the eCommerce Events History in Electronics Store dataset (Kaggle, mkechinov, ~900K rows). The goal is a portfolio-ready GitHub repository that demonstrates SQL proficiency, analytical thinking, and the ability to translate data findings into business recommendations.

The user writes all code independently. This spec defines the structure, content, and intent of each deliverable file.

---

## Dataset

- **Source:** Kaggle — eCommerce Events History in Electronics Store (mkechinov)
- **Size:** ~900K rows
- **Columns:** event_time, event_type, product_id, category_id, category_code, brand, price, user_id, user_session
- **Event types:** view, cart, purchase
- **Date range:** ~5 months
- **Known weakness:** Electronics is a low-repeat-purchase category. This is a finding, not a flaw. "X% of purchasers never return within 90 days" is a valid, defensible insight that leads to a recommendation.

---

## Deliverables

| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | Business-facing summary: question → findings → recommendation | Recruiters |
| `docs/guide.md` | Step-by-step build guide, week by week | Self (while building) |
| `docs/concepts.md` | Analytics concepts tied to this project | Self + any reader |
| `docs/schema.md` | Tables, columns, ER diagram, cleaning decisions | Technical reviewers |
| `etl/load.py` | Reads CSV, inserts to Postgres raw_events | — |
| `etl/profile.py` | Data quality checks: nulls, dupes, edge cases | — |
| `etl/build_dims.py` | Derives dim_users, dim_products from raw_events | — |
| `sql/01_schema.sql` | CREATE TABLE statements for all 5 tables | — |
| `sql/02_funnel.sql` | Funnel analysis queries | — |
| `sql/03_cohorts.sql` | Weekly cohort + repeat-purchase queries | — |
| `sql/04_retention.sql` | D7/D30/D60 return-visit curves | — |
| `sql/05_segments.sql` | ARPU, AOV, revenue concentration by segment | — |

---

## Repository Structure

```
ecommerce-analytics/
├── README.md                         # recruiter-facing summary
├── docs/
│   ├── guide.md                      # week-by-week build guide
│   ├── concepts.md                   # analytics concept reference
│   └── schema.md                     # data model + cleaning log
├── etl/
│   ├── load.py                       # CSV → Postgres loader
│   ├── profile.py                    # data quality profiler
│   └── build_dims.py                 # dim table derivation
├── sql/
│   ├── 01_schema.sql
│   ├── 02_funnel.sql
│   ├── 03_cohorts.sql
│   ├── 04_retention.sql
│   └── 05_segments.sql
├── requirements.txt
└── .gitignore
```

---

## Data Model

### Tables

**raw_events** — as loaded from CSV, no transformations
- event_time (timestamptz), event_type (text), product_id (bigint)
- category_id (bigint), category_code (text, nullable), brand (text, nullable)
- price (numeric), user_id (bigint), user_session (uuid)

**dim_products** — one row per product_id
- product_id, brand, category (parsed from category_code), price_band
- price_band buckets: <$50, $50–$200, $200–$500, >$500

**dim_users** — one row per user_id, derived from raw_events
- user_id, first_seen (MIN(event_time)), first_purchase (MIN event_time WHERE event_type='purchase')
- cohort_week (DATE_TRUNC('week', first_seen))
- This derivation is the core modeling work — first_seen and cohort_week do not exist in raw data

**fct_sessions** — one row per user_session
- session_id (user_session), user_id, start (MIN event_time in session)
- duration (MAX - MIN event_time), events (count), converted (bool: any purchase in session)

**fct_events** — cleaned raw_events with FK references
- All raw_events columns + FK to dim_products, dim_users, fct_sessions

### Cleaning Decisions (to be logged in schema.md)
- Sessions spanning midnight: document the count, decide whether to split or keep
- Missing category_code: document % null, keep rows (brand/price still useful)
- Price = 0: document count, exclude from revenue calculations
- Duplicate events: after profiling, define a threshold based on what you find — a reasonable starting point is same user_id + product_id + event_type within 1 second; adjust if the data shows a different pattern

---

## docs/guide.md — Content Spec

### Week 1: Foundation (Days 1–5)

**Days 1–2: Load**
- Prerequisites: Postgres installed locally, Python packages (psycopg2 or SQLAlchemy, pandas)
- How to run load.py and what output to expect (row count, time taken)
- How to run profile.py and what to look for in each check
- Cleaning decisions checklist: what to document and where (schema.md)

**Days 3–5: Model**
- How to run 01_schema.sql to create tables
- How to run build_dims.py — explain the derivation logic for dim_users
- First window function queries to write:
  - ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY event_time) — event order within session
  - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) — time between user events
- Deliverable check: 5 working queries, clean schema

### Week 2: Analysis (Days 6–12)

**Days 6–8: Funnel (02_funnel.sql)**
- How to write a CTE-based funnel query using conditional aggregation
- SQL pattern: CASE WHEN event_type = 'purchase' THEN 1 END inside COUNT()
- What to look for: where is the biggest drop-off?
- Slices to try: by price_band, by brand, by day of week (EXTRACT(DOW FROM event_time))
- Link to concepts: Funnel Analysis, CTEs + Conditional Aggregation

**Days 9–10: Cohorts (03_cohorts.sql)**
- How to build weekly cohort table from dim_users
- How to compute repeat-purchase rate at D7/D30/D60
- How to read a cohort heatmap (rows = cohort week, columns = days since first event)
- Link to concepts: Cohort Analysis

**Days 11–12: Retention + Segments (04_retention.sql, 05_segments.sql)**
- Return-visit curves: % of users back at each time interval
- Key query: which first purchase price band predicts a second purchase? (the best finding candidate)
- ARPU by segment: revenue / distinct users, grouped by price_band or category
- Revenue concentration: what % of users drive what % of revenue
- Deliverable check: one sentence you didn't know on day 1, supported by a query result

### Week 3: Package (Days 13–21)

**Days 13–15: Metrics Framework**
- North Star: Repeat Purchase Rate within 90 days
  - Why this one: honest about electronics' weakness, directly actionable, not gameable
  - Alternative candidates considered: conversion rate (too generic), ARPU (inflatable by one big purchase)
- Supporting metrics: funnel conversion rate, AOV, ARPU per cohort, session depth

**Days 16–18: README**
- Template (fill in with your actual numbers):
  ```
  ## Business Question
  [One sentence: what did you set out to find?]

  ## Data
  [Dataset, size, date range, event types]

  ## Cleaning Decisions
  [Bullet list: what you dropped, what you kept, why]

  ## Funnel Finding
  [e.g. "Cart-to-purchase conversion is X%. The biggest drop-off is at..."]

  ## Cohort Finding
  [e.g. "D30 repeat-purchase rate is X%. Users from [cohort week] had the highest retention."]

  ## Key Insight
  [One sentence finding: e.g. "Users whose first purchase was under $50 return at 2.3× the rate of users whose first purchase was over $200."]

  ## Recommendation
  [What should this company change? One concrete action tied to the finding.]

  ## Limitations
  [Electronics has low repeat rates by nature. Dataset is ~5 months. No demographic data.]
  ```

**Days 19–21: Tableau (optional)**
- Three views to build: funnel bar chart, cohort heatmap, segment revenue breakdown
- How to publish to Tableau Public and link from README
- Skip if behind — Parts 1–4 are what matter for the portfolio

---

## docs/concepts.md — Content Spec

Format for each entry: **What it is** (2–3 sentences) + **How it applies in this project** (1–2 sentences) + link to the relevant SQL file.

Concepts to cover (10 total):

1. **Funnel Analysis** — measuring drop-off at each stage of a user journey. In this project: view → cart → purchase. Links to 02_funnel.sql.
2. **Session Definition** — grouping user events into a single visit. In this project: user_session is pre-defined. Edge case: sessions spanning midnight.
3. **Cohort Analysis** — grouping users by first-seen week and tracking behavior over time. In this project: weekly cohorts, repeat-purchase rate at D7/D30/D60. Links to 03_cohorts.sql.
4. **Retention Curves** — % of users who return at each time interval after first event. In this project: low retention is expected (electronics) and is itself a finding. Links to 04_retention.sql.
5. **Window Functions** — SQL functions that compute across a set of rows without collapsing them. Three used: ROW_NUMBER(), LAG(), SUM() OVER(). Each gets a short SQL snippet from the actual schema.
6. **CTEs + Conditional Aggregation** — WITH clauses for readable multi-step queries; CASE WHEN inside aggregates to pivot event types into columns. Example from 02_funnel.sql.
7. **ARPU / AOV** — Average Revenue Per User vs Average Order Value. Difference: AOV is per transaction, ARPU is per user over a period. Links to 05_segments.sql.
8. **Price Band Segmentation** — bucketing a continuous price variable into ordinal groups (<$50, $50–$200, etc.) to enable group-level comparison. Why it matters: continuous price makes GROUP BY useless; bands reveal behavioral patterns.
9. **Revenue Concentration** — what % of users account for what % of revenue (Pareto principle). In this project: electronics often has extreme concentration. Revealing this justifies a targeted retention recommendation.
10. **North Star Metric** — the single metric that best captures long-term product health. In this project: you'll choose and justify yours in Week 3. Candidate analysis included.

---

## docs/schema.md — Content Spec

1. ER diagram in ASCII showing relationships between all 5 tables
2. Full column list for each table with types and nullable flags
3. dim_users derivation walkthrough (how first_seen and cohort_week are computed)
4. price_band bucket definitions
5. Cleaning decisions log — one entry per decision, format: `[column] [issue] [count/% affected] [decision] [reason]`
6. FK relationship table

---

## Constraints

- No Docker, no S3, no PySpark — local Postgres only
- No pandas groupby as a substitute for SQL aggregation — analysis happens in SQL
- No Claude attribution in git commits
- All code written by the user

---

## Success Criteria

- README reads as a business document, not a technical walkthrough
- At least one finding that is a specific, defensible sentence with a number in it
- SQL uses window functions, CTEs, conditional aggregation — not just SELECT + GROUP BY
- Cleaning decisions are documented, not silently applied
- The recommendation is tied directly to a finding
