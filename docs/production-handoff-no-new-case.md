# DETECTIVE OS — Production handoff (no new case)

Use this handoff after pulling the latest `main`. It only deploys the front end and synchronizes the existing scheduled runner. **Do not create or run any investigation job.**

## 1. Pull and verify

```bash
git pull --ff-only origin main
python3 -m unittest discover -s tests -v
python3 scripts/check_frontend.py
python3 -m detective_os.cli check cases/case-cn-1996-001
python3 scripts/validate_baiyin.py
python3 -m detective_os.cli check cases/case-cn-1988-001
```

Expected: 56 tests pass; frontend reports 11 result workspaces; both formal case packs validate.

## 2. Deploy

```bash
python3 deploy.py
```

The deploy script now runs `scripts/build_site.py` first, then Wrangler deploys `public/` and the Pages Functions.

Verify:
- `https://detective-os.pages.dev/` loads the redesigned case center.
- `https://detective-os.pages.dev/investigate.html` loads the V2 intake form and all 11 result tabs.
- `GET https://detective-os.pages.dev/api/jobs` returns JSON.
- Submit an intentionally invalid test body such as `{"direction":"x"}` to `POST /api/investigate`; expect HTTP 400 and verify no new KV job was created. Do not submit a valid test investigation.

## 3. Synchronize the existing scheduled runner

1. Use `cron.view` to read the complete current `detective-os-job-watch` task body and confirm its existing cadence.
2. Replace only that task's body with the complete contents of `docs/runner-v2-instructions.md`. Preserve the existing schedule; do not create a second cron task.
3. Use `cron.view` again and read the full saved body. Confirm it contains the V2 intake fields, cutoff-date rule, URL-first collection, `collected.json` schema, and the single `python3 scripts/run_job.py <job_id>` execution path.
4. Do not trigger a manual run, do not create a test case, and do not change any existing job or checkpoint.

## 4. Report back

Report the deployed Pages URL and deployment ID, the HTTP checks, test totals, and confirmation that the existing cron body was read back. If deployment or cron access is unavailable, state exactly which step is blocked; do not claim it is live.
