import sqlite3, numpy as np, pandas as pd
LSL, USL = 0.35, 0.50

def load(db="data/warehouse.db"):
    return pd.read_sql("SELECT * FROM measurements", sqlite3.connect(db), parse_dates=["ts"])

def cpk(x, lsl=LSL, usl=USL):
    m, s = np.mean(x), np.std(x, ddof=1); return min(usl - m, m - lsl) / (3 * s)

def gauge_rr(df):
    """Crossed ANOVA Gauge R&R (AIAG). Returns variance components, %GRR (study var), ndc."""
    p, o = df.part.nunique(), df.operator.nunique(); r = len(df) // (p * o); g = df.value.mean()
    pm, om = df.groupby("part").value.mean(), df.groupby("operator").value.mean()
    cm = df.groupby(["part", "operator"]).value.mean()
    ssp, sso = o * r * ((pm - g) ** 2).sum(), p * r * ((om - g) ** 2).sum()
    ssi = r * ((cm - g) ** 2).sum() - ssp - sso
    sse = ((df.value - df.groupby(["part", "operator"]).value.transform("mean")) ** 2).sum()
    msp, mso, msi, mse = ssp / (p - 1), sso / (o - 1), ssi / ((p - 1) * (o - 1)), sse / (p * o * (r - 1))
    rep = mse; inter = max((msi - mse) / r, 0); oper = max((mso - msi) / (p * r), 0); part = max((msp - msi) / (o * r), 0)
    grr = rep + oper + inter; tot = grr + part
    return dict(repeatability=rep, reproducibility=oper + inter, part=part, pct_grr=100 * np.sqrt(grr / tot),
                ndc=int(1.41 * np.sqrt(part / grr)))

def golden_correlation(df):
    """Station-to-station: each station's golden-unit readings vs. cross-station consensus."""
    g = df[df.serial.str.startswith("GOLD")]
    pv = g.groupby(["serial", "station"]).value.mean().unstack()
    cons = pv.mean(axis=1); out = {}
    for s in pv:
        slope, _ = np.polyfit(cons, pv[s], 1); out[s] = dict(offset=(pv[s] - cons).mean(), slope=slope, r=np.corrcoef(cons, pv[s])[0, 1])
    t = pd.DataFrame(out).T; dev = (t.offset - t.offset.median()).abs()
    t["bias_flag"] = dev > 3 * 1.4826 * dev.median(); return t

def cusum_alarm(x, mu, sd, start, k=0.5, h=8.0):
    """Tabular CUSUM on daily means vs. a frozen baseline (mu, sd). Returns first alarm index or None."""
    hi = lo = 0.0
    for i in range(start, len(x)):
        z = (x[i] - mu) / sd; hi = max(0, hi + z - k); lo = max(0, lo - z - k)
        if hi > h or lo > h: return i
    return None

def drift_scan(df, base_n=28):
    """Per-station CUSUM; sigma is pooled across stations' baseline windows (more stable than 1 station's 14-28 points)."""
    prod = df[~df.serial.str.startswith("GOLD")].copy(); prod["day"] = prod.ts.dt.floor("D")
    daily = {s: g.groupby("day").value.mean() for s, g in prod.groupby("station")}
    sd = np.sqrt(np.mean([d.values[:base_n].var(ddof=1) for d in daily.values()])); res = {}
    for s, d in daily.items():
        i = cusum_alarm(d.values, d.values[:base_n].mean(), sd, base_n)
        res[s] = dict(alarm_day=None if i is None else str(d.index[i].date()), alarm_idx=i)
    return pd.DataFrame(res).T
