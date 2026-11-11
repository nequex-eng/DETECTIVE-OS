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

STYLE = """<style>
:root{color-scheme:dark;--bg:#09111b;--panel:#121e2c;--line:#2a3a4d;--muted:#8fa2b7;--text:#e6edf5;--gold:#e7b84f;--blue:#84baff;--green:#74d9b5}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 18% -8%,#1a3045 0,transparent 42%),var(--bg);color:var(--text);font:14px/1.65 system-ui,-apple-system,sans-serif;max-width:1180px;padding:28px;margin:0 auto}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}.top{display:flex;justify-content:space-between;align-items:center;gap:16px}.brand{display:flex;align-items:center;gap:12px}.mark{width:42px;height:42px;border:1px solid #8c743d;border-radius:12px;display:grid;place-items:center;color:var(--gold);font-size:22px;background:#241f15}.eyebrow,.kicker{font-size:10px;letter-spacing:.17em;color:var(--gold);font-weight:700}h1{font-size:22px;margin:0}h2{font-size:16px;color:var(--gold)}h3{font-size:17px;margin:6px 0}.muted,.note{color:var(--muted);font-size:12px}.hero{margin:24px 0;padding:30px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(135deg,#172a3e,#101a27)}.hero h2{font-size:30px;line-height:1.25;color:var(--text);margin:8px 0 12px}.hero p{color:#b5c3d1;max-width:780px}.btn{display:inline-block;padding:11px 17px;border-radius:9px;background:var(--gold);color:#17130b;font-weight:750;margin:10px 8px 0 0}.btn.secondary{background:#22364b;border:1px solid #405a75;color:#e3edf8}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.case-card,.panel{display:block;background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:18px;color:var(--text)}.case-card:hover{border-color:#987a3e;text-decoration:none;transform:translateY(-1px)}.case-meta{color:var(--muted);font-size:11px;margin-top:10px}.stats{display:flex;gap:24px;flex-wrap:wrap;margin-top:20px}.stats strong{display:block;font-size:20px;color:var(--gold)}.safety{border-left:3px solid var(--gold);background:#211f19;padding:11px 14px;border-radius:0 8px 8px 0;color:#c7c0ad;font-size:12px;margin:17px 0}.section{margin:24px 0}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.panel{padding:16px}.panel b{color:var(--gold)}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:9px;text-align:left}th{color:var(--muted)}.footer{padding:25px 0;text-align:center;color:var(--muted);font-size:11px}
@media(max-width:720px){body{padding:14px}.hero{padding:20px}.hero h2{font-size:24px}.cards,.grid3{grid-template-columns:1fr}.topnav{display:none}}
</style>"""


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
    cards = "".join(
        f'<a class="case-card" href="{cid}.html">'
        f'<div class="kicker">{esc(r["case"]["case_id"])}</div>'
        f'<h3>{esc(r["case"]["name"])}</h3>'
        f'<div>{esc(r["report"]["bayesian"]["verdict"])}</div>'
        f'<div class="case-meta">证据{len(json.loads((ROOT / "cases" / cid / "evidence.json").read_text(encoding="utf-8")))}条 · '
        f'来源{len(json.loads((ROOT / "cases" / cid / "sources.json").read_text(encoding="utf-8")))}个 · '
        f'{esc(r["case"]["status"])}</div></a>'
        for cid, r in built)
    index = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="DETECTIVE OS真实案件公开资料研究、证据管理与可追溯推理工作站">
<title>DETECTIVE OS — Real Case Intelligence</title>{STYLE}</head><body>
<header class="top"><div class="brand"><div class="mark">⌕</div><div><div class="eyebrow">REAL CASE INTELLIGENCE</div><h1>DETECTIVE OS</h1></div></div>
<div class="topnav"><a href="investigate.html">调查工作站</a>　<a href="https://github.com/nequex-eng/DETECTIVE-OS">GitHub</a></div></header>
<section class="hero"><div class="eyebrow">PUBLIC-SOURCE INVESTIGATION ENGINE</div>
<h2>把线索变成可核验的证据链。</h2>
<p>面向真实历史刑事案件的公开资料研究、证据分析、时间线重建、矛盾识别、竞争性假设与反方审查。每一项结论都应能回溯到来源；不知道的事情，就明确标记为未知。</p>
<a class="btn" href="investigate.html">创建调查委托 →</a><a class="btn secondary" href="#cases">浏览案件档案</a>
<div class="safety">研究范围仅限合法公开资料。AI推断和用户供料不作为已核实证据；不根据网络传言指认现实个人为凶手。自动报告均为未审草稿。</div></section>
<section class="section"><div class="kicker">HOW IT WORKS</div><h2>一份委托，完整调查流程</h2>
<div class="grid3"><div class="panel"><b>01 · Collect</b><p>检索公开资料，打开原始页面，识别转载链与来源独立性。</p></div>
<div class="panel"><b>02 · Structure</b><p>抽取事实、原文引用、证据等级、时间线与待核实缺口。</p></div>
<div class="panel"><b>03 · Challenge</b><p>比较竞争假设，主动寻找反证，生成覆盖率与审查报告。</p></div></div></section>
<section class="section" id="cases"><div class="kicker">CASE ARCHIVE</div><h2>案件档案</h2><div class="cards">{cards}</div></section>
<section class="section"><div class="kicker">ENGINE RULES</div><h2>不把推断伪装成事实</h2>
<p class="note">证据分级、转载去重、引用核验、证据截止日期与独立审查共同约束自动分析。资料缺失不是失败；结论不确定时，系统必须拒绝过早选定。</p></section>
<footer class="footer">DETECTIVE OS · REAL CASE INTELLIGENCE & INVESTIGATION ENGINE</footer>
</body></html>"""
    (out / "index.html").write_text(index, encoding="utf-8")
    print(f"built index.html ({len(built)} cases)")


if __name__ == "__main__":
    main()
