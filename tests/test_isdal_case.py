"""T2 acceptance: the Isdal Woman file remains an unresolved suspicious death.

No named suspect is created. The case is built only from sourced public
material, preserves interpretation conflicts, and refuses an early verdict.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.cli import load_case, run_case
from detective_os.coverage import CoverageChecklist

CASE_DIR = ROOT / "cases" / "case-no-1970-001"


class TestIsdalWomanCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load_case(CASE_DIR)
        cls.case = cls.loaded["case"]

    def test_case_pack_loads_and_has_independent_sources(self):
        self.assertEqual(self.case["case_id"], "CASE-NO-1970-001")
        registry = self.loaded["registry"]
        self.assertGreaterEqual(len(registry.sources), 4)
        self.assertGreaterEqual(
            registry.independent_source_count(list(registry.sources)), 3)
        self.assertIn("NRK", {s.publisher for s in registry.sources.values()})
        self.assertIn("BBC News", {s.publisher for s in registry.sources.values()})

    def test_every_evidence_has_source_quote_and_grade(self):
        board = self.loaded["board"]
        registry = self.loaded["registry"]
        self.assertGreaterEqual(len(board.items), 12)
        for ev in board.items.values():
            self.assertIn(ev.source_id, registry.sources)
            self.assertTrue(ev.original_quote, ev.evidence_id)
            self.assertTrue(ev.source_location, ev.evidence_id)
            self.assertIn(ev.grade, ("B", "C", "D", "E"))
        self.assertFalse(any(e.grade in ("A", "B") for e in board.items.values()),
                         "secondary reporting must not be upgraded to A/B")

    def test_no_person_is_falsely_marked_as_suspect(self):
        self.assertTrue(self.loaded["graph"].entities)
        self.assertFalse(any(e.is_suspect
                             for e in self.loaded["graph"].entities.values()))
        self.assertIn("不能先验认定为谋杀", " ".join(self.case["limits"]))

    def test_competing_death_hypotheses_refuse_early_verdict(self):
        bayes = self.loaded["hypotheses"].bayesian()
        self.assertEqual(len(bayes["posteriors"]), 4)
        gap = (bayes["posteriors"][0]["posterior"] -
               bayes["posteriors"][1]["posterior"])
        self.assertLess(gap, 0.10)
        self.assertTrue(bayes["verdict"].startswith("undecided"))

    def test_contradictions_are_recorded_as_interpretation_not_proof(self):
        contra = self.loaded["contradictions"].items
        self.assertGreaterEqual(len(contra), 3)
        self.assertIn("不等于", contra["CT01"].could_be_drift)
        self.assertIn("不能", contra["CT03"].could_be_drift)
        for c in contra.values():
            self.assertTrue(c.quote_a and c.quote_b)
            self.assertTrue(c.source_ids)
            self.assertTrue(c.needs_what)

    def test_coverage_template_is_complete_and_valid(self):
        checklist = CoverageChecklist.load(CASE_DIR)
        self.assertIsNotNone(checklist)
        self.assertEqual(len(checklist.items), 22)
        self.assertEqual(checklist.validate(self.loaded["board"]), [])
        summary = checklist.compute(self.loaded["board"],
                                    self.loaded["registry"])
        self.assertEqual(summary["total"], 18)
        self.assertGreater(summary["missing"], 0)

    def test_report_is_generated_and_review_has_no_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_case(CASE_DIR, Path(tmp), None)
            report_path = Path(tmp) / "CASE-NO-1970-001-report.md"
            data_path = Path(tmp) / "CASE-NO-1970-001-report.json"
            self.assertTrue(report_path.exists())
            self.assertTrue(data_path.exists())
            report = report_path.read_text(encoding="utf-8")
            data = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertIn("本报告回答不了的问题", report)
            self.assertTrue(data["bayesian"]["verdict"].startswith("undecided"))
            self.assertEqual(result["review"]["blockers"], 0)
            self.assertTrue(result["review"]["passed"])


if __name__ == "__main__":
    unittest.main()
