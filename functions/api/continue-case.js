// Create the first incremental follow-up from the archived 1996 case pack.
// The runner reads the canonical pack from the repository as the immutable v1 baseline.
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" }
  });
}
function cleanText(value, max) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}
export async function onRequestPost(context) {
  try {
    const env = context.env || {};
    if (!env.JOBS) return json({ error: "任务存储还没接好，请稍后再试" }, 503);
    const body = await context.request.json();
    const caseId = cleanText(body.case_id, 80);
    const supported = {
      "case-cn-1996-001": {
        case_id: "CASE-CN-1996-001",
        direction: "1996南京大学刁爱青遇害案"
      }
    };
    const baseline = supported[caseId];
    if (!baseline) return json({ error: "该静态案卷暂不支持增量续办" }, 400);
    const sourceUrls = Array.isArray(body.source_urls)
      ? body.source_urls.map(v => cleanText(v, 2000)).filter(v => /^https?:\/\//i.test(v)).slice(0, 20)
      : [];
    const sourceText = cleanText(body.source_text, 20000);
    const materials = cleanText(body.materials, 12000);
    const questions = cleanText(body.questions, 5000);
    const knownFacts = cleanText(body.known_facts, 5000);
    if (!sourceUrls.length && !sourceText && !materials && !questions && !knownFacts) {
      return json({ error: "请至少添加一个新信源、补充信息或跟进问题" }, 400);
    }

    const rootJobId = "case-pack:" + baseline.case_id;
    const listed = await env.JOBS.list({ prefix: "job:", limit: 1000 });
    const lineage = [];
    for (const key of (listed.keys || [])) {
      const raw = await env.JOBS.get(key.name);
      if (!raw) continue;
      try {
        const item = JSON.parse(raw);
        const root = item.root_job_id || item.result?.root_job_id ||
          item.parent_job_id || item.job_id;
        if (root === rootJobId) lineage.push(item);
      } catch (_) {}
    }
    const active = lineage.find(item =>
      ["queued", "collecting", "extracting", "reasoning"].includes(item.status));
    if (active) return json({
      error: "该案已有续办任务正在执行，请先查看任务 " + active.job_id,
      active_job_id: active.job_id
    }, 409);
    const version = lineage.reduce((max, item) =>
      Math.max(max, Number(item.result?.version || item.version || 1)), 1) + 1;
    const now = new Date().toISOString();
    const job = {
      job_id: crypto.randomUUID(),
      direction: baseline.direction,
      language: "zh",
      region: "南京，中国",
      hints: "【继续调查】基于正式静态案卷v1增量跟进；只处理新增信源，不得重跑旧来源。",
      version,
      parent_job_id: rootJobId,
      root_job_id: rootJobId,
      intake: {
        objective: "在正式案卷v1基础上进行增量跟进，核查新增信源并更新分析。",
        parent_job_id: rootJobId,
        baseline_case_id: baseline.case_id,
        source_urls: sourceUrls,
        user_source_text: sourceText,
        materials,
        questions,
        known_facts: knownFacts,
        parent_report_context: "",
        parent_version: 1,
        exclusions: [],
        time_range: "",
        evidence_cutoff_date: ""
      },
      status: "queued",
      stage: "queued",
      stage_note: "续办委托已创建，等待跑手接手",
      events: [{ t: now, stage: "queued", message: "基于正式案卷v1创建增量续办；原案卷与原报告保持不变" }],
      result: null,
      error: null,
      created_at: now,
      updated_at: now
    };
    await env.JOBS.put("job:" + job.job_id, JSON.stringify(job));
    return json({ job_id: job.job_id, parent_job_id: rootJobId, version, status: job.status }, 201);
  } catch (_) {
    return json({ error: "续办请求有误，请检查输入后重试" }, 400);
  }
}
export async function onRequest(context) {
  if (context.request.method === "POST") return onRequestPost(context);
  return json({ error: "只接受POST" }, 405);
}
