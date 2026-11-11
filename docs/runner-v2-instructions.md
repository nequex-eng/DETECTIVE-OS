# DETECTIVE OS — Scheduled Runner V2

This file is the complete task body for the existing `detective-os-job-watch` runner. It replaces the old hand-written stage sequence. The runner must process the structured user intake, collect public sources, then invoke the single mechanical executor.

## Purpose and hard rules

- This is a real-case public-source research engine, not a fictional game.
- Never identify a real person as the perpetrator from rumours, forum posts, AI inference, or unverified names.
- Keep fact, media report, witness/party statement, user-supplied material, rumour, AI inference, and unknown separate.
- Do not promote AI-generated or user-supplied material into verified evidence.
- Preserve original quotations, source URLs, publication dates, source locations, and reprint/origin relationships.
- Do not invent source text, quotes, dates, events, or source independence.
- Do not overwrite either formal case pack. All automatic runs are drafts under `runs/<job_id>` and `cases/draft-<short_id>`.
- Never set a job to `done` yourself. `scripts/run_job.py` owns final result generation and the final status transition.

## Each scheduled execution

1. Run `python3 scripts/job.py poll`.
2. For each queued job, run `python3 scripts/job.py get <job_id>` and read the complete JSON. Do not rely on the list summary.
3. If another runner has already moved the task beyond `queued`, do not start a duplicate collection process. Resume only if the job is in a recoverable state and no other process is working on it.
4. Move the job from `queued` to `collecting` using `job.py update`, with an explanatory note and event.
5. Read all of:
   - `direction`, `region`, `language`, `hints`
   - `intake.objective`
   - `intake.time_range`
   - `intake.evidence_cutoff_date`
   - `intake.known_facts`
   - `intake.questions`
   - `intake.exclusions`
   - `intake.source_urls`
   - `intake.materials`
   - `intake.parent_job_id`
   - `intake.parent_report_context`

The API mirrors structured intake fields into `hints` for compatibility with older runner instructions. Treat the structured `intake` object as authoritative. A follow-up job is a new linked job with `parent_job_id`; never overwrite or mark the parent job running.

## Collection instructions

- Open and inspect every valid user-specified `source_urls` URL first. Record failures honestly; do not silently discard inaccessible URLs.
- Use `intake.objective`, `time_range`, `known_facts`, and `questions` to refine the search plan. Known facts are leads to verify, not established facts.
- Apply `intake.exclusions` strictly.
- If `intake.evidence_cutoff_date` is set, exclude all sources and information published after that date from the reasoning corpus. Do not use later information to shape hypotheses or collection conclusions; record the cutoff in the collected file notes.
- Search in the requested language and, where useful, English or the relevant local language. Search official sources, court records, contemporaneous reporting, and independent reputable media before secondary summaries.
- Open the underlying pages and collect substantive text, not just search snippets. Aim for multiple independent origins, but never inflate source counts with reprints.
- Record the actual publisher, title, author when available, publication date, canonical URL, source type, whether it is a reprint, and its original source when known.
- If several outlets reproduce the same original report, set `reprint_of` or `origin_url` so the engine counts the cluster as one independent origin.
- Treat `intake.materials` and `intake.known_facts` as unverified user leads only. Never add them to `sources` or `texts`, never extract evidence from them, and never present them as independently verified.
- If `intake.parent_job_id` exists, use the prior report and its gaps to guide collection, but do not treat the report as a source or evidence. `run_job.py` merges the parent result’s saved source records and raw source text (when available), deduplicates canonical URLs, and re-runs extraction across the carried-forward corpus plus new sources. Legacy parent jobs that lack saved raw source text are report-context only; do not invent or reconstruct their source texts.
- If no reliable public source can be found, record the failed search paths and explain the limitation. Do not fabricate a result.

## Required collected file

Create `runs/<job_id>/collected.json` with this structure:

```json
{
  "direction": "copy the job direction",
  "sources": [
    {
      "source_id": "S01",
      "title": "Source title",
      "publisher": "Publisher",
      "author": "",
      "published_at": "YYYY-MM-DD or empty",
      "url": "https://...",
      "origin_url": "canonical original URL or empty",
      "source_type": "news",
      "is_reprint": false,
      "reprint_of": "",
      "reliability": "why this source is useful and its limitations",
      "last_verified": "YYYY-MM-DD",
      "notes": "provenance notes"
    }
  ],
  "texts": {
    "S01": "substantive page text actually read"
  },
  "paths_tried": [
    {
      "path": "web_search",
      "status": "found",
      "note": "what was searched and what was found"
    }
  ]
}
```

Use unique source IDs. Each `texts` key must match a source ID. For follow-up jobs, keep the parent source corpus intact and add only newly inspected sources; `run_job.py` performs canonical-URL deduplication and stable source-ID reassignment.\n\nThe accepted collection path names are: `web_search`, `direct_source`, `news_db`, `web_archive`, `court_db`, `local_language`, `books_media`, `user_supplied`, `community_lead`, `foia`. Status values: `tried`, `found`, `nothing`, `not_applicable`. The normalizer can repair free-form path notes, but use canonical values when possible.

## Execute and verify

1. After writing `collected.json`, update the task note/event to say collection is complete and include the real source count.
2. Run exactly: `python3 scripts/run_job.py <job_id>`.
3. Let the script perform extraction, quote verification, likelihood proposals, category mapping, draft-pack generation, engine checks, coverage calculation, independent review, report writing, and final KV update.
4. If interrupted, do not delete checkpoints. Rerun `run_job.py`; it resumes from valid checkpoints tied to the `collected.json` modification time.
5. If it fails, report the exact error and leave the task in the state written by the script. Do not forge a result or manually mark it done.
6. Verify the final task by reading it again with `job.py get`. Confirm `status=done`, a non-null result, and that the result's source/fact counts and coverage match the generated files.
7. Do not claim completion if the result is missing or the job is still running.

## User-facing output

Report the task ID, sources collected, facts extracted, evidence-grade distribution, verdict, posterior table, coverage (covered/single/missing), review blockers, and report path. Always call it an unreviewed draft. Explain that the posterior is a relative model ranking, not the probability that any named person committed the crime.
