"""Scheduled refresh (GitHub Actions): recompute everything and save data/snapshot.csv."""
import engine

if __name__ == "__main__":
    df = engine.compute_all(lambda p, m: print(f"{p:.0%} {m}", flush=True))
    engine.save_snapshot(df, "Yahoo Finance")
    print(f"Saved {len(df)} rows")
