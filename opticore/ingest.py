"""Schema-tolerant ingestion. Principle: nothing is dropped silently.
rows_in == loaded + duplicates + quarantined, asserted for every file."""
import re, json, sqlite3, pathlib, pandas as pd
SYN = {"serial": {"serial", "serial_number", "sn", "unit_id"},
       "station": {"station", "station_id", "bench", "stn"},
       "value": {"mtf50", "mtf_50", "mtf", "mtf50_pct"},
       "ts": {"ts", "timestamp", "date", "time"}}
LO, HI = 0.05, 0.95   # physically plausible MTF50 after unit normalisation

def norm_station(x):
    if x is None or (isinstance(x, float) and x != x): return None
    m = re.search(r"(\d+)", str(x)); return f"ST{int(m.group(1)):02d}" if m else None

def map_columns(cols):
    out, pct = {}, False
    for c in cols:
        k = c.strip().lower()
        for canon, names in SYN.items():
            if k in names: out[c] = canon; pct = pct or (canon == "value" and k.endswith("_pct"))
    if set(out.values()) != set(SYN): raise ValueError(f"unmapped schema: {list(cols)}")
    return out, pct

def parse_ts(s):
    if pd.api.types.is_numeric_dtype(s): return pd.to_datetime(s, unit="s", errors="coerce")
    return pd.to_datetime(s, format="mixed", errors="coerce")

def ingest_file(path, con):
    path = pathlib.Path(path); raw = pd.read_csv(path); n_in = len(raw)
    try: cmap, pct = map_columns(raw.columns)
    except ValueError as e:
        con.execute("INSERT INTO quarantine VALUES (?,?,?)", (path.name, "unmapped_schema", str(e)))
        return dict(file=path.name, rows_in=n_in, loaded=0, dup=0, quarantined=n_in, schema_error=True)
    df = raw.rename(columns=cmap).copy()
    df["station"] = df.station.map(norm_station); df["ts"] = parse_ts(df.ts)
    df["value"] = pd.to_numeric(df.value, errors="coerce") / (100 if pct else 1)
    reason = pd.Series("", index=df.index)
    reason[df.serial.isna()] = "missing_serial"
    reason[(reason == "") & df.station.isna()] = "missing_station"
    reason[(reason == "") & df.ts.isna()] = "bad_timestamp"
    reason[(reason == "") & ~df.value.between(LO, HI)] = "out_of_range"
    for i in df.index[reason != ""]:
        con.execute("INSERT INTO quarantine VALUES (?,?,?)", (path.name, reason[i], raw.loc[i].to_json()))
    good = df[reason == ""]; dedup = good.drop_duplicates(["serial", "station", "ts"])
    out = dedup.assign(metric="mtf50", source_file=path.name)[["serial", "station", "metric", "value", "ts", "source_file"]].copy()
    out["ts"] = out.ts.astype(str); out.to_sql("measurements", con, if_exists="append", index=False)
    r = dict(file=path.name, rows_in=n_in, loaded=len(dedup), dup=len(good) - len(dedup), quarantined=int((reason != "").sum()))
    assert r["rows_in"] == r["loaded"] + r["dup"] + r["quarantined"], f"silent row loss in {path.name}"
    return r

def run(raw_dir="data/raw", db="data/warehouse.db"):
    pathlib.Path(db).unlink(missing_ok=True); con = sqlite3.connect(db)
    con.execute("CREATE TABLE quarantine(source_file, reason, raw)")
    reports = [ingest_file(p, con) for p in sorted(pathlib.Path(raw_dir).glob("*.csv"))]
    con.commit(); con.close(); return reports

if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
