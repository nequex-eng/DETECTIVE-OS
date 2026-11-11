# Muse runner sync — archived-case continuation

Please update the existing scheduled task `detective-os-job-watch`. Do not create a second cron task and do not change any source code.

1. Call `cron.view` and read the complete current task body before editing.
2. Read the current repository file `docs/runner-v2-instructions.md` from `nequex-eng/DETECTIVE-OS` main. Treat that file as the authoritative runner protocol.
3. Replace/synchronize the existing scheduled task body so it includes the full V2 protocol, including this mandatory branch:

   - If `intake.baseline_case_id` is set and `intake.parent_job_id` begins with `case-pack:`, this is the first incremental continuation from an archived formal case pack.
   - Do NOT call `python3 scripts/job.py get` using that synthetic parent ID.
   - Read the immutable baseline from `cases/<baseline_case_id>/case.json`, `sources.json`, `evidence.json`, and `coverage.json`, plus `reports/<CASE-ID>-report.json`.
   - Preserve the original source IDs and the eligible A-E baseline facts. F/G/H records remain quarantined.
   - Open every user-supplied URL first. Treat uploaded/pasted text and notes only as leads; independently open and verify the original sources.
   - Write ONLY newly inspected sources and their text into the child `runs/<job_id>/collected.json`. Never copy old baseline sources into that file.
   - Then run exactly `python3 scripts/run_job.py <job_id>`. The executor builds the v1 baseline, appends only new sources, and creates v2/v3 report versions without modifying the formal case pack or original report.

4. Preserve the normal UUID-parent continuation behavior for later versions. If `parent_job_id` is a UUID, read the parent job and its checkpoints as described in the V2 protocol.
5. Keep all other runner safety rules: no fabricated sources or quotes, no user-pasted material promoted to evidence, no real-person perpetrator claims, and never mark a task done manually.
6. After editing, call `cron.view` again and read the complete saved task body. Confirm the `baseline_case_id` / `case-pack:` branch is present in the read-back. If the edit tool reports success but read-back does not show it, do not claim the sync succeeded.

Report back with: the task name, whether the full body was read before editing, whether the new branch is visible in the read-back, and whether the runner can access the current main commit. Do not start any investigation task during this synchronization.
