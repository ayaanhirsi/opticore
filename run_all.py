import datetime as dt, json, pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from opticore import generate_data, ingest, analytics as A, calibration as C
generate_data.generate(); rep = ingest.run()
tot = {k: sum(r[k] for r in rep) for k in ("rows_in", "loaded", "dup", "quarantined")}
df = A.load(); as_of = df.ts.max().date()
print("INGEST", json.dumps(tot)); import sqlite3
print(pd.read_sql("SELECT reason, COUNT(*) n FROM quarantine GROUP BY reason", sqlite3.connect("data/warehouse.db")).to_string(index=False))
grr = A.gauge_rr(pd.read_csv("data/grr_study.csv")); print("GRR", {k: round(v, 6) if isinstance(v, float) else v for k, v in grr.items()})
prod = df[~df.serial.str.startswith("GOLD")]; print("CPK\n", prod.groupby("station").value.apply(A.cpk).round(2).to_string())
gc = A.golden_correlation(df); print("GOLDEN\n", gc.round(4).to_string()); dr = A.drift_scan(df); print("DRIFT\n", dr.to_string())
alerts = [(s, "bias_vs_golden_consensus") for s in gc.index[gc.bias_flag]] + [(s, "cusum_drift_alarm") for s in dr.index[dr.alarm_idx.notna()]]
C.seed("data/warehouse.db", as_of)
for a, b in C.run_agent("data/warehouse.db", as_of, alerts): print("AGENT", a, b)
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8)); p = prod.assign(day=prod.ts.dt.floor("D"))
for s in ("ST03", "ST05", "ST01"): ax[0].plot(p[p.station == s].groupby("day").value.mean(), label=s)
ax[0].set_title("Daily mean MTF50 by station"); ax[0].legend(); ax[1].bar(gc.index, gc.offset); ax[1].set_title("Golden-unit offset vs consensus")
plt.tight_layout(); plt.savefig("report.png", dpi=110)
