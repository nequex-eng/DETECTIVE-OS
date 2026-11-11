# Muse cron sync — DETECTIVE OS incremental follow-up (T7)

This is the required one-time update to the existing Muse scheduled task
`detective-os-job-watch`. The GPT code/API contract is implemented in
`functions/api/continue.js`, `functions/api/jobs.js`, and
`scripts/run_job.py`. Do not change the parent job or overwrite old reports.

## Required runner behavior

1. Every 10 minutes run `python3 scripts/job.py poll`. If no queued jobs, exit silently.
2. For each queued ID, run `python3 scripts/job.py get <job_id>`. Only process a job whose status is exactly `queued`. Process one job at a time.
3. Read the complete task JSON, including `parent_job_id`, `intake.source_urls`,
   `intake.user_source_text`, `intake.materials`, `intake.questions`,
   `intake.known_facts`, and `intake.parent_report_context`.
4. Mark only the child task as collecting:
   `python3 scripts/job.py update <job_id> --status collecting --stage collecting --note "正在收集新增来源" --event "开始收集"`.
5. If `parent_job_id` is absent, collect sources for a normal new investigation as usual.
6. If `parent_job_id` is present, this is an incremental continuation:
   - Read the parent task with `python3 scripts/job.py get <parent_job_id>`; require `status=done` and a non-null result.
   - Read the parent report and use its summary/gaps/questions to guide searches.
   - Open every URL in `intake.source_urls` first and collect the actual page text.
   - Treat `intake.user_source_text`, `intake.materials`, and `intake.known_facts` as unverified leads. Search for and inspect the original source independently. Never turn pasted text directly into evidence.
   - Search for additional independent sources addressing `intake.questions` and gaps in the parent report.
   - Write ONLY newly inspected sources and their full texts into the child `runs/<job_id>/collected.json`. Do not copy the parent's old sources into the child file. Temporary IDs may start at S01; `run_job.py` remaps them after the parent's existing source IDs.
   - Preserve provenance, publication dates, canonical URLs, original-source/reprint relationships, and search paths. Reprints do not count as independent origins.
   - If no genuinely new independent source can be collected, record the failed paths and let the mechanical runner fail honestly. Do not mark it done.
7. For both new and follow-up jobs, after writing `collected.json`, run exactly:
   `python3 scripts/run_job.py <job_id>`.
   Do not manually call extract/build/run_draft or write result.json. The script owns extraction, checkpoints, evidence merge, engine/coverage rerun, report versioning, summary, and final KV status.
8. Verify with `python3 scripts/job.py get <job_id>`: require `status=done`, a non-null result, correct `version`, `parent_job_id` (if any), source/fact counts, previous/current verdicts, coverage, and a versioned report path. The parent job must remain unchanged.
9. Report the child task ID, parent task ID, version, newly collected sources, newly extracted facts, total source/fact counts, previous verdict, current verdict, coverage, review blockers, report path, and the full `summary` text. Always label the report an unreviewed draft.

## Non-negotiable safeguards

- Never overwrite the parent task, parent `collected.json`, parent candidate checkpoints, original draft pack, or original report.
- Follow-up versions are append-only: v2, v3, etc. Each version gets its own draft-pack directory and report directory.
- Only new source texts are sent through extraction. Old candidate facts and source IDs are reused.
- User-pasted text and claims are not evidence unless independently verified from an inspected source.
- Never identify a real person as the perpetrator from rumours, AI inference, or unverified claims.
- Evidence remains capped at grade C; the report retains its unreviewed-draft banner.
- Never touch either formal case pack.

## Sync and verify

Before editing the live cron task, read its full current body with `cron.view`.
Replace the body with the behavior above plus the existing normal-investigation
search procedure. After saving, read it again with `cron.view` and confirm the
follow-up rules and exact `run_job.py` command are present. Do not claim the
runner-side connection is complete until the live cron body has been read back.
