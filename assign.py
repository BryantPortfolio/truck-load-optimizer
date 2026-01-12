from datetime import date
from pathlib import Path
import pandas as pd

from optimizer_core import build_latest_assignments_df, update_assignment_history_csv

REPO_ROOT = Path(__file__).resolve().parent

def main():
    # latest snapshot
    latest = build_latest_assignments_df()
    latest.to_csv(REPO_ROOT / "latest_assignments.csv", index=False)

    # history (today appended)
    update_assignment_history_csv(date.today())

if __name__ == "__main__":
    main()
