from pathlib import Path
from optimizer_core import build_latest_assignments_df


OUTPUT = Path("latest_assignments.csv")

def main ():
    df = build_latest_assignments_df()
    df.to_csv(OUTPUT, index=False)
    print(f"[OK] Wrote {OUTPUT.resolve()} ({len(df)} rows)")

if __name__ == "__main__":
    main()