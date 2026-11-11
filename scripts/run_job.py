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


def serialize_plan_tasks(tasks):
    """Convert InvestigationTask objects into JSON-safe public records."""
    fields = (
        "task_id", "case_id", "question", "purpose", "hypotheses",
        "expected_info", "impact_if_yes", "impact_if_no",
        "source_or_channel", "estimated_value", "status",
    )
    out = []
    for task in tasks or []:
        row = {}
        for name in fields:
            value = getattr(task, name, None)
            if isinstance(value, Path):
                value = str(value)
            row[name] = value
        out.append(row)
    return out


def build_timeline_events(evidence):
    """Build only dates explicitly visible in each verbatim source quote.

    Content summaries and model-suggested event_date values are not used
    to create timeline dates. A range is preserved as a range.
    """
    import re
    from datetime import date

    def iso(y, m, d):
        try:
            return date(int(y), int(m), int(d)).isoformat()
        except (TypeError, ValueError):
            return None

    range_re = re.compile(
        r"(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d1>\d{1,2})日"
        r"\s*(?:至|到|—|－|-|~|～)\s*"
        r"(?:(?P<y2>\d{4})年)?(?:(?P<m2>\d{1,2})月)?"
        r"(?P<d2>\d{1,2})日?")
    date_re = re.compile(r"(?P<y>\d{4})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日")
    iso_re = re.compile(r"(?<!\d)(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?!\d)")
    events = []
    for item in evidence or []:
        quote = str(item.get("original_quote", ""))
        if not quote:
            continue
        evidence_id = str(item.get("evidence_id", ""))
        match = range_re.search(quote)
        if match:
            y1, m1, d1 = match.group("y", "m", "d1")
            y2 = match.group("y2") or y1
            m2 = match.group("m2") or m1
            start, end = iso(y1, m1, d1), iso(y2, m2, match.group("d2"))
            if start and end:
                events.append({
                    "event_id": f"EVT-{evidence_id}",
                    "title": str(item.get("content", "")),
                    "time": {"kind": "range", "label": f"{start}至{end}",
                             "earliest": start, "latest": end},
                    "evidence_ids": [evidence_id],
                    "source_ids": [item.get("source_id", "")] if item.get("source_id") else [],
                })
            continue
        match = date_re.search(quote)
        if match:
            y, m, d = match.group("y", "m", "d")
        else:
            match = iso_re.search(quote)
            if not match:
                continue
            y, m, d = match.group("y", "m", "d")
        value = iso(y, m, d)
        if value:
            events.append({
                "event_id": f"EVT-{evidence_id}",
                "title": str(item.get("content", "")),
                "time": {"kind": "date", "label": value,
                         "earliest": value, "latest": value},
                "evidence_ids": [evidence_id],
                "source_ids": [item.get("source_id", "")] if item.get("source_id") else [],
            })
    events.sort(key=lambda row: (row["time"]["earliest"], row["event_id"]))
    return events


def build_traceability_graph(sources, evidence):
    """Create source/evidence nodes and citation edges only for known IDs."""
    source_ids = {str(source.get("source_id", "")) for source in sources or []}
    entities = []
    relationships = []
    for source in sources or []:
        sid = str(source.get("source_id", ""))
        if not sid:
            continue
        entities.append({
            "entity_id": f"SRC-{sid}", "kind": "source",
            "name": str(source.get("title", sid)),
            "publisher": str(source.get("publisher", "")),
        })
    for item in evidence or []:
        eid = str(item.get("evidence_id", ""))
        if not eid:
            continue
        entities.append({
            "entity_id": f"EVD-{eid}", "kind": "evidence",
            "name": str(item.get("content", "")),
            "grade": str(item.get("grade", "")),
        })
        sid = str(item.get("source_id", ""))
        if sid and sid in source_ids:
            relationships.append({
                "from": f"EVD-{eid}", "to": f"SRC-{sid}",
                "relation": "cites",
            })
    return {"entities": entities, "relationships": relationships}



def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {} if default is None else default


def source_key(source):
    """Canonical identity for deduplicating reprints across follow-up runs."""
    url = str(source.get("origin_url") or source.get("url") or "").strip()
    if url:
        return url.split("#", 1)[0].rstrip("/").lower()
    return "meta:" + "|".join(
        str(source.get(k, "")).strip().lower()
        for k in ("publisher", "title", "published_at"))


def merge_followup_sources(parent_sources, parent_texts,
                           new_sources, new_texts):
    """Keep the old corpus and append only genuinely new source origins.

    Existing source IDs stay stable. New source IDs are assigned after the
    existing corpus so old candidate references remain valid.
    """
    merged = []
    texts = {}
    seen = set()
    for source in parent_sources or []:
        row = dict(source)
        sid = str(row.get("source_id") or f"S{len(merged) + 1:02d}")
        row["source_id"] = sid
        key = source_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        old_text = (parent_texts or {}).get(source.get("source_id", ""), "")
        if old_text:
            texts[sid] = str(old_text)[:12000]

    new_ids = []
    remap = {}
    for source in new_sources or []:
        old_id = str(source.get("source_id", ""))
        key = source_key(source)
        if key in seen:
            continue
        seen.add(key)
        sid = f"S{len(merged) + 1:02d}"
        row = dict(source)
        row["source_id"] = sid
        merged.append(row)
        remap[old_id] = sid
        new_ids.append(sid)
        value = (new_texts or {}).get(old_id, "")
        if value:
            texts[sid] = str(value)[:12000]
    return merged, texts, new_ids, remap


def build_case_summary(direction, candidates, verdict, coverage,
                       review_blockers, version, new_fact_count):
    facts = candidates[-min(len(candidates), 6):]
    fact_lines = "\n".join(
        f"- {item.get('content', '')}（来源：{item.get('source_id', '未知')}）"
        for item in facts if item.get("content"))
    if not fact_lines:
        fact_lines = "- 本轮没有可逐字引用核验的新增候选事实。"
    return (
        f"## 案件总结（v{version}）\n\n"
        "本节由跑手依据已采集来源与引擎输出整理，非引擎原生结论。\n\n"
        f"### 事件背景\n调查方向：{direction}。本轮为既有调查的增量跟进。\n\n"
        "### 来源原文抽取的关键事实（仍待人工复核）\n"
        f"{fact_lines}\n\n"
        "### 引擎结论及其含义\n"
        f"{verdict}。这是竞争性假设的相对模型排序，不代表任何个人的犯罪概率；"
        "若排序差距不足或证据不足，应保留无法判断。\n\n"
        "### 主要缺口与注意事项\n"
        f"资料覆盖：{coverage.get('score_pct', 0)}%；"
        f"已覆盖{coverage.get('covered', 0)}项、单来源{coverage.get('single', 0)}项、"
        f"缺失{coverage.get('missing', 0)}项；独立审查blocker：{review_blockers}。"
        f"本版本新增抽取{new_fact_count}条候选事实。所有自动抽取仍需人工复核，"
        "用户提供的文字与线索不直接作为证据。"
    )


def read_parent_checkpoint(parent_run_dir, parent_result):
    """Recover the parent source corpus and candidate checkpoints.

    Prefer workspace checkpoints (which preserve exact source text); fall
    back to the previous KV result for runs created by newer versions.
    """
    collected = load_json(parent_run_dir / "collected.json", {})
    candidates_doc = load_json(parent_run_dir / "candidates.json", {})
    likelihoods_doc = load_json(parent_run_dir / "likelihoods.json", {})
    categories_doc = load_json(parent_run_dir / "categories.json", {})

    parent_sources = collected.get("sources") or parent_result.get("sources") or []
    parent_texts = collected.get("texts") or parent_result.get("source_texts") or {}
    parent_candidates = candidates_doc.get("candidates") or parent_result.get("candidates") or []
    parent_likelihoods = likelihoods_doc.get("likelihoods") or parent_result.get("likelihoods") or {}
    parent_categories = categories_doc.get("categories") or parent_result.get("categories") or {}

    if not parent_candidates:
        draft_path = parent_result.get("draft_pack_path")
        if draft_path:
            pack_dir = ROOT / draft_path
        else:
            pack_dir = ROOT / "cases" / f"draft-{parent_run_dir.name[:8]}"
        evidence = load_json(pack_dir / "evidence.json", [])
        parent_candidates = [{
            "content": e.get("content", ""),
            "quote": e.get("original_quote", ""),
            "source_location": e.get("source_location", ""),
            "evidence_type": e.get("evidence_type", "fact"),
            "event_date": e.get("event_date", ""),
            "category": "",
            "source_id": e.get("source_id", "")
        } for e in evidence]
    if not parent_candidates:
        raise RuntimeError(
            "原调查的候选事实检查点与草稿证据档案均不可用，无法增量续办；"
            "为避免伪造或从零重跑，任务已停止。")
    return (collected, parent_sources, parent_texts, parent_candidates,
            parent_likelihoods, parent_categories)


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

    data = load_json(collected_path, {})
    live = job_get(job_id)
    intake = live.get("intake", {}) if isinstance(live.get("intake"), dict) else {}
    parent_id = live.get("parent_job_id") or intake.get("parent_job_id")
    direction = data.get("direction") or live.get("direction", "")
    if not direction:
        raise RuntimeError("任务缺少调查方向")

    parent = {}
    parent_result = {}
    parent_candidates = []
    parent_likelihoods = {}
    parent_categories = {}
    parent_sources = []
    parent_texts = {}
    parent_paths = []
    previous_verdict = None
    root_job_id = job_id
    version = 1
    if parent_id:
        parent = job_get(parent_id)
        if parent.get("status") != "done" or not parent.get("result"):
            raise RuntimeError("原调查任务不存在或未完成，不能继续调查")
        parent_result = parent["result"]
        if not isinstance(parent_result, dict):
            raise RuntimeError("原调查结果格式异常，不能继续调查")
        parent_run_dir = ROOT / "runs" / parent_id
        (parent_collected, parent_sources, parent_texts, parent_candidates,
         parent_likelihoods, parent_categories) = read_parent_checkpoint(
            parent_run_dir, parent_result)
        parent_paths = parent_collected.get("paths_tried", [])
        previous_verdict = parent_result.get("verdict")
        root_job_id = parent_result.get("root_job_id") or parent_id
        version = int(parent_result.get("version") or parent.get("version") or 1) + 1

    new_sources = data.get("sources", [])
    new_texts = data.get("texts", {})
    if parent_id:
        if data.get("parent_job_id") == parent_id and data.get("new_source_ids"):
            # A previous attempt already wrote the merged corpus. Reuse its
            # stable IDs and checkpoints instead of merging it a second time.
            sources = data.get("sources", [])
            texts = data.get("texts", {})
            new_source_ids = data.get("new_source_ids", [])
            paths_tried = data.get("paths_tried", [])
        else:
            sources, texts, new_source_ids, remap = merge_followup_sources(
                parent_sources, parent_texts, new_sources, new_texts)
            if not new_source_ids:
                raise RuntimeError(
                    "本轮没有新增的独立来源。请跑手继续搜索并打开新来源；"
                    "重复转载或仅有用户粘贴文本不能作为新增证据。")
            paths_tried = list(parent_paths) + list(data.get("paths_tried", []))
            data = {
                "direction": direction, "sources": sources, "texts": texts,
                "paths_tried": paths_tried, "parent_job_id": parent_id,
                "new_source_ids": new_source_ids, "source_id_remap": remap
            }
            collected_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        case_id = parent_result.get("case_id") or f"CASE-DRAFT-{root_job_id[:8]}"
        case_name = parent_result.get("case_name") or direction + "（草稿）"
    else:
        sources, texts = new_sources, new_texts
        new_source_ids = [str(s.get("source_id")) for s in sources if s.get("source_id")]
        paths_tried = data.get("paths_tried", [])
        case_id = f"CASE-DRAFT-{job_id[:8]}"
        case_name = direction + "（草稿）"

    collected_mtime = collected_path.stat().st_mtime
    ck_candidates = run_dir / "candidates.json"
    ck_likelihoods = run_dir / "likelihoods.json"
    ck_categories = run_dir / "categories.json"

    try:
        if parent_id and (not parent_result or parent.get("status") != "done"):
            raise RuntimeError("无法读取原调查基线，停止续办以避免覆盖或丢失原结果")
        live = job_get(job_id)
        if live.get("status") in ("extracting", "reasoning"):
            job_update(job_id, "--note", "断点续跑：从检查点继续",
                       "--event", "断点续跑：复用已完成的抽取/拟合结果")
        else:
            job_update(job_id, "--status", "extracting", "--stage", "extracting",
                       "--expect-status", "collecting",
                       "--note", "正在抽取新增来源", "--event", "开始抽取新增来源：逐字引用核验")

        ck = load_checkpoint(ck_candidates, collected_mtime)
        if ck is not None:
            candidates = ck["candidates"]
            failed_sources = ck.get("failed_sources", [])
            new_fact_count = ck.get("new_fact_count", 0)
            print(f"resumed: {len(candidates)} candidates from checkpoint")
        else:
            candidates = list(parent_candidates)
            failed_sources = []
            new_candidates = []
            for sid in new_source_ids:
                source_text = texts.get(sid, "")
                if not source_text:
                    failed_sources.append(sid)
                    continue
                try:
                    got = extract_candidates(
                        source_text, sid,
                        direction + "\n本轮补充核查重点（仅作待核实线索）：\n"
                        + str(intake.get("questions", "")) + "\n"
                        + str(intake.get("known_facts", "")) + "\n"
                        + str(intake.get("materials", "")) + "\n"
                        + str(intake.get("user_source_text", ""))[:10000])
                except Exception as exc:  # noqa: BLE001
                    print(f"{sid}: extraction failed ({exc}); skipping")
                    failed_sources.append(sid)
                    continue
                print(f"{sid}: {len(got)} new candidates verified")
                new_candidates.extend(got)
            new_fact_count = len(new_candidates)
            if not new_candidates:
                raise RuntimeError("新增来源未抽取出任何可逐字引用核验的候选事实")
            candidates.extend(new_candidates)
            save_checkpoint(ck_candidates, {
                "collected_mtime": collected_mtime,
                "candidates": candidates, "failed_sources": failed_sources,
                "new_fact_count": new_fact_count, "new_source_ids": new_source_ids})

        if failed_sources:
            print(f"note: sources with no extraction: {failed_sources}")

        # Build once to obtain the final stable evidence IDs, then only ask
        # the LLM to score/map the newly added evidence.
        draft = build_draft_pack(
            case_id, case_name, direction, job_id, sources, candidates, paths_tried,
            likelihoods=parent_likelihoods, categories=parent_categories)
        old_count = len(parent_candidates)
        new_evidence = draft["evidence"][old_count:]

        ck = load_checkpoint(ck_likelihoods, collected_mtime)
        if ck is not None:
            likelihoods = {
                (k.split("|", 1)[0], k.split("|", 1)[1]): v
                for k, v in ck["likelihoods"].items()
            }
        else:
            likelihoods = {
                (k.split("|", 1)[0], k.split("|", 1)[1]): v
                for k, v in parent_likelihoods.items()
                if "|" in k
            }
            likelihoods.update(propose_likelihoods(new_evidence))
            save_checkpoint(ck_likelihoods, {
                "collected_mtime": collected_mtime,
                "likelihoods": {f"{h}|{e}": v for (h, e), v in likelihoods.items()}})

        ck = load_checkpoint(ck_categories, collected_mtime)
        if ck is not None:
            categories = ck["categories"]
        else:
            categories = dict(parent_categories)
            categories.update(map_categories(new_evidence))
            save_checkpoint(ck_categories, {
                "collected_mtime": collected_mtime, "categories": categories})

        pack = build_draft_pack(
            case_id, case_name, direction, job_id, sources, candidates, paths_tried,
            likelihoods=likelihoods, categories=categories)

        if parent_id:
            root_short = root_job_id[:8]
            draft_dir_name = f"draft-{root_short}-v{version}"
            out_dir = ROOT / "reports" / "versions" / case_id / f"v{version}"
        else:
            draft_dir_name = f"draft-{job_id[:8]}"
            out_dir = ROOT / "reports"

        case_dir = write_draft_pack(ROOT / "cases" / draft_dir_name, pack)
        job_update(job_id, "--status", "reasoning", "--stage", "reasoning",
                   "--expect-status", "extracting",
                   "--note", f"正在生成v{version}报告与复核",
                   "--event", "增量草稿包已生成，开始重跑引擎与覆盖率")
        md_path, engine_summary = run_draft(case_dir, out_dir)
        cov = engine_summary["coverage"]
        score_pct = round(cov["score"] * 100, 1)
        posteriors = [{
            "hypothesis_id": p["hypothesis_id"],
            "posterior": p["posterior"], "prior": p["prior"]
        } for p in engine_summary["bayes"]["posteriors"]]
        verdict = engine_summary["bayes"]["verdict"]
        coverage = {
            "score_pct": score_pct, "covered": cov["covered"],
            "single": cov["single"], "missing": cov["missing"],
            "total": cov["total"]
        }
        case_summary = build_case_summary(
            direction, candidates, verdict, coverage,
            engine_summary["review"]["blockers"], version, new_fact_count)
        report_md = md_path.read_text(encoding="utf-8")
        report_md += "\n\n" + case_summary + "\n"
        md_path.write_text(report_md, encoding="utf-8")

        result = {
            "case_id": case_id, "case_name": case_name,
            "root_job_id": root_job_id, "parent_job_id": parent_id,
            "version": version, "previous_verdict": previous_verdict,
            "verdict": verdict, "posteriors": posteriors,
            "coverage": coverage,
            "review_blockers": engine_summary["review"]["blockers"],
            "source_count": len(sources), "new_source_count": len(new_source_ids),
            "fact_count": len(candidates), "new_fact_count": new_fact_count,
            "draft_pack_path": str(case_dir.relative_to(ROOT)),
            "report_path": str(md_path.relative_to(ROOT)),
            "sources": sources, "source_texts": texts,
            "candidates": candidates,
            "likelihoods": {f"{h}|{e}": v for (h, e), v in likelihoods.items()},
            "categories": categories, "paths_tried": paths_tried,
            "summary": case_summary, "report_md": report_md
        }
        (run_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        job_update(job_id, "--status", "done", "--stage", "done",
                   "--expect-status", "reasoning",
                   "--note", f"v{version}增量报告已生成",
                   "--event", f"完成v{version}：新增来源{len(new_source_ids)}个，新增事实{new_fact_count}条，覆盖{score_pct}%",
                   "--result", str(run_dir / "result.json"))
        print(f"done: {case_id} v{version}, verdict={verdict}, "
              f"coverage={score_pct}%, new_facts={new_fact_count}")
        return 0
    except Exception as exc:  # noqa: BLE001
        job_update(job_id, "--status", "failed", "--stage", "failed",
                   "--note", "任务失败", "--error", str(exc)[:500])
        print(f"failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
