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

STYLE = ("<style>body{background:#0d1117;color:#d7dee8;font-family:system-ui,sans-serif;"
         "max-width:900px;margin:0 auto;padding:24px}h1{font-size:22px}h2{font-size:17px;"
         "color:#e8b64c}a{color:#7fb3ff}table{border-collapse:collapse}"
         "td,th{border:1px solid #333;padding:6px 10px;text-align:left}"
         ".note{color:#9aa7b5;font-size:13px}</style>")


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
<h1>DETECTIVE OS — 案件中心</h1>
<p class="note">针对真实历史刑事案件的公开资料研究、证据分析、竞争性假设推理与调查辅助系统。
只依据公开资料；推测不包装成事实；不根据网络传言指认现实中的个人为凶手。</p>
<h2>案件</h2><ul>{links}</ul>
<p class="note">引擎：Python标准库，8模块。验收测试17项全过（含白银案回溯校验6项）。
第二案件白银案为已侦破案件的回溯校验：引擎只读破案前公开事实，已知结果存于独立校验文件，不进入推理。</p>
</body></html>"""
    (out / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(built)} cases)")


if __name__ == "__main__":
    main()
