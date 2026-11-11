-- DETECTIVE OS auto-run jobs (D1). Applied with:
--   python3 scripts/cf.py d1 execute detective-os-jobs --file scripts/schema.sql
-- Jobs are created by the Pages Function POST /api/investigate and
-- driven by the runner (agent + pipeline); the frontend polls
-- GET /api/jobs?id=<job_id> for status and results.
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  direction TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'zh',
  region TEXT NOT NULL DEFAULT '',
  hints TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'queued',
  stage TEXT NOT NULL DEFAULT 'queued',
  stage_note TEXT NOT NULL DEFAULT '',
  result_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
