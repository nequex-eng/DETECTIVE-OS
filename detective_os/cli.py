"""DETECTIVE OS — CLI: load a case pack, run all 8 modules, write report.

Usage:
  python -m detective_os.cli run cases/case-cn-1996-001 [--db reports/detective-os.db]
  python -m detective_os.cli check cases/case-cn-1996-001
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detective_os.core import (  # noqa: E402
    Evidence, EvidenceBoard, Entity, EntityGraph, Event, Relationship,
    Source, SourceRegistry, TimeRef, load_json)
from detective_os.reasoning import (  # noqa: E402
    Contradiction, ContradictionEngine, Hypothesis, HypothesisEngine,
    IndependentReview, InvestigationPlanner)
from detective_os import db as dbmod  # noqa: E402
from detective_os.report import render_markdown  # noqa: E402


def load_case(case_dir: Path):
    case = load_json(case_dir / "case.json")
    reg = SourceRegistry()
    for s in load_json(case_dir / "sources.json"):
        reg.add(Source(**s))
    board = EvidenceBoard(reg)
    for e in load_json(case_dir / "evidence.json"):
        board.add(Evidence(
            evidence_id=e["evidence_id"], case_id=case["case_id"],
            content=e["content"], evidence_type=e.get("evidence_type", ""),
            source_id=e.get("source_id", ""), original_quote=e.get("original_quote", ""),
            source_location=e.get("source_location", ""),
            publication_date=e.get("publication_date", ""),
            event_date=e.get("event_date", ""), grade=e["grade"],
            reliability_assessment=e.get("reliability_assessment", ""),
            verification_status=e.get("verification_status", "unverified"),
            supports=e.get("supports", []), contradicts=e.get("contradicts", []),
            analyst_notes=e.get("analyst_notes", "")))
    from detective_os.core import TimelineEngine
    tl = TimelineEngine()
    for ev in load_json(case_dir / "events.json"):
        t = ev["time"]
        tl.add(Event(event_id=ev["event_id"], case_id=case["case_id"],
                     title=ev["title"],
                     time=TimeRef(kind=t["kind"], label=t["label"],
                                  earliest=t.get("earliest", ""), latest=t.get("latest", "")),
                     persons=ev.get("persons", []), places=ev.get("places", []),
                     evidence_ids=ev.get("evidence_ids", []), notes=ev.get("notes", "")))
    graph = EntityGraph(reg)
    ents = load_json(case_dir / "entities.json")
    for en in ents["entities"]:
        graph.add_entity(Entity(entity_id=en["entity_id"], kind=en["kind"],
                                name=en["name"], is_suspect=en.get("is_suspect", False),
                                suspect_basis=en.get("suspect_basis", ""),
                                suspect_basis_grade=en.get("suspect_basis_grade", ""),
                                notes=en.get("notes", "")))
    for r in ents["relationships"]:
        graph.add_relationship(Relationship(**r))
    contra = ContradictionEngine()
    for c in load_json(case_dir / "contradictions.json"):
        contra.add(Contradiction(
            contradiction_id=c["contradiction_id"], case_id=case["case_id"],
            ctype=c["ctype"], evidence_ids=c["evidence_ids"], source_ids=c["source_ids"],
            quote_a=c["quote_a"], quote_b=c["quote_b"],
            wording_a=c["wording_a"], wording_b=c["wording_b"],
            could_be_drift=c.get("could_be_drift", ""), needs_what=c.get("needs_what", ""),
            resolvable_now=c.get("resolvable_now", False), resolution=c.get("resolution", "")))
    hyp = HypothesisEngine(board)
    for h in case["hypotheses"]:
        hyp.add(Hypothesis(
            hypothesis_id=h["hypothesis_id"], case_id=case["case_id"],
            description=h["description"], supports=h.get("supports", []),
            opposes=h.get("opposes", []), unexplained=h.get("unexplained", []),
            prerequisites=h.get("prerequisites", []), predictions=h.get("predictions", []),
            falsifiers=h.get("falsifiers", []), prior=h.get("prior", 0.0),
            likelihoods=h.get("likelihoods", {}), status=h.get("status", "open")))
    return {"case": case, "registry": reg, "board": board, "timeline": tl,
            "graph": graph, "contradictions": contra, "hypotheses": hyp}


def run_case(case_dir: Path, out_dir: Path, db_path: Path | None):
    loaded = load_case(case_dir)
    case = loaded["case"]
    bayes = loaded["hypotheses"].bayesian()
    qual = loaded["hypotheses"].qualitative_scores()
    planner = InvestigationPlanner(loaded["board"], loaded["hypotheses"],
                                   loaded["contradictions"])
    plan = planner.plan(case["case_id"])
    review = IndependentReview(loaded["board"], loaded["timeline"],
                               loaded["hypotheses"], loaded["contradictions"]).run(case["case_id"])
    md = render_markdown(case, qual, bayes, plan, review,
                         list(loaded["contradictions"].items.values()),
                         list(loaded["registry"].sources.values()))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case['case_id']}-report.md").write_text(md, encoding="utf-8")
    run_record = {"case_id": case["case_id"], "bayesian": bayes,
                  "qualitative": qual,
                  "plan": [t.__dict__ for t in plan],
                  "review": review,
                  "contradictions": [c.to_dict() for c in loaded["contradictions"].items.values()],
                  "gaps": case.get("gaps", []),
                  "limits": case.get("limits", [])}
    (out_dir / f"{case['case_id']}-report.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8")
    if db_path:
        conn = dbmod.init_db(str(db_path))
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        ev_ids = sorted(loaded["board"].items.keys())
        dbmod.record_run(conn, run_id, case["case_id"],
                         datetime.now(timezone.utc).isoformat(),
                         model="detective-os-structured-v0.1.0 (no LLM)",
                         prompt_version="n/a-structured-only",
                         evidence_ids=ev_ids, output=run_record,
                         verdict=bayes["verdict"])
        dbmod.audit(conn, case["case_id"], "cli", "reasoning_run", "reasoning_runs",
                    run_id, detail=bayes["verdict"],
                    recorded_at=datetime.now(timezone.utc).isoformat())
        conn.close()
    return {"bayes": bayes, "qualitative": qual, "plan_tasks": len(plan),
            "review": review, "report_md": str(out_dir / f"{case['case_id']}-report.md")}


def main():
    ap = argparse.ArgumentParser(prog="detective-os")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("case_dir")
    p_run.add_argument("--out", default="reports")
    p_run.add_argument("--db", default="reports/detective-os.db")
    p_check = sub.add_parser("check")
    p_check.add_argument("case_dir")
    args = ap.parse_args()
    case_dir = Path(args.case_dir)
    if args.cmd == "check":
        loaded = load_case(case_dir)
        print(f"case {loaded['case']['case_id']} loads clean:")
        print(f"  sources: {len(loaded['registry'].sources)}")
        print(f"  evidence: {len(loaded['board'].items)} "
              f"(A:{len(loaded['board'].by_grade('A'))} "
              f"B:{len(loaded['board'].by_grade('B'))} "
              f"C:{len(loaded['board'].by_grade('C'))} "
              f"D:{len(loaded['board'].by_grade('D'))} "
              f"E:{len(loaded['board'].by_grade('E'))} "
              f"F:{len(loaded['board'].by_grade('F'))} "
              f"G:{len(loaded['board'].by_grade('G'))} "
              f"H:{len(loaded['board'].by_grade('H'))})")
        print(f"  events: {len(loaded['timeline'].events)}")
        print(f"  entities: {len(loaded['graph'].entities)} "
              f"relationships: {len(loaded['graph'].relationships)}")
        print(f"  contradictions: {len(loaded['contradictions'].items)}")
        print(f"  hypotheses: {len(loaded['hypotheses'].items)}")
        return 0
    res = run_case(case_dir, Path(args.out), Path(args.db) if args.db else None)
    print(f"verdict: {res['bayes']['verdict']}")
    for s in res["bayes"]["posteriors"]:
        print(f"  {s['posterior']:.4f}  {s['hypothesis_id']} (prior {s['prior']})")
    print(f"qualitative: {res['qualitative']}")
    print(f"plan tasks: {res['plan_tasks']}")
    print(f"review: {res['review']['blockers']} blockers, passed={res['review']['passed']}")
    print(f"report: {res['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
