# Data Schema

Tables, relationships, column definitions, and every cleaning decision made during profiling.

---

## Entity-Relationship Diagram

```
raw_events
├── event_time       (timestamptz)
├── event_type       (text)
├── product_id  ─────────────────────────── dim_products.product_id
├── category_id      (bigint)
├── category_code    (text, nullable)
├── brand            (text, nullable)
├── price            (numeric)
├── user_id     ─────────────────────────── dim_users.user_id
└── user_session ────────────────────────── fct_sessions.session_id


dim_products                    dim_users
├── product_id (PK)             ├── user_id (PK)
├── brand                       ├── first_seen
├── category                    ├── first_purchase (nullable)
└── price_band                  └── cohort_week
         │                               │
         └──────────┬────────────────────┘
                    │
               fct_events
               ├── (all raw_events columns)
               ├── FK → dim_products.product_id
               ├── FK → dim_users.user_id
               └── FK → fct_sessions.session_id


fct_sessions
├── session_id (PK)   = user_session from raw_events
├── user_id
├── session_start
├── session_duration  (interval)
├── event_count
└── converted         (boolean)
```

**Relationship summary:**
- One `dim_products` row → many `raw_events` / `fct_events` rows
- One `dim_users` row → many `raw_events` / `fct_events` rows, one `fct_sessions` row per session
- One `fct_sessions` row → many `fct_events` rows
- `fct_events` is `raw_events` cleaned and FK-linked — the table you query for analysis

---

## Table Definitions

### raw_events

Loaded directly from the Kaggle CSV. No transformations applied.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| event_time | timestamptz | NO | UTC timestamps |
| event_type | text | NO | 'view', 'cart', or 'purchase' |
| product_id | bigint | NO | |
| category_id | bigint | NO | opaque identifier |
| category_code | text | YES | dot-separated hierarchy e.g. `electronics.telephone.telephone` |
| brand | text | YES | lowercase brand name |
| price | numeric | NO | in USD; some values are 0 |
| user_id | bigint | NO | |
| user_session | uuid | NO | pre-defined session identifier |

---

### dim_products

One row per `product_id`. Derived from `raw_events`.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| product_id | bigint | NO | PK |
| brand | text | YES | from raw_events; NULL if never observed with a brand |
| category | text | YES | first segment of category_code (e.g. 'electronics'); NULL if category_code always null for this product |
| price_band | text | NO | derived — see price band logic below |

**Price band logic:**

| Band | Condition |
|------|-----------|
| `under_50` | price < 50 |
| `50_to_200` | 50 ≤ price < 200 |
| `200_to_500` | 200 ≤ price < 500 |
| `over_500` | price ≥ 500 |

Price band is assigned using the most recent non-zero price observed for each product. Products with only zero-price events are excluded from `dim_products`.

---

### dim_users

One row per `user_id`. Fully derived from `raw_events` — none of these columns exist in the source data.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| user_id | bigint | NO | PK |
| first_seen | timestamptz | NO | `MIN(event_time)` across all events for this user |
| first_purchase | timestamptz | YES | `MIN(event_time)` where `event_type = 'purchase'`; NULL if user never purchased |
| cohort_week | date | NO | `DATE_TRUNC('week', first_seen)` — the Monday of the user's first week |

**Derivation note:** `cohort_week` uses `DATE_TRUNC('week', ...)` which returns the Monday. This means all users who first appeared Mon–Sun of the same week share a cohort. This is the standard weekly cohort definition.

---

### fct_sessions

One row per `user_session`. Derived from `raw_events`.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| session_id | uuid | NO | PK — same as `user_session` in raw_events |
| user_id | bigint | NO | FK → dim_users |
| session_start | timestamptz | NO | `MIN(event_time)` in the session |
| session_duration | interval | NO | `MAX(event_time) - MIN(event_time)` in the session |
| event_count | integer | NO | total events in the session |
| converted | boolean | NO | TRUE if any event in the session has `event_type = 'purchase'` |

---

### fct_events

Cleaned version of `raw_events` with FK columns added. This is the primary table for analysis queries.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| event_time | timestamptz | NO | |
| event_type | text | NO | |
| product_id | bigint | NO | FK → dim_products |
| category_id | bigint | NO | |
| category_code | text | YES | |
| brand | text | YES | |
| price | numeric | NO | |
| user_id | bigint | NO | FK → dim_users |
| user_session | uuid | NO | FK → fct_sessions |

Rows excluded from `fct_events`: duplicate events (see cleaning decisions below).

---

## Cleaning Decisions Log

Fill this in as you run `etl/profile.py`. One row per decision. If you find an issue not listed here, add it.

| # | Column / Issue | What you found | Count / % affected | Decision | Reason |
|---|---------------|---------------|-------------------|---------|--------|
| 1 | `category_code` nulls | Many products have no category_code | TBD after profiling | Keep rows — brand and price still usable for segmentation | Dropping these rows would remove valid funnel and revenue data |
| 2 | `brand` nulls | Some products have no brand | TBD after profiling | Keep rows | Product_id and price are still valid |
| 3 | `price = 0` | Some events have zero price | TBD after profiling | Exclude from revenue calculations (funnel counts still valid) | Zero-price purchases inflate conversion metrics but understate revenue |
| 4 | Duplicate events | Same user + product + event_type within 1 second | TBD after profiling | Remove duplicates; keep one row | Likely double-fire from the tracking system |
| 5 | Sessions spanning midnight | Sessions where MIN(event_time)::date ≠ MAX(event_time)::date | TBD after profiling | Keep as single session | Splitting would misattribute the session's purchase to a different calendar day; the user_session id already defines the boundary |
| 6 | `price < 0` | Negative prices (if any) | TBD after profiling | Exclude from all calculations | Likely data errors; negative revenue is not meaningful |

**Instructions:** Replace each "TBD after profiling" with the actual count and % after running `etl/profile.py`.

---

## FK Relationship Table

| From table | Column | To table | Column | Relationship |
|-----------|--------|---------|--------|-------------|
| fct_events | product_id | dim_products | product_id | many-to-one |
| fct_events | user_id | dim_users | user_id | many-to-one |
| fct_events | user_session | fct_sessions | session_id | many-to-one |
| fct_sessions | user_id | dim_users | user_id | many-to-one |

Note: `raw_events` has no FK constraints by design — it is the raw source table. FKs are enforced on `fct_events` only.
