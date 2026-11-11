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
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DETECTIVE OS — 案件中心</title>{STYLE}</head><body>
<h1>DETECTIVE OS — 案件中心</h1>
<p class="note">针对真实历史刑事案件的公开资料研究、证据分析、竞争性假设推理与调查辅助系统。
只依据公开资料；推测不包装成事实；不根据网络传言指认现实中的个人为凶手。</p>
<div class="actions"><a class="action" href="workbench.html">打开十模块研究工作站 →</a><a class="action" href="investigate.html">开始自动调查 →</a></div>
<h2>案件</h2><ul>{links}</ul>
<p class="note">所有统计、排序、调查计划和审查结果均由结构化引擎生成；没有报告的案件不填充演示数据。
研究工作站为只读静态数据视图，不会创建调查任务或修改生产KV。</p>
</body></html>"""
    (public / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(built)} cases) and data/cases/index.json")


if __name__ == "__main__":
    main()
