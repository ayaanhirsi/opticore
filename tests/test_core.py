import unittest, numpy as np, pandas as pd, tempfile
from opticore import ingest, analytics as A
class T(unittest.TestCase):
    def test_station_names(self):
        for x in ["st-01", "Station_1", "STN 1", "BENCH-1", "ST01"]: self.assertEqual(ingest.norm_station(x), "ST01")
        self.assertIsNone(ingest.norm_station("lab")); self.assertIsNone(ingest.norm_station(None))
    def test_schema_drift_and_unknown(self):
        self.assertEqual(set(ingest.map_columns(["serial_number", "station_id", "MTF_50", "timestamp"])[0].values()), set(ingest.SYN))
        self.assertTrue(ingest.map_columns(["unit_id", "station_id", "mtf50_pct", "timestamp"])[1])
        with self.assertRaises(ValueError): ingest.map_columns(["a", "b", "c"])
    def test_no_silent_loss(self):
        d = tempfile.mkdtemp(); pd.DataFrame({"serial": ["a", "a", None, "c"], "station": ["st-1"] * 3 + [None], "mtf50": [.4, .4, .4, 40], "ts": ["2026-01-01"] * 4}).to_csv(f"{d}/x.csv", index=False)
        r = ingest.run(d, f"{d}/w.db")[0]; self.assertEqual((r["loaded"], r["dup"], r["quarantined"]), (1, 1, 2))
    def test_grr_recovers_truth(self):
        rng = np.random.default_rng(0); rows = []; parts = rng.normal(0, .02, 10); ops = rng.normal(0, .003, 3)
        for p in range(10):
            for o in range(3):
                for t in range(3): rows.append((p, o, parts[p] + ops[o] + rng.normal(0, .004)))
        r = A.gauge_rr(pd.DataFrame(rows, columns=["part", "operator", "value"])); self.assertAlmostEqual(r["repeatability"] ** .5, .004, delta=.001)
    def test_cusum(self):
        rng = np.random.default_rng(1); x = rng.normal(0, 1, 60); self.assertIsNone(A.cusum_alarm(x[:40], 0, 1, 14, h=8)); x[30:] += 2; self.assertLess(A.cusum_alarm(x, 0, 1, 14) - 30, 6)
if __name__ == "__main__": unittest.main()
