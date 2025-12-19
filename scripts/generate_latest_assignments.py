from pathlib import Path
import sys

# Add repo root to Python path so imports work in GitHub Actions
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from optimizer_core import build_latest_assignments_df  # noqa: E402

OUTPUT = REPO_ROOT / "latest_assignments.csv"

def main():
    df = build_latest_assignments_df()
    df.to_csv(OUTPUT, index=False)
    print(f"[OK] Wrote {OUTPUT} ({len(df)} rows)")

if __name__ == "__main__":
    main()
