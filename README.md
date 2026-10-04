# Product Analytics and Experimentation

E-commerce behavioural dataset (Kaggle, Sep 2020 – Feb 2021). Raw events loaded into Postgres, cleaned into a star schema, and analysed across funnel, cohort, retention, and revenue segments.

---

## Dataset

| Metric | Value |
|--------|-------|
| Raw events loaded | 885,129 |
| Date range | 2020-09-24 → 2021-02-28 |
| Unique users | 407,283 |
| Unique products | 53,453 |
| Sessions | 490,398 |
| Events after dedup | 884,133 |

---

## Funnel

### Overall (unique users)

| Stage | Users | Conversion |
|-------|-------|------------|
| Viewed at least one product | 406,817 | — |
| Added to cart | 36,948 | 9.08% of viewers |
| Purchased | 21,304 | 57.66% of carters · **5.24% overall** |

### View → Cart by price band

| Price band | Viewers | Cart adders | View→Cart | Cart→Purchase |
|------------|---------|-------------|-----------|---------------|
| under_50 | 202,769 | 15,474 | 7.63% | 62.78% |
| 50_to_200 | 146,132 | 11,754 | 8.04% | 56.36% |
| 200_to_500 | 68,055 | 9,710 | 14.27% | 49.67% |
| over_500 | 19,378 | 1,870 | 9.65% | 50.80% |

Higher-priced items attract more intentional browsers (14.27% view→cart for 200–500) but close at a lower rate.

### View → Purchase by day of week

| Day (0=Mon) | Viewers | Purchasers | View→Purchase |
|-------------|---------|------------|---------------|
| Wednesday | 66,033 | 3,501 | 5.30% |
| Thursday | 65,430 | 3,388 | 5.18% |
| Tuesday | 68,121 | 3,498 | 5.13% |
| Saturday | 63,569 | 3,153 | 4.96% |
| Sunday | 59,477 | 2,958 | 4.97% |

Midweek (Tue–Thu) converts ~0.3 pp better than weekends.

---

## Cohorts

Weekly cohorts; each user assigned to the Monday of their first-seen week.

| Cohort week | Cohort size | D7 rate | D30 rate | D60 rate |
|-------------|-------------|---------|----------|----------|
| 2020-09-21 | 8,115 | 0.65% | 1.05% | 1.22% |
| 2020-09-28 | 16,555 | 0.57% | 0.82% | 0.88% |
| 2020-10-05 | 16,061 | 0.52% | 0.73% | 0.84% |
| 2020-10-12 | 19,220 | 0.53% | 0.73% | 0.76% |
| 2020-10-19 | 20,999 | 0.59% | 0.77% | 0.88% |

All cohorts shown are fully observable through D60 (data extends to 2021-02-28). Retention rates are low in absolute terms — typical for a broad e-commerce catalogue without loyalty mechanics.

---

## Retention

### Repeat purchase rate by first-purchase price band

| First purchase band | First-time buyers | Returned | Repeat rate |
|---------------------|-------------------|----------|-------------|
| 50_to_200 | 6,484 | 2,393 | 36.91% |
| 200_to_500 | 4,701 | 1,699 | 36.14% |
| over_500 | 856 | 279 | 32.59% |
| under_50 | 9,631 | 3,020 | 31.36% |

Users who first buy in the mid-price range (50–500) return at the highest rates.

### Overall buyer activity windows

| Buyers | Active D7 | Active D30 | Active D60 |
|--------|-----------|------------|------------|
| 21,304 | 5.70% | 7.04% | 7.28% |

---

## Revenue Segments

### ARPU by price band

| Price band | Buyers | Total revenue | ARPU |
|------------|--------|---------------|------|
| over_500 | 950 | $959,271 | $1,009.76 |
| 200_to_500 | 4,823 | $2,561,827 | $531.17 |
| 50_to_200 | 6,624 | $1,220,356 | $184.23 |
| under_50 | 9,715 | $383,659 | $39.49 |

### ARPU by top categories

| Category | Buyers | Total revenue | ARPU |
|----------|--------|---------------|------|
| computers | 9,423 | $3,728,836 | $395.72 |
| construction | 560 | $108,682 | $194.08 |
| appliances | 554 | $105,300 | $190.07 |
| auto | 628 | $117,313 | $186.80 |
| electronics | 4,141 | $450,349 | $108.75 |

### Revenue concentration (quintiles)

| Quintile | Users | Revenue | Share |
|----------|-------|---------|-------|
| Top 20% | 4,261 | $3,473,193 | 67.77% |
| 2nd 20% | 4,261 | $1,003,142 | 19.57% |
| 3rd 20% | 4,261 | $406,696 | 7.94% |
| 4th 20% | 4,261 | $172,407 | 3.36% |
| Bottom 20% | 4,260 | $69,676 | 1.36% |

Top 20% of buyers drive 67.8% of revenue.

---

## Recommendation

**Target view-to-cart drop-off, not cart abandonment.**

The cart-to-purchase rate is already strong at 57.7%. The real leakage is earlier: 90.9% of users who view a product never add it to cart. A re-engagement nudge triggered 24h after a product view with no subsequent cart event would move the needle far more than optimising checkout. The 200–500 price band is the best starting point — it already has the highest view-to-cart rate (14.27%), signalling intent, but the lowest cart-to-purchase close rate (49.67%), suggesting price friction is the final barrier. A targeted discount or financing prompt for that segment could close both gaps simultaneously.

---

## Project Structure

```
etl/
  load.py          # Load raw CSV into raw_events
  profile.py       # Data quality checks
  build_dims.py    # Build star schema
sql/
  01_schema.sql    # DDL for all tables
  02_funnel.sql    # Funnel queries
  03_cohorts.sql   # Cohort and repeat-purchase analysis
  04_retention.sql # Buyer activity windows
  05_segments.sql  # Revenue segmentation
docs/
  schema.md        # Table definitions and cleaning decisions log
```

## Setup

```bash
# Requires PostgreSQL 16 and Python 3.x
cp .env.example .env        # set DB_URL=postgresql://localhost/ecommerce
source .venv/bin/activate
python etl/load.py
python etl/build_dims.py
export DB_URL="$(grep '^DB_URL=' .env | cut -d= -f2-)"
psql "$DB_URL" -f sql/02_funnel.sql
psql "$DB_URL" -f sql/03_cohorts.sql
psql "$DB_URL" -f sql/04_retention.sql
psql "$DB_URL" -f sql/05_segments.sql
```
