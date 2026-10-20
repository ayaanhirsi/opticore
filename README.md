# OptiCore: Upstream Data Ingestion, Test Analytics and Calibration Agent for Optical Metrology

Prototype of a data-quality layer for MR-headset optical test data (sharpness / MTF50), mirroring the
three pillars of an optical-metrology data team. Built on synthetic data with known ground truth
so every analytic is validated, not just demoed.

## What it does
1. **Ingestion** (`ingest.py`): 4 differently shaped feeds (factory A with mid-quarter column rename, factory B in
   percent units + epoch time, lab benches with US dates and missing station metadata) -> one schema.
   Station-name normalisation, unit normalisation, range validation, dedup, quarantine table with reasons.
   Invariant asserted per file: `rows_in == loaded + duplicates + quarantined` (no silent loss).
2. **Production-test analytics** (`analytics.py`): ANOVA Gauge R&R (repeatability / reproducibility / %GRR / ndc),
   Cpk per station, station-to-station correlation via golden units (offset, slope, r), CUSUM drift detection.
3. **Calibration agent** (`calibration.py`): instrument system of record (SQLite), certification-due tracking,
   ticket creation with duplicate suppression and proposed service slot, LLM tool schemas
   (`TOOLS`) so any tool-calling model can drive it; deterministic planner by default (testable offline).
   Analytics alerts (bias/drift) automatically open maintenance tickets.

## Run
    python3 run_all.py            # generate data, ingest, analyse, open tickets, write report.png
    python3 -m unittest tests.test_core

## Known limitations (honest)
- Synthetic data; real feeds need a schema registry with versioning and an LLM-assisted mapping proposal step.
- CUSUM threshold trades detection delay for false alarms (h=5 gave 2 false alarms in 8 stations x 62 days; h=8 gave none, ~16 day delay on 0.0004/day drift).
- Golden-unit bias averages over the whole window, so a drifting station (ST03) is also flagged by it.
