from datetime import date, timedelta
from optimizer_core import backfill_assignment_history_csv

end = date.today()
start = end - timedelta(days=365*2)

df = backfill_assignment_history_csv(
    start_date=start,
    end_date=end,
    n_loads_per_day=60,
    seed=42
)

print("Backfill complete:", len(df), "rows")
