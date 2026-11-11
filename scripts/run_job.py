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
    collected_path = run_dir / "collected.json"
    if not collected_path.exists():
        print(f"no collected.json for {job_id}; collect sources first")
        return 1
    data = json.loads(collected_path.read_text(encoding="utf-8"))
    sources = list(data["sources"])
    texts = dict(data["texts"])
    paths_tried = list(data.get("paths_tried", []))
    # Read the structured user intake as well as the agent-collected sources.
    # User text is preserved as a separate manual source and later graded H
    # until an independent public source verifies it.
    live = job_get(job_id)
    intake = live.get("intake", {}) if isinstance(live, dict) else {}
    direction = data.get("direction") or live.get("direction", "")
    material = str(intake.get("materials", "")).strip()
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
