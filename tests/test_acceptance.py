"""DETECTIVE OS — acceptance tests 1-10 (spec section 8).

Run: python -m unittest discover -s tests -v
Stdlib only. Each test builds its own fixtures except where it loads
the real case pack CASE-CN-1996-001.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.core import (  # noqa: E402
    Evidence, EvidenceBoard, Source, SourceRegistry, TimeRef, Event,
    TimelineEngine, Entity, EntityGraph)
from detective_os.reasoning import (  # noqa: E402
    Contradiction, ContradictionEngine, Hypothesis, HypothesisEngine,
    IndependentReview, InvestigationPlanner)
from detective_os.cli import load_case  # noqa: E402
from detective_os import db as dbmod  # noqa: E402

CASE_DIR = ROOT / "cases" / "case-cn-1996-001"


def _src(sid, reprint_of=""):
    return Source(source_id=sid, title=f"article {sid}", publisher="paper",
                  published_at="2016-01-21", url=f"https://example.com/{sid}",
                  is_reprint=bool(reprint_of), reprint_of=reprint_of)


class TestAcceptance(unittest.TestCase):
    def test01_same_article_10_reprints_count_as_one_source(self):
        """T1: 10 reprints of one article must count as ONE independent source."""
        reg = SourceRegistry()
        reg.add(_src("ORIG"))
        for i in range(10):
            reg.add(_src(f"REP{i}", reprint_of="ORIG"))
        ids = ["ORIG"] + [f"REP{i}" for i in range(10)]
        self.assertEqual(reg.independent_source_count(ids), 1)
        self.assertEqual(len(reg.same_origin_cluster(ids)), 1)

    def test02_conflicting_time_wordings_both_kept(self):
        """T2: two reports describe one event's time differently; both kept."""
        loaded = load_case(CASE_DIR)
        contra = loaded["contradictions"].items
        self.assertIn("CT01", contra)  # 19 vs 20 years old
        c = contra["CT01"]
        self.assertTrue(c.quote_a and c.quote_b)
        self.assertIn("口径", c.could_be_drift)
        # Fuzzy time preserved: disappearance keeps "evening", no invented hour.
        ev = loaded["timeline"].events["E02"]
        self.assertEqual(ev.time.kind, "approx")
        self.assertIn("傍晚", ev.time.label)

    def test03_rumour_without_origin_is_never_a_fact(self):
        """T3: a rumour with no reliable origin cannot be listed as fact."""
        loaded = load_case(CASE_DIR)
        board = loaded["board"]
        for eid in ("F19", "F20", "F21"):
            self.assertEqual(board.items[eid].grade, "F")
            self.assertEqual(board.items[eid].weight, 0.0)
            self.assertFalse(board.items[eid].usable_as_evidence)
        for h in loaded["hypotheses"].items.values():
            for eid in ("F19", "F20", "F21", "F22", "F23", "F24", "F25"):
                self.assertNotIn(eid, h.supports)
        with self.assertRaises(ValueError):
            board.promote("F20", "A")
        with self.assertRaises(ValueError):
            board.promote("F22", "C")  # AI inference can never be promoted

    def test04_conclusion_without_evidence_is_flagged(self):
        """T4: a conclusion with no evidence must surface an evidence gap."""
        reg = SourceRegistry()
        reg.add(_src("S1"))
        board = EvidenceBoard(reg)
        hyp = HypothesisEngine(board)
        hyp.add(Hypothesis(hypothesis_id="HX", case_id="C",
                           description="baseless", supports=[], opposes=[],
                           unexplained=[], prerequisites=[],
                           predictions=["p"], falsifiers=["f"], prior=1.0))
        review = IndependentReview(board, TimelineEngine(), hyp,
                                   ContradictionEngine()).run("C")
        self.assertTrue(any(f["severity"] == "blocker" and
                            "没有任何支持证据" in f["finding"]
                            for f in review["findings"]))

    def test05_new_evidence_overturns_old_hypothesis_with_history(self):
        """T5: a run is superseded, never silently overwritten; history kept."""
        conn = dbmod.init_db(":memory:")
        dbmod.record_run(conn, "run-1", "C", "2026-11-10T00:00:00Z",
                         model="m1", prompt_version="v1",
                         evidence_ids=["E1"], output={"verdict": "leading: H1"},
                         verdict="leading: H1")
        dbmod.record_run(conn, "run-2", "C", "2026-11-10T01:00:00Z",
                         model="m1", prompt_version="v1",
                         evidence_ids=["E1", "E2"],
                         output={"verdict": "leading: H2"},
                         verdict="leading: H2", superseded_run_id="run-1")
        rows = conn.execute(
            "SELECT run_id, verdict, superseded_run_id FROM reasoning_runs"
            " ORDER BY run_id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], "leading: H1")   # old verdict preserved
        self.assertEqual(rows[1][2], "run-1")         # new run points at old
        tables = dbmod.table_list(conn)
        for t in dbmod.TABLES_14:
            self.assertIn(t, tables)

    def test06_multiple_hypotheses_fit_refuse_to_pick_early(self):
        """T6: when several hypotheses fit, refuse to crown one early."""
        loaded = load_case(CASE_DIR)
        bayes = loaded["hypotheses"].bayesian()
        self.assertTrue(bayes["verdict"].startswith("undecided"))
        top_two = bayes["posteriors"][:2]
        self.assertLess(top_two[0]["posterior"] - top_two[1]["posterior"], 0.10)

    def test07_every_factual_conclusion_traces_to_a_source(self):
        """T7: every A-grade fact links to a source that exists."""
        loaded = load_case(CASE_DIR)
        reg, board = loaded["registry"], loaded["board"]
        for e in board.items.values():
            if e.grade == "A":
                self.assertTrue(e.source_id, f"{e.evidence_id} has no source")
                self.assertIsNotNone(reg.get(e.source_id))
                self.assertTrue(e.original_quote or e.content)

    def test08_media_quote_of_police_vs_direct_police_release(self):
        """T8: 'media reports police said' vs 'police published directly' differ."""
        loaded = load_case(CASE_DIR)
        board = loaded["board"]
        f08, f09 = board.items["F08"], board.items["F09"]
        # F08 reached us via reprint (Xinhua reprinting Beijing Youth Daily).
        self.assertIn("转载", f08.reliability_assessment)
        # F09 is a direct report of a police hotline response.
        self.assertIn("直接报道", f09.reliability_assessment)
        self.assertNotEqual(f08.source_id, f09.source_id)

    def test09_unanswerable_questions_are_stated(self):
        """T9: the system must say plainly what public sources cannot answer."""
        from detective_os.report import render_markdown
        loaded = load_case(CASE_DIR)
        case = loaded["case"]
        self.assertGreaterEqual(len(case.get("gaps", [])), 6)
        self.assertTrue(any("第一现场" in g["gap"] for g in case["gaps"]))
        bayes = loaded["hypotheses"].bayesian()
        qual = loaded["hypotheses"].qualitative_scores()
        md = render_markdown(case, qual, bayes, [], {"findings": [], "blockers": 0,
                                                     "passed": True}, [], [])
        self.assertIn("回答不了的问题", md)
        self.assertIn("警方掌握但未公布的证据", md)
        self.assertIn("不得据此假装还原完整刑侦卷宗", md)

    def test10_adversarial_reviewer_actually_argues_back(self):
        """T10: the devil's advocate must cite opposing evidence, not echo."""
        loaded = load_case(CASE_DIR)
        review = IndependentReview(
            loaded["board"], loaded["timeline"], loaded["hypotheses"],
            loaded["contradictions"]).run(loaded["case"]["case_id"])
        adv = [f for f in review["findings"] if f["role"] == "adversarial"]
        self.assertTrue(adv, "no adversarial findings at all")
        self.assertTrue(all(f["cites"] for f in adv),
                        "adversarial findings must cite evidence")
        # Rigged case: leader with no counter-evidence must FAIL review.
        reg = SourceRegistry()
        reg.add(_src("S1"))
        board = EvidenceBoard(reg)
        board.add(Evidence(evidence_id="E1", case_id="C", content="x",
                           source_id="S1", grade="A",
                           reliability_assessment="r",
                           verification_status="verified"))
        hyp = HypothesisEngine(board)
        hyp.add(Hypothesis(hypothesis_id="HX", case_id="C", description="d",
                           supports=["E1"], opposes=[], unexplained=[],
                           prerequisites=[], predictions=["p"],
                           falsifiers=["f"], prior=1.0))
        bad = IndependentReview(board, TimelineEngine(), hyp,
                                ContradictionEngine()).run("C")
        self.assertTrue(any(f["role"] == "adversarial" and
                            f["severity"] == "blocker"
                            for f in bad["findings"]))

    def test_suspect_flag_requires_reliable_basis(self):
        """Guardrail: mention is not suspecthood; rumour basis is refused."""
        reg = SourceRegistry()
        g = EntityGraph(reg)
        g.add_entity(Entity(entity_id="P9", kind="person", name="Someone"))
        with self.assertRaises(ValueError):
            g.mark_suspect("P9", basis="online rumour", basis_grade="F")
        with self.assertRaises(ValueError):
            g.add_entity(Entity(entity_id="P10", kind="person", name="X",
                                is_suspect=True, suspect_basis="mentioned",
                                suspect_basis_grade="C"))


if __name__ == "__main__":
    unittest.main()
