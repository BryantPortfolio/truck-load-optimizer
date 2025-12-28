from datetime import date
from optimizer_core import build_latest_assignments_df, backfill_assignment_history, update_assignment_history_csv

def main():
    # always update the latest snapshot
    latest = build_latest_assignments_df()
    latest.to_csv("latest_assignments.csv", index=False)

    # if history doesn't exist yet or is tiny, backfill 2 years
    # (this makes your portfolio look realistic immediately)
    try:
        import pandas as pd
        from pathlib import Path
        p = Path("assignment_history.csv")
        if (not p.exists()) or (p.stat().st_size < 200):  # missing or basically empty
            backfill_assignment_history(end_date=date.today(), days=365*2)
        else:
            update_assignment_history_csv(date.today())
    except Exception:
        # If anything unexpected happens, still at least generate today's row set
        update_assignment_history_csv(date.today())

if __name__ == "__main__":
    main()
