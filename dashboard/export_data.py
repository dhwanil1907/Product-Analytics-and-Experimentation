"""
Export all dashboard query results to dashboard/data/*.csv.
Run once so the dashboard can work without a live DB (e.g. Streamlit Cloud).

Usage: python dashboard/export_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries as q

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def export(name: str, df_fn):
    df = df_fn()
    out = DATA_DIR / f"{name}.csv"
    df.to_csv(out, index=False)
    print(f"  {name}.csv  ({len(df)} rows)")


if __name__ == "__main__":
    print(f"Exporting to {DATA_DIR}/")
    export("overview",             q.get_overview)
    export("funnel_overall",       q.get_funnel_overall)
    export("funnel_by_price_band", q.get_funnel_by_price_band)
    export("funnel_by_dow",        q.get_funnel_by_dow)
    export("cohorts",              q.get_cohorts)
    export("repeat_rates",         q.get_repeat_rates)
    export("buyer_activity",       q.get_buyer_activity)
    export("arpu_by_band",         q.get_arpu_by_band)
    export("arpu_by_category",     q.get_arpu_by_category)
    export("quintiles",            q.get_quintiles)
    print("Done.")
