// DETECTIVE OS — POST /api/investigate: take an investigation direction
// and queue an auto-run job. The runner (agent + pipeline) picks it up,
// runs collect -> dedup -> extract -> reason -> draft report, and writes
// progress back to KV. This endpoint only creates jobs; it never runs
// the pipeline and never touches the engine.
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" }
  });
}

export async function onRequestPost(context) {
  try {
    const env = context.env || {};
    if (!env.JOBS) return json({ error: "任务存储还没接好，请稍后再试" }, 503);
    const body = await context.request.json();
    const direction = typeof body.direction === "string" ? body.direction.trim() : "";
    if (!direction) return json({ error: "请先输入调查方向" }, 400);
    if (direction.length > 500) return json({ error: "调查方向请控制在500字以内" }, 400);
    const language = typeof body.language === "string" && /^[a-z]{2,5}$/.test(body.language.trim())
      ? body.language.trim() : "zh";
    const region = typeof body.region === "string" ? body.region.trim().slice(0, 200) : "";
    const hints = typeof body.hints === "string" ? body.hints.trim().slice(0, 500) : "";
    const now = new Date().toISOString();
    const job = {
      job_id: crypto.randomUUID(),
      direction, language, region, hints,
      status: "queued", stage: "queued",
      stage_note: "已收到，等待跑手接手",
      events: [{ t: now, stage: "queued", message: "任务已创建，等待跑手接手" }],
      result: null, error: null,
      created_at: now, updated_at: now
    };
    await env.JOBS.put("job:" + job.job_id, JSON.stringify(job));
    return json({ job_id: job.job_id, status: job.status }, 201);
  } catch (e) {
    return json({ error: "请求有误，请再试一次" }, 400);
  }
}

export async function onRequest(context) {
  if (context.request.method === "POST") return onRequestPost(context);
  return json({ error: "只接受POST" }, 405);
}
