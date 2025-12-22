from pathlib import Path
import sys
from datetime import date

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from optimizer_core import build_latest_assignments_df, update_assignment_history_csv

def main():
    # Update snapshot
    latest = build_latest_assignments_df()
    latest_path = REPO_ROOT / "latest_assignments.csv"
    latest.to_csv(latest_path, index=False)
    print(f"[OK] Wrote {latest_path} ({len(latest)} rows)")

    # Update history for today's date
    combined = update_assignment_history_csv(date.today())
    hist_path = REPO_ROOT / "assignment_history.csv"
    print(f"[OK] Updated {hist_path} ({len(combined)} total rows)")

if __name__ == "__main__":
    main()