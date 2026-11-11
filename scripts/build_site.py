#!/usr/bin/env python3
"""Build the static DETECTIVE OS site and data-driven workbench dataset.

All visible case facts come from case packs. All rankings, plans, and review
results come from the structured engine report. This script is read-only with
respect to case packs and never writes to production KV or starts a live job.
"""
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from detective_os.cli import run_case

CASES = ["case-cn-1996-001", "case-cn-1988-001", "case-no-1970-001"]

STYLE = ("<style>body{background:#0d1117;color:#d7dee8;font-family:system-ui,sans-serif;"
         "max-width:1000px;margin:0 auto;padding:24px}h1{font-size:22px}h2{font-size:17px;"
         "color:#e8b64c}a{color:#7fb3ff}table{border-collapse:collapse;width:100%}"
         "td,th{border:1px solid #333;padding:7px 10px;text-align:left}"
         ".note{color:#9aa7b5;font-size:13px;line-height:1.7}.actions{display:flex;gap:16px;"
         "margin:18px 0}.action{display:inline-block;background:#263b52;padding:10px 14px;"
         "border-radius:6px;text-decoration:none}</style>")


def esc(value):
    return html.escape(str(value))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_case_data(case_id):
    case_dir = ROOT / "cases" / case_id
    case = read_json(case_dir / "case.json")
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_json = reports_dir / f"{case['case_id']}-report.json"
    report_md = reports_dir / f"{case['case_id']}-report.md"

    # Deterministic, structured-only run; no LLM, no database, no case-pack writes.
    run_case(case_dir, reports_dir, None)
    report = read_json(report_json)
    entities_doc = read_json(case_dir / "entities.json")
    return {
        "case": case,
        "sources": read_json(case_dir / "sources.json"),
        "evidence": read_json(case_dir / "evidence.json"),
        "events": read_json(case_dir / "events.json"),
        "entities": entities_doc.get("entities", []),
        "relationships": entities_doc.get("relationships", []),
        "contradictions": report.get("contradictions", []),
        "hypotheses": case.get("hypotheses", []),
        "bayesian": report.get("bayesian", {}),
        "qualitative": report.get("qualitative", {}),
        "plan": report.get("plan", []),
        "review": report.get("review", {}),
        "gaps": report.get("gaps", []),
        "limits": report.get("limits", case.get("limits", [])),
        "coverage": report.get("coverage"),
        "reportMarkdown": report_md.read_text(encoding="utf-8") if report_md.exists() else "",
        "reportUrl": f"/data/reports/{case['case_id']}-report.md",
    }


def case_page(data):
    case = data["case"]
    report = {"bayesian": data["bayesian"]}
    sources = data["sources"]
    evidence = data["evidence"]
    rows = "".join(
        f"<tr><td>{esc(row['hypothesis_id'])}</td>"
        f"<td>{esc(row['posterior'])}</td><td>{esc(row['prior'])}</td></tr>"
        for row in report["bayesian"].get("posteriors", []))
    contra = "".join(
        f"<li><b>{esc(item['contradiction_id'])}</b>（{esc(item.get('type_label', item.get('ctype', '')))}）："
        f"{esc(item['wording_a'])} vs {esc(item['wording_b'])}。"
        f"口径漂移可能：{esc(item.get('could_be_drift', ''))}。尚需：{esc(item.get('needs_what', ''))}</li>"
        for item in data["contradictions"])
    gaps = "".join(f"<li><b>{esc(item['id'])}</b>：{esc(item['gap'])}</li>"
                   for item in data["gaps"])
    srcs = "".join(
        f"<li><b>{esc(source['source_id'])}</b> {esc(source['title'])}——{esc(source['publisher'])}"
        f"（{esc(source.get('published_at', ''))}）<br><a href=\"{esc(source['url'])}\">{esc(source['url'])}</a></li>"
        for source in sources if source.get("url"))
    grades = {}
    for item in evidence:
        grades[item["grade"]] = grades.get(item["grade"], 0) + 1
    grade_line = "、".join(f"{grade}级{grades.get(grade, 0)}条" for grade in "ABCDEFGH")
    coverage = data.get("coverage") or {}
    coverage_line = (f"资料覆盖率{coverage.get('score', 0) * 100:.1f}%"
                     if coverage else "资料覆盖尚未计算")
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DETECTIVE OS — {esc(case['name'])}</title>{STYLE}</head><body>
<p><a href="index.html">← 案件中心</a> · <a href="workbench.html">打开研究工作站 →</a></p>
<h1>DETECTIVE OS — {esc(case['name'])}</h1>
<p>案件编号：{esc(case['case_id'])}｜状态：{esc(case['status'])}</p>
<p class="note">本页由案包与引擎真实输出生成，非手写结论。只依据公开资料，不代表警方卷宗；
推测不包装成事实，不根据网络传言指认现实中的个人为凶手。</p>
<h2>假设排序（贝叶斯，结论：{esc(report['bayesian'].get('verdict', '尚未生成'))}）</h2>
<table><tr><th>假设</th><th>后验</th><th>先验</th></tr>{rows}</table>
<p class="note">{esc(report['bayesian'].get('disclosure', ''))}</p>
<h2>证据统计</h2><p>{grade_line}。共{len(evidence)}条证据，{len(sources)}个来源。{coverage_line}。</p>
<h2>矛盾（{len(data['contradictions'])}条）</h2><ul>{contra}</ul>
<h2>缺口（{len(data['gaps'])}条）</h2><ul>{gaps}</ul>
<h2>来源</h2><ul>{srcs}</ul>
<p><a href=\"{esc(data['reportUrl'])}\">下载引擎报告Markdown</a></p>
<h2>回答不了的问题</h2>
<p>公开资料无法回答警方掌握但未公布的证据、完整法医原始报告和全部排查记录。不得据此假装还原完整刑侦卷宗。</p>
</body></html>"""
    return page


def main():
    public = ROOT / "public"
    public.mkdir(exist_ok=True)
    cases_dir = public / "data" / "cases"
    reports_public = public / "data" / "reports"
    cases_dir.mkdir(parents=True, exist_ok=True)
    reports_public.mkdir(parents=True, exist_ok=True)

    built = []
    index_rows = []
    for case_id in CASES:
        data = build_case_data(case_id)
        case = data["case"]
        case_file = cases_dir / f"{case['case_id']}.json"
        case_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        report_source = ROOT / "reports" / f"{case['case_id']}-report.md"
        if report_source.exists():
            shutil.copy2(report_source, reports_public / report_source.name)
        (public / f"{case_id}.html").write_text(case_page(data), encoding="utf-8")
        coverage = data.get("coverage") or {}
        index_rows.append({
            "case_id": case["case_id"],
            "name": case["name"],
            "status": case["status"],
            "verdict": data["bayesian"].get("verdict", "尚未生成"),
            "evidence_count": len(data["evidence"]),
            "source_count": len(data["sources"]),
            "coverage_score": coverage.get("score"),
            "review_passed": bool(data["review"].get("passed", False)),
        })
        built.append(data)
        print(f"built {case['case_id']}: {len(data['sources'])} sources, "
              f"{len(data['evidence'])} evidence, report generated")

    (cases_dir / "index.json").write_text(
        json.dumps(index_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    links = "".join(
        f"<li><a href=\"{esc(row['case_id'].lower().replace('case-', 'case-'))}.html\">"
        f"{esc(row['name'])}</a> — {esc(row['case_id'])}，"
        f"结论：{esc(row['verdict'])}，证据{row['evidence_count']}条</li>"
        for row in index_rows)
    index = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#08121d">
<title>DETECTIVE OS — Intelligence Operations</title>
<style>
:root{{--bg:#08121d;--panel:#101e2b;--line:#2a4053;--text:#e1e8ef;--muted:#8fa3b6;--gold:#c9a35f}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 80% 0%,#1b2b38 0,transparent 42%),var(--bg);color:var(--text);font:14px/1.6 Inter,system-ui,sans-serif}}
a{{color:inherit;text-decoration:none}}.shell{{max-width:1320px;margin:auto;padding:30px 34px 60px}}
header{{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:20px}}
.brand{{display:flex;align-items:center;gap:13px}}.seal{{width:46px;height:46px;display:grid;place-items:center;border:1px solid #8d7449;color:#e3c27f;font:700 16px Georgia,serif}}
.brand b{{display:block;font-size:13px;letter-spacing:2.2px}}.brand small{{display:block;color:#71879a;font-size:9px;letter-spacing:1.6px;margin-top:4px}}
.classified{{font:10px ui-monospace,monospace;letter-spacing:1.5px;color:#c6a76c;border:1px solid #6c593b;padding:7px 10px}}
.hero{{padding:54px 0 35px;display:grid;grid-template-columns:1.5fr 1fr;gap:35px;align-items:end}}
.eyebrow{{color:#b89a62;font:700 10px ui-monospace,monospace;letter-spacing:2px}}
h1{{font:500 clamp(30px,4vw,48px)/1.12 Georgia,serif;margin:12px 0 13px}}.hero p{{max-width:690px;color:#9aabba;font-size:13px;line-height:1.9;margin:0}}
.hero-side{{border-left:1px solid #405163;padding:8px 0 8px 20px;color:#8ea2b4;font-size:11px;line-height:1.9}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 32px}}.action{{padding:11px 16px;border:1px solid #8e7448;background:#c6a15f;color:#111b24;font-size:10px;font-weight:800;letter-spacing:1px}}.action.secondary{{background:#142638;color:#c6d5e2;border-color:#3c5367}}
.section{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--line);padding-bottom:10px;margin:30px 0 14px}}.section h2{{font:500 19px Georgia,serif;margin:5px 0 0}}.section span{{font:9px ui-monospace,monospace;color:#788da0;letter-spacing:1px}}
.live-grid,.archive-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.job,.archive-card{{background:linear-gradient(140deg,#122333,#0e1a26);border:1px solid #2a4053;padding:16px;display:block;min-width:0}}
.job:hover,.archive-card:hover{{border-color:#a8874f}}.job-main{{display:block;padding:0}}.continue-link{{display:block;margin-top:12px;padding-top:10px;border-top:1px solid #2a4053;color:#d8b875;font-size:10px}}.continue-link:hover{{color:#f0d49a}}.job-top,.job-bottom{{display:flex;justify-content:space-between;gap:10px;align-items:center}}
.job-id,.archive-card span{{font:9px ui-monospace,monospace;color:#8da5b9;letter-spacing:.7px}}
.status{{font-size:9px;padding:3px 7px;border:1px solid #6c593b;color:#dfc17e}}.status.done{{border-color:#416b59;color:#83c6a1}}.status.failed{{border-color:#754c4c;color:#e29a96}}
.job h3{{font-size:13px;margin:13px 0 5px}}.job p{{color:#93a7b9;font-size:10px;min-height:30px;margin:0 0 12px}}.job-bottom{{border-top:1px solid #26394a;padding-top:8px;color:#73899d;font:9px ui-monospace,monospace}}
.empty{{border:1px dashed #34495b;padding:23px;color:#91a5b8;font-size:11px}}.empty b{{display:block;color:#dce5ed;font:16px Georgia,serif;margin-bottom:5px}}
.archive-card b{{display:block;font:15px Georgia,serif;margin:10px 0}}.archive-card small{{display:block;color:#8196a9;font-size:9px;letter-spacing:1px}}.archive-card em{{display:block;color:#c4a66d;font-size:10px;font-style:normal;margin-top:10px;line-height:1.6}}
.notice{{margin-top:35px;padding:14px 16px;border-left:2px solid #8c744b;background:#111d28;color:#8fa2b3;font-size:10px;line-height:1.8}}
@media(max-width:700px){{.shell{{padding:18px 15px 40px}}header{{align-items:flex-start}}.hero{{grid-template-columns:1fr;padding:38px 0 25px;gap:15px}}.hero-side{{border-left:0;border-top:1px solid #405163;padding:12px 0 0}}.live-grid,.archive-grid{{grid-template-columns:1fr}}.classified{{font-size:8px}}}}
</style></head><body><div class="shell">
<header><div class="brand"><div class="seal">D·OS</div><div><b>DETECTIVE OS</b><small>REAL CASE INTELLIGENCE & INVESTIGATION</small></div></div><div class="classified">RESEARCH OPERATIONS / OPEN SOURCE</div></header>
<section class="hero"><div><div class="eyebrow">INTELLIGENCE OPERATIONS CENTER</div><h1>Evidence first.<br>Conclusions earned.</h1><p>面向真实历史案件的公开资料调查与证据分析工作站。统一管理调查委托、资料采集、证据链、竞争性假设与独立审查。事实、报道、推断与未知严格区分。</p></div><div class="hero-side">CASE INTELLIGENCE DIVISION<br>OPEN-SOURCE RESEARCH DESK<br>TRACEABLE · AUDITABLE · EVIDENCE-LED</div></section>
<div class="actions"><a class="action" href="investigate.html">＋ CREATE INVESTIGATION</a><a class="action secondary" href="workbench.html">OPEN INTELLIGENCE WORKBENCH →</a></div>
<div class="section"><div><div class="eyebrow">LIVE OPERATIONS</div><h2>近期调查任务</h2></div><span id="jobCount">CONNECTING TO TASK REGISTRY</span></div>
<div class="live-grid" id="jobs"><div class="empty"><b>正在连接任务库</b>读取服务器端调查记录……</div></div>
<div class="section"><div><div class="eyebrow">ARCHIVED CASE FILES</div><h2>已归档案卷</h2></div><span>{len(index_rows)} CASE FILES</span></div>
<div class="archive-grid">{links}</div>
<div class="notice">研究边界：公开资料不等于完整警方卷宗。来源相关性不等于独立佐证；模型推断不等于事实；假设权重不等于真实犯罪概率。证据不足时允许不作结论。</div>
</div>
<script>
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
async function loadJobs(){{const root=document.getElementById("jobs"),count=document.getElementById("jobCount");try{{const r=await fetch("/api/jobs?ts="+Date.now(),{{cache:"no-store"}});if(!r.ok)throw Error("registry unavailable");const d=await r.json(),jobs=d.jobs||[];count.textContent=jobs.length+" RECENT RECORDS";root.innerHTML=jobs.length?jobs.map(j=>{{const done=j.status==="done",failed=j.status==="failed",label=done?"COMPLETED":failed?"FAILED":j.status==="queued"?"AWAITING HANDLER":"IN PROGRESS";return '<div class="job"><a class="job-main" href="investigate.html?job='+encodeURIComponent(j.job_id)+'"><div class="job-top"><span class="job-id">'+esc(j.job_id.slice(0,16).toUpperCase())+'</span><span class="status '+(done?'done':failed?'failed':'')+'">'+label+'</span></div><h3>'+esc(j.direction)+'</h3><p>'+esc(j.stage_note||j.stage||'Status pending')+'</p><div class="job-bottom"><span>'+esc(j.stage||'queued')+'</span><span>'+esc(j.updated_at||j.created_at||'')+'</span></div></a>'+(done?'<a class="continue-link" href="investigate.html?continue='+encodeURIComponent(j.job_id)+'">＋ 继续调查 · 添加信源与新线索</a>':'')+'</div>'}}).join(""):'<div class="empty"><b>当前没有调查任务</b>创建新的调查委托后，任务会自动显示在这里。<br><a href="investigate.html">创建第一项调查 →</a></div>'}}catch(e){{count.textContent="TASK REGISTRY OFFLINE";root.innerHTML='<div class="empty"><b>暂时无法连接任务库</b>静态案卷仍可访问，请稍后刷新。</div>'}}}}
loadJobs();setInterval(loadJobs,15000);
</script></body></html>"""
    (public / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(built)} cases) and data/cases/index.json")


if __name__ == "__main__":
    main()
