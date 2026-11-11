#!/usr/bin/env python3
"""Build the static case dashboard from the engine's real report JSONs.

No hand-written content: every number on the pages comes from
reports/<CASE>-report.json and the case packs. A case without an engine
report is listed as 'not run yet', never faked.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ["case-cn-1996-001", "case-cn-1988-001"]

STYLE = ("<style>body{background:radial-gradient(ellipse at 80% 0%,#1b2b38 0,transparent 42%),#08121d;color:#dce5ed;font-family:system-ui,sans-serif;max-width:1180px;margin:0 auto;padding:28px}"
         "h1{font:500 clamp(28px,4vw,42px)/1.15 Georgia,serif}h2{font:500 19px Georgia,serif;color:#e0c17e}"
         "a{color:#b7d1e7;text-decoration:none}a:hover{color:#e3c17c}table{border-collapse:collapse}"
         "td,th{border:1px solid #33485a;padding:6px 10px;text-align:left}"
         ".note{color:#9aaebe;font-size:12px;line-height:1.8}.eyebrow{color:#b89a62;font:700 10px ui-monospace,monospace;letter-spacing:2px}"
         ".ops-banner{padding:22px 24px;margin:24px 0;background:linear-gradient(112deg,#14283a,#101d2b 65%,#1d211d);border:1px solid #35495b;border-left:3px solid #c39a50}"
         ".ops-banner h2{font:500 21px Georgia,serif;color:#e4eaf0;margin:8px 0}.ops-banner p{color:#94a7b9;font-size:11px}"
         ".action{display:inline-block;padding:10px 15px;background:#c5a05e;color:#111a22;font-size:10px;font-weight:800;letter-spacing:1px}"
         ".job-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.job{padding:15px;background:#101e2b;border:1px solid #2a4053}"
         ".job-main{display:block}.job-top,.job-bottom{display:flex;justify-content:space-between;gap:10px;font:9px ui-monospace,monospace;color:#8fa5b8}"
         ".job h3{font-size:13px;color:#e1e8ef;margin:12px 0 5px}.job p{font-size:10px;color:#91a5b7;min-height:30px}"
         ".status{font-size:9px;padding:3px 7px;border:1px solid #6c593b;color:#dfc17e}.status.done{border-color:#416b59;color:#83c6a1}.status.failed{border-color:#754c4c;color:#e29a96}"
         ".continue-link{display:block;margin-top:10px;padding-top:10px;border-top:1px solid #2a4053;color:#d8b875;font-size:10px}"
         ".empty{padding:22px;border:1px dashed #405365;color:#92a6b8;font-size:11px}.section-head{margin:30px 0 12px;padding-bottom:9px;border-bottom:1px solid #2b4052}"
         "@media(max-width:700px){body{padding:16px}.job-grid{grid-template-columns:1fr}}</style>")


def esc(s):
    return html.escape(str(s))


def case_page(case_id):
    case_dir = ROOT / "cases" / case_id
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    report_path = ROOT / "reports" / f"{case['case_id']}-report.json"
    if not report_path.exists():
        print(f"skip {case_id}: no engine report yet")
        return None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sources = json.loads((case_dir / "sources.json").read_text(encoding="utf-8"))
    evidence = json.loads((case_dir / "evidence.json").read_text(encoding="utf-8"))
    rows = "".join(
        f"<tr><td>{esc(s['hypothesis_id'])}</td>"
        f"<td>{esc(s['posterior'])}</td><td>{esc(s['prior'])}</td></tr>"
        for s in report["bayesian"]["posteriors"])
    contra = "".join(
        f"<li><b>{esc(c['contradiction_id'])}</b>（{esc(c['type_label'])}）："
        f"{esc(c['wording_a'])} vs {esc(c['wording_b'])}。"
        f"口径漂移可能：{esc(c['could_be_drift'])}。尚需：{esc(c['needs_what'])}</li>"
        for c in report["contradictions"])
    gaps = "".join(f"<li><b>{esc(g['id'])}</b>：{esc(g['gap'])}</li>"
                   for g in report["gaps"])
    srcs = "".join(
        f"<li><b>{esc(s['source_id'])}</b> {esc(s['title'])}——{esc(s['publisher'])}"
        f"（{esc(s['published_at'])}）<br><a href=\"{esc(s['url'])}\">{esc(s['url'])}</a></li>"
        for s in sources if s.get("url"))
    grades = {}
    for e in evidence:
        grades[e["grade"]] = grades.get(e["grade"], 0) + 1
    grade_line = "、".join(f"{g}级{grades.get(g, 0)}条" for g in "ABCDEFGH")
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>DETECTIVE OS — {esc(case['name'])}</title>{STYLE}</head><body>
<p><a href="index.html">← 案件中心</a></p>
<h1>DETECTIVE OS — {esc(case['name'])}</h1>
<p>案件编号：{esc(case['case_id'])}｜状态：{esc(case['status'])}</p>
<p class="note">本页由引擎真实输出生成，非手写结论。只依据公开资料，不代表警方卷宗；
推测不包装成事实，不根据网络传言指认现实中的个人为凶手。</p>
<h2>假设排序（贝叶斯，结论：{esc(report['bayesian']['verdict'])}）</h2>
<table><tr><th>假设</th><th>后验</th><th>先验</th></tr>{rows}</table>
<p class="note">{esc(report['bayesian']['disclosure'])}</p>
<h2>证据统计</h2><p>{grade_line}。共{len(evidence)}条证据，{len(sources)}个来源。</p>
<h2>矛盾（{len(report['contradictions'])}条）</h2><ul>{contra}</ul>
<h2>缺口（{len(report['gaps'])}条）</h2><ul>{gaps}</ul>
<h2>来源</h2><ul>{srcs}</ul>
<h2>回答不了的问题</h2>
<p>公开资料无法回答：警方掌握但未公布的证据、法医原始报告、完整的排查记录、DNA比对现状。不得据此假装还原完整刑侦卷宗。</p>
</body></html>"""
    out = ROOT / "public" / f"{case_id}.html"
    out.write_text(page, encoding="utf-8")
    print(f"built {out.name}")
    return {"case": case, "report": report}


def main():
    out = ROOT / "public"
    out.mkdir(exist_ok=True)
    built = []
    for case_id in CASES:
        r = case_page(case_id)
        if r:
            built.append((case_id, r))
    links = "".join(
        f"<li><a href=\"{cid}.html\">{esc(r['case']['name'])}</a> — "
        f"{esc(r['case']['case_id'])}，结论：{esc(r['report']['bayesian']['verdict'])}，"
        f"证据{len(json.loads((ROOT / 'cases' / cid / 'evidence.json').read_text(encoding='utf-8')))}条</li>"
        for cid, r in built)
    index = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>DETECTIVE OS — 案件中心</title>{STYLE}</head><body>
<div class="eyebrow">INTELLIGENCE OPERATIONS CENTER / OPEN-SOURCE RESEARCH</div>
<h1>DETECTIVE OS</h1>
<p class="note">真实案件公开资料调查工作站。统一管理调查委托、来源采集、证据链、竞争性假设与独立审查。事实、报道、用户线索、推断和未知严格区分。</p>
<div class="ops-banner"><div class="eyebrow">CASEWORK / LIVE OPERATIONS</div><h2>调查行动中心</h2><p>每项完成的调查都可以继续跟进。新增信源将追加到原始案卷，旧报告保留，生成独立版本。</p><a class="action" href="investigate.html">＋ 新建调查委托</a></div>
<div class="section-head"><div class="eyebrow">LIVE TASK REGISTER</div><h2>近期调查任务 <small id="jobCount">CONNECTING…</small></h2></div>
<div id="jobs" class="job-grid"><div class="empty">正在读取任务库……</div></div>
<div class="section-head"><div class="eyebrow">ARCHIVED CASE FILES</div><h2>已归档案卷</h2></div><ul>{links}</ul>
<p class="note">研究边界：公开资料不等于完整警方卷宗。转载不等于独立佐证；模型推断不等于事实；假设排序不等于真实犯罪概率。证据不足时允许不作结论。</p>
<script>
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
async function loadJobs(){{
  const root=document.getElementById("jobs"),count=document.getElementById("jobCount");
  try{{
    const res=await fetch("/api/jobs",{{cache:"no-store"}});
    if(!res.ok)throw Error("task registry unavailable");
    const data=await res.json(),jobs=data.jobs||[];
    count.textContent=jobs.length+" RECORDS";
    root.innerHTML=jobs.length?jobs.map(j=>{{
      const done=j.status==="done",failed=j.status==="failed";
      const label=done?"COMPLETED":failed?"FAILED":j.status==="queued"?"AWAITING HANDLER":"IN PROGRESS";
      return '<div class="job"><a class="job-main" href="investigate.html?job='+encodeURIComponent(j.job_id)+'"><div class="job-top"><span>'+esc(j.job_id.slice(0,13).toUpperCase())+'</span><span class="status '+(done?'done':failed?'failed':'')+'">'+label+'</span></div><h3>'+esc(j.direction)+'</h3><p>'+esc(j.stage_note||j.stage||"等待状态更新")+'</p><div class="job-bottom"><span>v'+esc(j.version||1)+'</span><span>'+esc(j.updated_at||j.created_at||"")+'</span></div></a>'+(done?'<a class="continue-link" href="investigate.html?continue='+encodeURIComponent(j.job_id)+'">＋ 继续调查 · 添加信源与新线索</a>':'')+'</div>';
    }}).join(""):'<div class="empty">当前没有调查任务。创建新的调查委托后会自动显示在这里。</div>';
  }}catch(e){{count.textContent="OFFLINE";root.innerHTML='<div class="empty">暂时无法连接任务库，稍后刷新。</div>';}}
}}
loadJobs();setInterval(loadJobs,15000);
</script>
</body></html>"""
    (out / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(built)} cases)")


if __name__ == "__main__":
    main()
