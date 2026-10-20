"""Instrument certification system of record + tool layer for an LLM agent.
The agent loop is planner-agnostic: pass any LLM that emits tool calls; the
default planner is deterministic so behaviour is testable offline."""
import sqlite3, datetime as dt, numpy as np
TOOLS = [
 {"name": "list_due_instruments", "description": "Instruments whose certification is overdue or due within N days.",
  "input_schema": {"type": "object", "properties": {"within_days": {"type": "integer"}}, "required": ["within_days"]}},
 {"name": "open_maintenance_ticket", "description": "Open a ticket and propose a service slot.",
  "input_schema": {"type": "object", "properties": {"instrument_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["instrument_id", "reason"]}},
]
def seed(db, as_of, seed=3):
    rng = np.random.default_rng(seed); con = sqlite3.connect(db)
    con.executescript("DROP TABLE IF EXISTS instruments; DROP TABLE IF EXISTS tickets;"
      "CREATE TABLE instruments(instrument_id, station, last_cert, interval_days, vendor);"
      "CREATE TABLE tickets(instrument_id, reason, opened, proposed_slot);")
    for s in range(1, 9):
        last = as_of - dt.timedelta(days=int(rng.integers(20, 120)))
        con.execute("INSERT INTO instruments VALUES (?,?,?,?,?)", (f"INS-ST{s:02d}", f"ST{s:02d}", last.isoformat(), 90, "VendorA" if s % 2 else "VendorB"))
    con.commit(); con.close()
def list_due(db, as_of, within_days):
    con = sqlite3.connect(db); out = []
    for iid, st, last, iv, v in con.execute("SELECT * FROM instruments"):
        left = (dt.date.fromisoformat(last) + dt.timedelta(days=iv) - as_of).days
        if left <= within_days: out.append(dict(instrument_id=iid, station=st, days_to_due=left, status="OVERDUE" if left < 0 else "DUE_SOON"))
    return sorted(out, key=lambda r: r["days_to_due"])
def open_ticket(db, as_of, instrument_id, reason):
    slot = (as_of + dt.timedelta(days=7)).isoformat(); con = sqlite3.connect(db)
    if con.execute("SELECT 1 FROM tickets WHERE instrument_id=? AND reason=?", (instrument_id, reason)).fetchone(): return dict(status="duplicate_suppressed")
    con.execute("INSERT INTO tickets VALUES (?,?,?,?)", (instrument_id, reason, as_of.isoformat(), slot)); con.commit(); return dict(status="opened", slot=slot)
def run_agent(db, as_of, analytics_alerts=(), within_days=14):
    """Deterministic planner: certification schedule + analytics-triggered (drift/bias) alerts -> tickets."""
    log = []
    for r in list_due(db, as_of, within_days): log.append((r, open_ticket(db, as_of, r["instrument_id"], r["status"].lower())))
    for st, why in analytics_alerts: log.append(({"station": st, "why": why}, open_ticket(db, as_of, f"INS-{st}", why)))
    return log
