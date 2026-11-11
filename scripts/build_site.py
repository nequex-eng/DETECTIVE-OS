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

def discover_case_ids():
    """Discover all registered case packs instead of maintaining a hard-coded allowlist."""
    return sorted(
        p.name for p in (ROOT / "cases").iterdir()
        if p.is_dir() and (p / "case.json").is_file()
    )

STYLE = ("<style>"
         ":root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;color:#dce5ef;background:#080f19;--bg:#080f19;--panel:#101b29;--panel2:#132235;--line:#23364a;--muted:#8ea0b4;--text:#dce5ef;--gold:#d9ae58;--blue:#79aee8}"
         "*{box-sizing:border-box}body{margin:0;min-width:320px;background:radial-gradient(ellipse at 80% 0%,#17283a 0,transparent 40%),var(--bg);color:var(--text);font:14px/1.7 Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}"
         "a{color:#91bff1;text-decoration:none}a:hover{color:#c2ddff}.shell{max-width:1320px;margin:auto;padding:26px 34px 60px}"
         ".site-header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:0 0 18px;margin-bottom:26px;gap:18px}"
         ".brand{display:flex;align-items:center;gap:13px}.seal{width:44px;height:42px;display:grid;place-items:center;border:1px solid #8d7449;color:#e3c27f;font-weight:800;font-size:15px;letter-spacing:-1px}.brand b{display:block;font-size:12px;letter-spacing:1.8px}.brand small{display:block;color:#71879a;font-size:9px;letter-spacing:1.5px;margin-top:3px}"
         ".nav{display:flex;gap:9px;flex-wrap:wrap}.nav a,.action{display:inline-flex;align-items:center;padding:9px 13px;border:1px solid #344b60;background:#122235;color:#c5d4e2;font-size:11px;border-radius:4px}.nav a:hover,.action:hover{border-color:#9a7b48;color:#f1d69d}"
         ".eyebrow{font-size:9px;color:#b89a62;letter-spacing:1.8px;font-weight:700}.page-title{font-size:clamp(25px,3vw,36px);line-height:1.25;margin:8px 0 8px;font-weight:650;letter-spacing:-.5px}.meta,.note{color:var(--muted);font-size:12px;line-height:1.8}"
         ".panel{background:linear-gradient(145deg,#111f2e,#0e1926);border:1px solid var(--line);border-radius:7px;padding:19px 21px;margin:17px 0}.followup{border-color:#79633f;background:linear-gradient(120deg,#182a39,#111d2a);display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}.followup h2{margin:4px 0 6px;color:#f0d49a;font-size:19px}.followup p{margin:0;color:#a5b6c6;font-size:12px;max-width:760px}.action.primary{background:#c6a15f;border-color:#c6a15f;color:#101820;font-weight:700}.action.primary:hover{background:#e0bd7b;color:#101820}"
         "h2{font-size:18px;color:#e0c17f;margin:28px 0 12px}h3{font-size:15px}table{border-collapse:collapse;width:100%;background:#101c2a;border:1px solid var(--line);border-radius:6px;overflow:hidden}td,th{border-bottom:1px solid #26394b;padding:10px 12px;text-align:left;font-size:12px}th{color:#c5a66d;background:#142538;font-weight:650}td{color:#d0dce7}li{margin:7px 0;color:#c4d0dc;line-height:1.7}ul{padding-left:22px}.report-link{display:inline-block;margin-top:8px;color:#91bff1}"
         "@media(max-width:700px){.shell{padding:18px 15px 40px}.site-header{align-items:flex-start;flex-direction:column}.nav{width:100%}.followup{align-items:flex-start}.panel{padding:16px}}"
         "</style>")


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
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#080f19"><title>DETECTIVE OS — {esc(case['name'])}</title>{STYLE}</head><body><div class="shell">
<header class="site-header"><div class="brand"><div class="seal">D·OS</div><div><b>DETECTIVE OS</b><small>REAL CASE INTELLIGENCE & INVESTIGATION</small></div></div><nav class="nav"><a href="index.html">案件中心</a><a href="workbench.html">研究工作站</a><a href="investigate.html">自动调查</a></nav></header>
<div class="eyebrow">{'DRAFT CASE FILE / REVIEW REQUIRED' if str(case.get('status','')).startswith('draft') else 'CASE FILE / PUBLIC-SOURCE RESEARCH'}</div>
<h1 class="page-title">{esc(case['name'])}</h1>
<p class="meta">案件编号：{esc(case['case_id'])}　｜　状态：{esc(case['status'])}</p>
<p class="note">本页由案包与引擎真实输出生成，非手写结论。只依据公开资料，不代表警方卷宗；推测不包装成事实，不根据网络传言指认现实中的个人为凶手。</p>
<section class="panel followup"><div><div class="eyebrow">CONTINUE CASEWORK / 增量续办</div><h2>继续调查这个案件</h2><p>提交新的来源链接、上传TXT/MD/CSV/JSON资料、粘贴原文、补充线索并提出核查问题。系统以当前正式案卷为v1基线，只抽取新增来源，生成独立的v2报告，不覆盖原始案卷。</p></div><a class="action primary" href="investigate.html?case={case['case_id'].lower().replace('case-', 'case-')}">＋ 继续调查 · 上传资料与线索 →</a></section>
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
</div></body></html>"""
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
    for case_id in discover_case_ids():
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
            "slug": case_id,
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

    def lifecycle(row):
        if str(row.get("status", "")).startswith("draft"):
            return "draft"
        if row.get("review_passed") and row.get("evidence_count", 0) and row.get("source_count", 0):
            return "archived"
        return "review"

    def render_case_rows(rows):
        if not rows:
            return '<div class="empty">当前分类暂无案件。</div>'
        cards = []
        for row in rows:
            href = row.get("slug", row["case_id"].lower()) + ".html"
            stage = {"draft": "草稿 · 待调查", "review": "调查资料已生成 · 待复核", "archived": "阶段归档 · 可继续增量调查"}[lifecycle(row)]
            cards.append(
                f'<a class="archive-card" href="{esc(href)}">'
                f'<small>{esc(row["case_id"])} · {stage}</small>'
                f'<b>{esc(row["name"])}</b>'
                f'<span>来源 {row["source_count"]} · 证据 {row["evidence_count"]} · '
                f'复核{"通过" if row["review_passed"] else "未通过/未完成"}</span>'
                f'<em>引擎输出：{esc(row["verdict"])}</em></a>'
            )
        return "".join(cards)

    drafts = [x for x in index_rows if lifecycle(x) == "draft"]
    review_queue = [x for x in index_rows if lifecycle(x) == "review"]
    archived = [x for x in index_rows if lifecycle(x) == "archived"]
    task_drafts = read_json(ROOT / "cases" / "task-registry.json")
    task_draft_cards = "".join(
        f'<a class="archive-card" href="investigate.html?job={esc(task["job_id"])}">'
        f'<small>{esc(task["case_id"])} · 自动调查任务草稿 · 待人工复核</small>'
        f'<b>{esc(task["name"])}</b>'
        f'<span>来源记录 {task["source_count"]} · 抽取事实 {task["fact_count"]} · '
        f'复核阻断项 {task["review_blockers"]} · 覆盖率 {task["coverage_pct"]}%</span>'
        f'<em>{esc(task["limitations"])}　打开原始任务报告 →</em></a>'
        for task in task_drafts
    )
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
<div class="section"><div><div class="eyebrow">CASE LIFECYCLE / 01</div><h2>待调查 · 草稿案卷</h2></div><span>{len(drafts)} DRAFTS</span></div>
<div class="archive-grid">{render_case_rows(drafts)}</div>
<div class="section"><div><div class="eyebrow">TASK RECORDS / RECOVERED</div><h2>已完成任务 · 尚未形成完整案卷</h2></div><span>{len(task_drafts)} TASK DRAFTS</span></div>
<div class="archive-grid">{task_draft_cards or '<div class="empty">暂无待恢复的调查任务记录。</div>'}</div>
<div class="section"><div><div class="eyebrow">CASE LIFECYCLE / 02</div><h2>调查完成 · 等待复核</h2></div><span>{len(review_queue)} IN REVIEW</span></div>
<div class="archive-grid">{render_case_rows(review_queue)}</div>
<div class="section"><div><div class="eyebrow">CASE LIFECYCLE / 03</div><h2>阶段归档 · 可追溯案卷</h2></div><span>{len(archived)} ARCHIVED</span></div>
<div class="archive-grid">{render_case_rows(archived)}</div>
<p class="note">归档表示本阶段资料、报告和复核已满足归档条件，不代表案件已经侦破。未破案件也可以形成阶段归档；新增资料通过“继续调查”建立新版本，不覆盖旧案卷。</p>
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
