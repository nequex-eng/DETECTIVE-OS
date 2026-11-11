// DETECTIVE OS — read-only job status and results API.
// GET /api/jobs?id=<job_id> returns one full job; GET /api/jobs lists recent summaries.
function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});}
export async function onRequestGet(context){
 const env=context.env||{};if(!env.JOBS)return json({error:"任务存储还没接好"},503);
 const url=new URL(context.request.url),id=url.searchParams.get("id");
 if(id){const raw=await env.JOBS.get("job:"+id);if(!raw)return json({error:"没有这个任务"},404);return json(JSON.parse(raw));}
 const list=await env.JOBS.list({prefix:"job:",limit:50}),jobs=[];
 for(const k of list.keys){const raw=await env.JOBS.get(k.name);if(!raw)continue;const j=JSON.parse(raw),i=j.intake||{},r=j.result||{};jobs.push({job_id:j.job_id,direction:j.direction,language:j.language,region:j.region,status:j.status,stage:j.stage,stage_note:j.stage_note,progress:j.progress,metrics:j.metrics,created_at:j.created_at,updated_at:j.updated_at,intake_summary:{source_urls:(i.source_urls||[]).length,has_materials:!!i.materials,has_questions:!!i.questions}});}
 jobs.sort((a,b)=>(a.created_at<b.created_at?1:-1));return json({jobs:jobs.slice(0,20)});
}
export async function onRequest(context){if(context.request.method==="GET")return onRequestGet(context);return json({error:"只接受GET"},405);}
