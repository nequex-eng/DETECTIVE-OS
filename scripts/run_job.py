#!/usr/bin/env python3
"""Run one DETECTIVE OS auto-run job end to end (mechanical half).

The agent collects sources first (browser.search / browser.open) and
writes runs/<job_id>/collected.json:
  {"sources": [{source_id, title, publisher, published_at, url,
                source_type, is_reprint, reprint_of, notes}],
   "texts": {source_id: "full source text"},
   "paths_tried": [{path, status, note}]}

Then this script does the rest: extract (MiniMax, quote-verified) ->
draft pack -> engine + coverage -> draft report -> result.json ->
job status done (or failed). Usage:
  python3 scripts/run_job.py <job_id>

It never touches the two real case packs. Evidence is capped at C.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.pipeline import (  # noqa: E402
    build_draft_pack, extract_candidates, map_categories,
    propose_likelihoods, run_draft, write_draft_pack)


def job_update(job_id, *args):
    cmd = [sys.executable, str(ROOT / "scripts" / "job.py"),
           "update", job_id, *args]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(proc.stdout.strip() or proc.stderr.strip()[-300:])
    return proc.returncode


def job_get(job_id):
    """Read the live job doc ({} on any failure — the caller decides)."""
    cmd = [sys.executable, str(ROOT / "scripts" / "job.py"),
           "get", job_id]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return {}


def save_checkpoint(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def serialize_plan_tasks(tasks):
    """Convert engine InvestigationTask dataclasses into JSON-safe records."""
    fields = ("task_id", "case_id", "question", "purpose", "hypotheses",
              "expected_info", "impact_if_yes", "impact_if_no",
              "source_or_channel", "estimated_value", "status")
    return [{key: getattr(task, key, None) for key in fields}
            for task in (tasks or [])]


def build_timeline_events(evidence):
    """Build only date-anchored events from verified verbatim source quotes.

    The model's event_date field is not trusted on its own. A date must be
    visibly present in the quote; precision is kept at the level the quote
    actually supports.
    """
    events = []
    patterns = [
        ("day_range", re.compile(r"(\\d{4})年(\\d{1,2})月(\\d{1,2})日?\\s*(?:至|到|[-—])\\s*(\\d{1,2})日")),
        ("month_range", re.compile(r"(\\d{4})年(\\d{1,2})月\\s*(?:至|到|[-—])\\s*(\\d{1,2})月")),
        ("day", re.compile(r"(\\d{4})年(\\d{1,2})月(\\d{1,2})日")),
        ("iso", re.compile(r"(\\d{4})-(\\d{2})-(\\d{2})")),
        ("month", re.compile(r"(\\d{4})年(\\d{1,2})月")),
    ]
    for item in evidence or []:
        quote = str(item.get("original_quote", ""))
        found = None
        for kind, pattern in patterns:
            match = pattern.search(quote)
            if match:
                values = [int(x) for x in match.groups()]
                if kind == "day_range":
                    year, month, start, end = values
                    label = f"{year:04d}-{month:02d}-{start:02d} 至 {year:04d}-{month:02d}-{end:02d}"
                    sort_key = (year, month, start)
                    precision = "range"
                elif kind == "month_range":
                    year, start, end = values
                    label = f"{year:04d}-{start:02d} 至 {year:04d}-{end:02d}"
                    sort_key = (year, start, 1)
                    precision = "range"
                elif kind in ("day", "iso"):
                    year, month, day = values
                    label = f"{year:04d}-{month:02d}-{day:02d}"
                    sort_key = (year, month, day)
                    precision = "date"
                else:
                    year, month = values
                    label = f"{year:04d}-{month:02d}"
                    sort_key = (year, month, 1)
                    precision = "month"
                found = (sort_key, label, precision)
                break
        if not found:
            continue
        sort_key, label, precision = found
        events.append({
            "event_id": f"EV{len(events) + 1:02d}",
            "description": str(item.get("content", "")),
            "time": {"kind": precision, "label": label},
            "evidence_ids": [item.get("evidence_id", "")],
            "source_ids": [item.get("source_id", "")],
            "original_quote": quote,
        })
        events[-1]["_sort_key"] = sort_key
    events.sort(key=lambda event: event["_sort_key"])
    for event in events:
        event.pop("_sort_key", None)
    for index, event in enumerate(events, 1):
        event["event_id"] = f"EV{index:02d}"
    return events


def build_traceability_graph(sources, evidence):
    """Create a factual source↔evidence graph, not speculative people links."""
    nodes = []
    edges = []
    source_ids = set()
    for source in sources or []:
        sid = str(source.get("source_id", ""))
        if not sid:
            continue
        source_ids.add(sid)
        nodes.append({
            "entity_id": "SRC-" + sid,
            "name": str(source.get("title") or source.get("publisher") or sid),
            "kind": "source",
        })
    for item in evidence or []:
        eid = str(item.get("evidence_id", ""))
        sid = str(item.get("source_id", ""))
        if not eid:
            continue
        nodes.append({
            "entity_id": "EVD-" + eid,
            "name": f"{eid} [{item.get('grade', 'H')}] " + str(item.get("content", ""))[:100],
            "kind": "evidence",
        })
        if sid in source_ids:
            edges.append({
                "from": "EVD-" + eid,
                "relation": "cites_source",
                "to": "SRC-" + sid,
                "evidence_ids": [eid],
            })
    return {"entities": nodes, "relationships": edges}


def load_checkpoint(path, collected_mtime):
    """A checkpoint is valid only for the collected.json it was built
    from; a re-collection (new mtime) invalidates all of them."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if data.get("collected_mtime") != collected_mtime:
        return None
    return data


def main():
    if len(sys.argv) < 2:
        print("usage: run_job.py <job_id>")
        return 1
    job_id = sys.argv[1]
    run_dir = ROOT / "runs" / job_id
    run_dir.mkdir(parents=True, exist_ok=True)
    collected_path = run_dir / "collected.json"
    # Read the structured user intake before requiring agent-collected data.
    live = job_get(job_id)
    intake = live.get("intake", {}) if isinstance(live, dict) else {}
    material = str(intake.get("materials", "")).strip()
    parent_id = str(intake.get("parent_job_id", "")).strip()
    parent_report = ""
    if parent_id:
        parent_job = job_get(parent_id)
        parent_report = str((parent_job.get("result") or {}).get("report_md", "")).strip()
    if not collected_path.exists():
        if not material and not parent_report:
            print(f"no collected.json for {job_id}; public-source collection is still required")
            return 1
        # A user can submit source text without URLs and still run the
        # engine. It is kept as unverified manual input (H-grade), never C.
        seed = {"direction": live.get("direction", ""),
                "sources": [], "texts": {},
                "paths_tried": [{"path": "user_supplied", "status": "tried",
                                 "note": "仅有用户供料；尚无独立公开来源"}]}
        collected_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    data = json.loads(collected_path.read_text(encoding="utf-8"))
    sources = list(data["sources"])
    texts = dict(data["texts"])
    paths_tried = list(data.get("paths_tried", []))
    direction = data.get("direction") or live.get("direction", "")
    # User text is preserved as a separate manual source and later graded H
    # until an independent public source verifies it.
    if parent_report and not any(s.get("source_id") == "PAR01" for s in sources):
        sources.append({
            "source_id": "PAR01", "title": "父任务AI分析报告（仅作上下文）",
            "publisher": "DETECTIVE OS", "published_at": "",
            "url": "", "source_type": "ai_report", "is_reprint": False,
            "reprint_of": "", "origin_url": "", "reliability": "AI-generated inference",
            "last_verified": "", "notes": "上一轮AI报告，仅供追踪调查方向，不作为事实或证据。"
        })
        texts["PAR01"] = parent_report[:30000]
        paths_tried.append({"path": "user_supplied", "status": "tried",
                            "note": "上一轮AI报告仅作上下文，不计入证据"})
    if material and not any(s.get("source_id") == "USR01" for s in sources):
        sources.append({
            "source_id": "USR01", "title": "用户提交的补充材料",
            "publisher": "用户提供", "published_at": "",
            "url": "", "source_type": "manual", "is_reprint": False,
            "reprint_of": "", "origin_url": "", "reliability": "unverified",
            "last_verified": "", "notes": "用户提交文本；未经独立来源核验，不作为已确认事实。"
        })
        texts["USR01"] = material
        paths_tried.append({"path": "user_supplied", "status": "tried",
                            "note": "用户提交材料已纳入，待独立来源核验"})
    short = job_id[:8]
    case_id = f"CASE-DRAFT-{short}"
    collected_mtime = collected_path.stat().st_mtime
    ck_candidates = run_dir / "candidates.json"
    ck_likelihoods = run_dir / "likelihoods.json"
    ck_categories = run_dir / "categories.json"
    try:
        # Resume-aware first update: a run killed mid-flight (VM
        # restart) leaves the job at extracting/reasoning; demanding
        # "collecting" would refuse and the checkpoints below would
        # never be reached. A fresh run still goes through collecting.
        live = job_get(job_id)
        if live.get("status") in ("extracting", "reasoning"):
            job_update(job_id, "--note", "断点续跑：从检查点继续",
                       "--event", "断点续跑：复用已完成的抽取/拟合结果")
        else:
            job_update(job_id, "--status", "extracting", "--stage", "extracting",
                       "--expect-status", "collecting",
                       "--note", "正在抽取事实", "--event", "开始抽取：逐字引用核验")
        ck = load_checkpoint(ck_candidates, collected_mtime)
        if ck is not None:
            candidates = ck["candidates"]
            failed_sources = ck["failed_sources"]
            print(f"resumed: {len(candidates)} candidates from checkpoint")
        else:
            candidates = []
            failed_sources = []
            for s in sources:
                text = texts.get(s["source_id"], "")
                if not text:
                    continue
                try:
                    got = extract_candidates(text, s["source_id"], direction)
                except Exception as exc:  # noqa: BLE001 - one flaky source
                    # must not kill the whole job; the draft says which
                    # sources contributed nothing.
                    print(f"{s['source_id']}: extraction failed ({exc}); skipping")
                    failed_sources.append(s["source_id"])
                    continue
                print(f"{s['source_id']}: {len(got)} candidates verified")
                candidates.extend(got)
            if not candidates:
                raise RuntimeError(
                    f"no verified facts extracted from any source "
                    f"(failed: {failed_sources or 'none'})")
            save_checkpoint(ck_candidates, {
                "collected_mtime": collected_mtime,
                "candidates": candidates, "failed_sources": failed_sources})
        if failed_sources:
            print(f"note: sources with no extraction: {failed_sources}")
        pack = build_draft_pack(case_id, direction + "（草稿）", direction,
                                job_id, sources, candidates, paths_tried)
        job_update(job_id, "--note", "正在拟合假设似然与覆盖映射",
                   "--expect-status", "extracting",
                   "--event", f"抽取完成：{len(candidates)}条事实，拟合似然与覆盖映射")
        likelihoods = None
        ck = load_checkpoint(ck_likelihoods, collected_mtime)
        if ck is not None:
            likelihoods = {(k.split("|", 1)[0], k.split("|", 1)[1]): v
                           for k, v in ck["likelihoods"].items()}
            print(f"resumed: {len(likelihoods)} likelihood pairs "
                  f"from checkpoint")
        else:
            likelihoods = propose_likelihoods(pack["evidence"])
            print(f"likelihood proposals: {len(likelihoods)} pairs")
            save_checkpoint(ck_likelihoods, {
                "collected_mtime": collected_mtime,
                "likelihoods": {f"{h}|{e}": v
                                for (h, e), v in likelihoods.items()}})
        cats = None
        ck = load_checkpoint(ck_categories, collected_mtime)
        if ck is not None:
            cats = ck["categories"]
            print(f"resumed: {len(cats)} category mappings from checkpoint")
        else:
            cats = map_categories(pack["evidence"])
            print(f"category mappings: {len(cats)} evidence items mapped")
            save_checkpoint(ck_categories, {
                "collected_mtime": collected_mtime, "categories": cats})
        pack = build_draft_pack(case_id, direction + "（草稿）", direction,
                                job_id, sources, candidates, paths_tried,
                                likelihoods=likelihoods, categories=cats)
        case_dir = write_draft_pack(ROOT / "cases" / f"draft-{short}", pack)
        job_update(job_id, "--status", "reasoning", "--stage", "reasoning",
                   "--expect-status", "extracting",
                   "--note", "正在推理与覆盖检查",
                   "--event", "草稿包已生成，开始引擎推理")
        out_dir = ROOT / "reports"
        md_path, summary = run_draft(case_dir, out_dir)
        report_md = md_path.read_text(encoding="utf-8")
        cov = summary["coverage"]
        score_pct = round(cov["score"] * 100, 1)
        result = {
            "case_id": case_id,
            "case_name": direction + "（草稿）",
            "verdict": summary["bayes"]["verdict"],
            "posteriors": [{"hypothesis_id": p["hypothesis_id"],
                            "posterior": p["posterior"], "prior": p["prior"]}
                           for p in summary["bayes"]["posteriors"]],
            "source_count": len(sources),
            "fact_count": len(candidates),
            "sources": [{"source_id": s.get("source_id", ""),
                         "title": s.get("title", ""),
                         "publisher": s.get("publisher", ""),
                         "published_at": s.get("published_at", ""),
                         "url": s.get("url", ""),
                         "source_type": s.get("source_type", "")}
                        for s in sources],
            "evidence": [{"evidence_id": e.get("evidence_id", ""),
                          "content": e.get("content", ""),
                          "original_quote": e.get("original_quote", ""),
                          "source_id": e.get("source_id", ""),
                          "source_location": e.get("source_location", ""),
                          "grade": e.get("grade", "H"),
                          "verification_status": e.get("verification_status", "")}
                         for e in pack.get("evidence", [])],
            "coverage": {"score_pct": score_pct,
                         "covered": cov["covered"],
                         "single": cov["single"], "missing": cov["missing"],
                         "total": cov["total"],
                         "missing_ids": cov.get("missing_ids", []),
                         "single_ids": cov.get("single_ids", []),
                         "items": cov.get("items", [])},
            "review_blockers": summary["review"]["blockers"],
            "review_passed": summary["review"].get("passed", False),
            "review_findings": summary["review"].get("findings", []),
            # Expose structured engine records to the UI. Empty arrays are
            # intentional: the draft collector must not fabricate timeline,
            # graph edges, or contradictions it has not actually established.
            "hypotheses_detail": pack["case"].get("hypotheses", []),
            "timeline_events": pack.get("events") or build_timeline_events(pack.get("evidence", [])),
            "entities": {
                "entities": (pack.get("entities") or {}).get("entities", []) +
                            build_traceability_graph(sources, pack.get("evidence", []))["entities"],
                "relationships": (pack.get("entities") or {}).get("relationships", []) +
                                 build_traceability_graph(sources, pack.get("evidence", []))["relationships"],
            },
            "contradictions": pack.get("contradictions", []),
            "investigation_plan": serialize_plan_tasks(summary.get("plan_tasks", [])),
            "report_md": report_md,
        }
        (run_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        job_update(job_id, "--status", "done", "--stage", "done",
                   "--expect-status", "reasoning",
                   "--note", "草稿报告已生成",
                   "--event", f"完成：{len(candidates)}条事实，覆盖{score_pct}%",
                   "--result", str(run_dir / "result.json"))
        print(f"done: {case_id}, verdict={summary['bayes']['verdict']}, "
              f"coverage={score_pct}%")
        return 0
    except Exception as exc:  # noqa: BLE001 - report and mark failed
        job_update(job_id, "--status", "failed", "--stage", "failed",
                   "--note", "任务失败", "--error", str(exc)[:500])
        print(f"failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
