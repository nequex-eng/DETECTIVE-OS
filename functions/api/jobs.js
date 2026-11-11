// DETECTIVE OS — GET /api/jobs: read job status and results.
//   /api/jobs?id=<job_id>  -> one job with its stage events
//   /api/jobs             -> most recent 20 jobs (no result bodies)
// No write endpoint here on purpose: only the runner (via wrangler KV)
// updates jobs, so the public internet cannot forge progress or results.
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" }
  });
}

export async function onRequestGet(context) {
  const env = context.env || {};
  if (!env.JOBS) return json({ error: "任务存储还没接好，请稍后再试" }, 503);
  const url = new URL(context.request.url);
  const id = url.searchParams.get("id");
  if (id) {
    try {
      const raw = await env.JOBS.get("job:" + id);
      if (!raw) return json({ error: "没有这个任务" }, 404);
      const job = JSON.parse(raw);
      if (!job || job.job_id !== id || typeof job.direction !== "string") {
        return json({ error: "任务记录无效或已损坏" }, 404);
      }
      return json(job);
    } catch (_) {
      return json({ error: "任务记录暂时不可读取" }, 503);
    }
  }
  try {
    const list = await env.JOBS.list({ prefix: "job:", limit: 1000 });
    const jobs = [];
    let skipped = 0;
    for (const k of (list.keys || [])) {
      try {
        const raw = await env.JOBS.get(k.name);
        if (!raw) { skipped++; continue; }
        const j = JSON.parse(raw);
        // Old/manual KV probes and interrupted writes may not be real jobs.
        // Never let one malformed record crash the whole public task registry.
        if (!j || typeof j.job_id !== "string" || !j.job_id ||
            typeof j.direction !== "string" || !j.direction ||
            typeof j.status !== "string") { skipped++; continue; }
        jobs.push({ job_id: j.job_id, direction: j.direction, language: j.language,
                    status: j.status, stage: j.stage || "unknown", stage_note: j.stage_note || "",
                    parent_job_id: j.parent_job_id || null,
                    version: j.result?.version || j.version || 1,
                    previous_verdict: j.result?.previous_verdict || null,
                    source_count: j.result?.source_count ?? null,
                    fact_count: j.result?.fact_count ?? null,
                    created_at: j.created_at || "", updated_at: j.updated_at || "" });
      } catch (_) { skipped++; }
    }
    jobs.sort((a, b) => String(a.created_at) < String(b.created_at) ? 1 : -1);
    return json({ jobs: jobs.slice(0, 1000), skipped_records: skipped });
  } catch (_) {
    return json({ error: "任务库暂时不可读取", code: "JOB_REGISTRY_READ_FAILED" }, 503);
  }
}

export async function onRequest(context) {
  if (context.request.method === "GET") return onRequestGet(context);
  return json({ error: "只接受GET" }, 405);
}
