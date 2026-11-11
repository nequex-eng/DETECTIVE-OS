// DETECTIVE OS — structured investigation intake API.
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}
function clean(value, max) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}
function lines(value, maxItems, maxLength) {
  const raw = Array.isArray(value) ? value : String(value || "").split(/\r?\n/);
  return [...new Set(raw.map(x => clean(x, maxLength)).filter(Boolean))].slice(0, maxItems);
}
export async function onRequestPost(context) {
  try {
    const env = context.env || {};
    if (!env.JOBS) return json({ error: "任务存储还没接好" }, 503);
    const size = Number(context.request.headers.get("content-length") || 0);
    if (size > 45000) return json({ error: "提交内容超过45KB限制" }, 413);
    const body = await context.request.json();
    const direction = clean(body.direction, 500);
    if (direction.length < 3) return json({ error: "请输入至少3个字的调查方向" }, 400);
    const lang = clean(body.language, 5);
    const language = /^[a-z]{2,5}$/.test(lang) ? lang : "zh";
    const now = new Date().toISOString();
    const sourceUrls = lines(body.source_urls, 21, 1000);
    if (sourceUrls.length > 20) return json({ error: "指定来源最多20条" }, 400);
    if (sourceUrls.some(u => !u.startsWith("https://") && !u.startsWith("http://"))) {
      return json({ error: "来源链接必须以http://或https://开头" }, 400);
    }
    const intake = {
      version: 2,
      objective: clean(body.objective, 2000),
      time_range: clean(body.time_range, 200),
      evidence_cutoff_date: clean(body.evidence_cutoff_date, 10),
      known_facts: clean(body.known_facts, 5000),
      questions: clean(body.questions, 5000),
      exclusions: clean(body.exclusions, 2000),
      source_urls: sourceUrls,
      materials: clean(body.materials, 30000),
      parent_job_id: clean(body.parent_job_id, 80),
      submitted_at: now
    };
    if (intake.evidence_cutoff_date && !/^\d{4}-\d{2}-\d{2}$/.test(intake.evidence_cutoff_date)) return json({ error: "资料截止日期格式应为YYYY-MM-DD" }, 400);
    // Mirror structured intake into hints for compatibility with existing
    // scheduled runners that already read the V1 job.hints field.
    const brief = [
      "[STRUCTURED USER INTAKE V2]",
      "调查目标：" + intake.objective,
      "调查时间范围：" + intake.time_range,
      "证据截止日期（不得使用此日期之后的信息）：" + intake.evidence_cutoff_date,
      "已知背景（仅作线索，需独立核验）：" + intake.known_facts,
      "待回答问题：" + intake.questions,
      "排除范围：" + intake.exclusions,
      "指定来源链接（优先打开并核验）：\n" + intake.source_urls.join("\n"),
      "用户提交材料（单独标记为用户供料，不得升级为事实）：\n" + intake.materials,
      "关联父任务（读取旧报告仅作上下文，不作为证据）：" + intake.parent_job_id
    ].filter(x => x.split("：").slice(1).join("：").trim()).join("\n\n");
    const hints = [clean(body.hints, 5000), brief].filter(Boolean).join("\n\n");
    const job = {
      job_id: crypto.randomUUID(),
      direction,
      language,
      region: clean(body.region, 200),
      hints,
      intake,
      status: "queued",
      stage: "queued",
      stage_note: "调查委托已收到，等待后台跑手执行",
      progress: { percent: 0, label: "排队中" },
      metrics: { sources: 0, facts: 0, contradictions: 0 },
      events: [{ t: now, stage: "queued", message: "完整调查委托已创建，等待后台自动执行" }],
      result: null,
      error: null,
      created_at: now,
      updated_at: now
    };
    await env.JOBS.put("job:" + job.job_id, JSON.stringify(job));
    return json({ job_id: job.job_id, status: job.status, intake_version: 2 }, 201);
  } catch (e) {
    return json({ error: "请求格式有误，请检查输入后重试" }, 400);
  }
}
export async function onRequest(context) {
  if (context.request.method === "POST") return onRequestPost(context);
  return json({ error: "只接受POST" }, 405);
}
