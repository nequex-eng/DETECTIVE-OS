// DETECTIVE OS — create a follow-up run linked to a completed investigation.
// User-provided notes are leads/context, never evidence. URLs are handed to the runner for independent collection.
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
    const parentId = cleanText(body.parent_job_id, 80);
    if (!parentId) return json({ error: "缺少原调查任务编号" }, 400);
    const raw = await env.JOBS.get("job:" + parentId);
    if (!raw) return json({ error: "找不到原调查任务" }, 404);
    const parent = JSON.parse(raw);
    if (parent.status !== "done" || !parent.result) {
      return json({ error: "只有已经完成且有报告的调查才能继续跟进" }, 409);
    }
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
    const now = new Date().toISOString();
    const nextVersion = Number(parent.result.version || 1) + 1;
    const followupHints = [
      "【继续调查】原任务：" + parentId + "；目标版本：v" + nextVersion,
      sourceUrls.length ? "【新增信源URL】\n" + sourceUrls.join("\n") : "",
      sourceText ? "【用户粘贴的信源文本：仅作待核实线索】\n" + sourceText : "",
      questions ? "【重点问题】\n" + questions : "",
      knownFacts ? "【补充线索：未核实】\n" + knownFacts : "",
      materials ? "【补充材料：未核实】\n" + materials : ""
    ].filter(Boolean).join("\n\n");
    const job = {
      job_id: crypto.randomUUID(),
      direction: parent.direction,
      language: parent.language || "zh",
      region: parent.region || "",
      hints: followupHints,
      version: nextVersion,
      parent_job_id: parentId,
      intake: {
        objective: "在原调查基础上继续跟进，核查新增信源和线索，并更新证据分析。",
        parent_job_id: parentId,
        source_urls: sourceUrls,
        user_source_text: sourceText,
        materials,
        questions,
        known_facts: knownFacts,
        parent_report_context: cleanText(parent.result.report_md, 12000),
        parent_version: Number(parent.result.version || 1),
        exclusions: [],
        time_range: "",
        evidence_cutoff_date: ""
      },
      status: "queued",
      stage: "queued",
      stage_note: "续办委托已创建，等待跑手接手",
      events: [{ t: now, stage: "queued", message: "继续调查任务已创建；原报告作为背景，新增信源待核验" }],
      result: null,
      error: null,
      created_at: now,
      updated_at: now
    };
    await env.JOBS.put("job:" + job.job_id, JSON.stringify(job));
    return json({ job_id: job.job_id, parent_job_id: parentId, status: job.status }, 201);
  } catch (e) {
    return json({ error: "续办请求有误，请检查输入后重试" }, 400);
  }
}
export async function onRequest(context) {
  if (context.request.method === "POST") return onRequestPost(context);
  return json({ error: "只接受POST" }, 405);
}
