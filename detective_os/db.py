"""DETECTIVE OS — persistence: SQLite schema (D1-compatible subset).

14 tables per spec. Versioning rule: rows are never overwritten in
place. An update inserts a new version row (version+1, supersedes the
old id) and writes an audit_logs entry. Every reasoning run records
which evidence, model, prompt version and output it used, so any
analysis can be replayed and any overturned judgment traced.
"""
from __future__ import annotations

import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT,
  description TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT, case_id TEXT, version INTEGER DEFAULT 1,
  title TEXT, publisher TEXT, author TEXT, published_at TEXT,
  url TEXT, source_type TEXT, accessible INTEGER DEFAULT 1,
  is_reprint INTEGER DEFAULT 0, reprint_of TEXT, origin_url TEXT,
  reliability TEXT, last_verified TEXT, notes TEXT,
  superseded_by TEXT, PRIMARY KEY (source_id, version)
);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT, case_id TEXT, version INTEGER DEFAULT 1,
  content TEXT, evidence_type TEXT, source_id TEXT,
  original_quote TEXT, source_location TEXT,
  publication_date TEXT, event_date TEXT, grade TEXT,
  reliability_assessment TEXT, verification_status TEXT,
  supports TEXT, contradicts TEXT, analyst_notes TEXT,
  superseded_by TEXT, PRIMARY KEY (evidence_id, version)
);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT, case_id TEXT, version INTEGER DEFAULT 1,
  title TEXT, time_kind TEXT, time_label TEXT,
  earliest TEXT, latest TEXT, persons TEXT, places TEXT,
  evidence_ids TEXT, notes TEXT,
  superseded_by TEXT, PRIMARY KEY (event_id, version)
);
CREATE TABLE IF NOT EXISTS persons (
  person_id TEXT, case_id TEXT, name TEXT, role TEXT,
  is_suspect INTEGER DEFAULT 0, suspect_basis TEXT,
  suspect_basis_grade TEXT, notes TEXT,
  PRIMARY KEY (person_id, case_id)
);
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT, case_id TEXT, kind TEXT, name TEXT,
  is_suspect INTEGER DEFAULT 0, suspect_basis TEXT,
  suspect_basis_grade TEXT, notes TEXT,
  PRIMARY KEY (entity_id, case_id)
);
CREATE TABLE IF NOT EXISTS relationships (
  id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT,
  from_id TEXT, to_id TEXT, relation TEXT,
  source_id TEXT, evidence_id TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS hypotheses (
  hypothesis_id TEXT, case_id TEXT, version INTEGER DEFAULT 1,
  description TEXT, supports TEXT, opposes TEXT, unexplained TEXT,
  prerequisites TEXT, predictions TEXT, falsifiers TEXT,
  prior REAL, likelihoods TEXT, status TEXT,
  superseded_by TEXT, PRIMARY KEY (hypothesis_id, version)
);
CREATE TABLE IF NOT EXISTS hypothesis_evidence (
  hypothesis_id TEXT, evidence_id TEXT, case_id TEXT,
  link_type TEXT, PRIMARY KEY (hypothesis_id, evidence_id, link_type)
);
CREATE TABLE IF NOT EXISTS contradictions (
  contradiction_id TEXT, case_id TEXT, version INTEGER DEFAULT 1,
  ctype TEXT, evidence_ids TEXT, source_ids TEXT,
  quote_a TEXT, quote_b TEXT, wording_a TEXT, wording_b TEXT,
  could_be_drift TEXT, needs_what TEXT,
  resolvable_now INTEGER DEFAULT 0, resolution TEXT,
  superseded_by TEXT, PRIMARY KEY (contradiction_id, version)
);
CREATE TABLE IF NOT EXISTS investigation_tasks (
  task_id TEXT, case_id TEXT, question TEXT, purpose TEXT,
  hypotheses TEXT, expected_info TEXT, impact_if_yes TEXT,
  impact_if_no TEXT, source_or_channel TEXT,
  estimated_value TEXT, status TEXT DEFAULT 'open',
  PRIMARY KEY (task_id, case_id)
);
CREATE TABLE IF NOT EXISTS investigation_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, case_id TEXT,
  result TEXT, evidence_ids TEXT, recorded_at TEXT
);
CREATE TABLE IF NOT EXISTS reasoning_runs (
  run_id TEXT PRIMARY KEY, case_id TEXT, run_at TEXT,
  model TEXT, prompt_version TEXT, evidence_ids TEXT,
  output_json TEXT, verdict TEXT, superseded_run_id TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT,
  actor TEXT, action TEXT, target_type TEXT, target_id TEXT,
  old_version INTEGER, new_version INTEGER, detail TEXT,
  recorded_at TEXT
);
"""

TABLES_14 = ["cases", "sources", "evidence", "events", "persons",
             "entities", "relationships", "hypotheses",
             "hypothesis_evidence", "contradictions",
             "investigation_tasks", "investigation_results",
             "reasoning_runs", "audit_logs"]


def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def table_list(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def audit(conn, case_id, actor, action, target_type, target_id, detail="",
          old_version=None, new_version=None, recorded_at=""):
    conn.execute(
        "INSERT INTO audit_logs (case_id, actor, action, target_type, target_id,"
        " old_version, new_version, detail, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (case_id, actor, action, target_type, target_id,
         old_version, new_version, detail, recorded_at))
    conn.commit()


def record_run(conn, run_id, case_id, run_at, model, prompt_version,
               evidence_ids, output, verdict, superseded_run_id=""):
    conn.execute(
        "INSERT INTO reasoning_runs (run_id, case_id, run_at, model, prompt_version,"
        " evidence_ids, output_json, verdict, superseded_run_id)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id, case_id, run_at, model, prompt_version,
         json.dumps(evidence_ids, ensure_ascii=False),
         json.dumps(output, ensure_ascii=False), verdict, superseded_run_id))
    conn.commit()
