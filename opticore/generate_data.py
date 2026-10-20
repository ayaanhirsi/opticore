"""Synthetic MR-optics test data with the failure modes the real world has:
inconsistent station names, schema drift, unit changes, missing metadata,
duplicates, and instrument bias/drift. Ground truth is known, so every
analytic can be validated against it."""
import numpy as np, pandas as pd, pathlib
START = pd.Timestamp("2026-07-01")
DAYS, PER_DAY = 90, 40
BIAS_STATION, DRIFT_STATION, DRIFT_START, DRIFT_RATE = 5, 3, 40, 0.0004

def generate(out="data/raw", seed=7):
    rng = np.random.default_rng(seed); out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    gold = rng.normal(0.42, 0.02, 10); rows = []
    for s in range(1, 9):
        for d in range(DAYS):
            bias = 0.015 if s == BIAS_STATION else 0.0
            drift = DRIFT_RATE * max(0, d - DRIFT_START) if s == DRIFT_STATION else 0.0
            n = PER_DAY
            ts = START + pd.to_timedelta(d * 86400 + rng.integers(0, 86400, n), unit="s")
            v = rng.normal(0.42, 0.02, n) + bias + drift + rng.normal(0, 0.006, n)
            rows += [(f"U{s}{d:03d}{i:02d}", s, v[i], ts[i]) for i in range(n)]
            if d % 7 == 0:  # weekly golden-unit check on every station
                gv = gold + bias + drift + rng.normal(0, 0.006, 10)
                rows += [(f"GOLD-{g:02d}", s, gv[g], START + pd.Timedelta(days=d, hours=6)) for g in range(10)]
    df = pd.DataFrame(rows, columns=["serial", "st", "mtf50", "ts"])
    names = {1: ["ST01", "st-01"], 2: ["ST02", "Station_2"], 3: ["st03", "STN 3"], 4: ["ST04", "stn-4"],
             5: ["ST05", "st_5"], 6: ["ST06", "Station 6"], 7: ["BENCH-7", "bench7"], 8: ["Bench_08", "BENCH 8"]}
    def messy(s): return names[s][rng.integers(0, 2)]
    a = df[df.st <= 3]; cut = START + pd.Timedelta(days=45)
    for tag, part, cols in [("a_early", a[a.ts < cut], ["serial", "station", "mtf50", "ts"]),
                            ("a_late", a[a.ts >= cut], ["serial_number", "station_id", "MTF_50", "timestamp"])]:
        pd.DataFrame({cols[0]: part.serial, cols[1]: [messy(s) for s in part.st], cols[2]: part.mtf50.round(5),
                      cols[3]: part.ts.dt.strftime("%Y-%m-%dT%H:%M:%S")}).to_csv(out / f"factory_{tag}.csv", index=False)
    b = df[(df.st >= 4) & (df.st <= 6)]
    epoch = (b.ts - pd.Timestamp("1970-01-01")).dt.total_seconds().astype("int64")
    pd.DataFrame({"unit_id": b.serial, "station_id": [messy(s) for s in b.st], "mtf50_pct": (b.mtf50 * 100).round(3),
                  "timestamp": epoch}).to_csv(out / "factory_b.csv", index=False)
    c = df[df.st >= 7]
    st = [messy(s) for s in c.st]; st = [None if rng.random() < 0.03 else x for x in st]
    pd.DataFrame({"SN": c.serial, "bench": st, "mtf": c.mtf50.round(5), "date": c.ts.dt.strftime("%m/%d/%Y %H:%M")}
                 ).to_csv(out / "lab_bench.csv", index=False)
    for f in out.glob("*.csv"):  # inject defects: duplicates, missing serials, unit-error values
        t = pd.read_csv(f); dup = t.sample(frac=0.01, random_state=1); t = pd.concat([t, dup], ignore_index=True)
        t.loc[t.sample(frac=0.005, random_state=2).index, t.columns[0]] = None
        vc = t.columns[2]; t.loc[t.sample(frac=0.003, random_state=3).index, vc] *= 100
        t.to_csv(f, index=False)
    parts = rng.normal(0.42, 0.02, 10); op = rng.normal(0, 0.003, 3); g = []
    for p in range(10):
        for o in range(3):
            for t in range(3): g.append((f"P{p:02d}", f"OP{o+1}", t + 1, parts[p] + op[o] + rng.normal(0, 0.004)))
    pd.DataFrame(g, columns=["part", "operator", "trial", "value"]).to_csv(out.parent / "grr_study.csv", index=False)

if __name__ == "__main__":
    generate()
