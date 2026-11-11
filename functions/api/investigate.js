// DETECTIVE OS — structured investigation intake API.
function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});}
function clean(v,n){return typeof v==="string"?v.trim().slice(0,n):"";}
function lines(v,max,n){const a=Array.isArray(v)?v:String(v||"").split(/\r?\n/);return [...new Set(a.map(x=>clean(x,n)).filter(Boolean))].slice(0,max);}
export async function onRequestPost(context){
 try{
  const env=context.env||{};if(!env.JOBS)return json({error:"任务存储还没接好"},503);
  const size=Number(context.request.headers.get("content-length")||0);if(size>45000)return json({error:"提交内容超过45KB限制"},413);
  const b=await context.request.json(),direction=clean(b.direction,500);
  if(direction.length<3)return json({error:"请输入至少3个字的调查方向"},400);
  const language=/^[a-z]{2,5}$/.test(clean(b.language,5))?clean(b.language,5):"zh";
  const now=new Date().toISOString();
  const intake={version:2,objective:clean(b.objective,2000),time_range:clean(b.time_range,200),known_facts:clean(b.known_facts,5000),questions:clean(b.questions,5000),exclusions:clean(b.exclusions,2000),source_urls:lines(b.source_urls,20,1000).filter(u=>/^https?:\/\//i.test(u)),materials:clean(b.materials,30000),parent_job_id:clean(b.parent_job_id,80),submitted_at:now};
  // Mirror the structured intake into hints so existing scheduled runners that read the V1 field also receive every user instruction.\n  const brief=["[STRUCTURED USER INTAKE V2]","调查目标："+intake.objective,"调查时间范围："+intake.time_range,"已知背景（仅作线索，需独立核验）："+intake.known_facts,"待回答问题："+intake.questions,"排除范围："+intake.exclusions,"指定来源链接（优先打开并核验）："+intake.source_urls.join("\\n"),"用户提交材料（单独标记为用户供料，不得升级为事实）："+intake.materials,"关联父任务："+intake.parent_job_id].filter(x=>x.split("：").slice(1).join("：").trim()).join("\\n\\n");\n  const hints=[clean(b.hints,5000),brief].filter(Boolean).join("\\n\\n");\n  const job={job_id:crypto.randomUUID(),direction,language,region:clean(b.region,200),hints,intake,status:"queued",stage:"queued",stage_note:"调查委托已收到，等待后台跑手执行",progress:{percent:0,label:"排队中"},metrics:{sources:0,facts:0,contradictions:0},events:[{t:now,stage:"queued",message:"完整调查委托已创建，等待后台自动执行"}],result:null,error:null,created_at:now,updated_at:now};
  await env.JOBS.put("job:"+job.job_id,JSON.stringify(job));
  return json({job_id:job.job_id,status:job.status,intake_version:2},201);
 }catch(e){return json({error:"请求格式有误，请检查输入后重试"},400);}
}
export async function onRequest(context){if(context.request.method==="POST")return onRequestPost(context);return json({error:"只接受POST"},405);}
