"""DETECTIVE OS — coverage checklist tests (module 9).

Run: python -m unittest discover -s tests -v
Stdlib only.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.core import (  # noqa: E402
    Evidence, EvidenceBoard, Source, SourceRegistry)
from detective_os.coverage import (  # noqa: E402
    COLLECTION_PATHS, CoverageChecklist, CoverageItem, template_items)
from detective_os.cli import load_case  # noqa: E402

NANDA_DIR = ROOT / "cases" / "case-cn-1996-001"
BAIYIN_DIR = ROOT / "cases" / "case-cn-1988-001"


def _reg_with(*sources):
    reg = SourceRegistry()
    for s in sources:
        reg.add(s)
    return reg


def _src(sid, reprint_of=""):
    return Source(source_id=sid, title=f"article {sid}", publisher="paper",
                  published_at="2016-01-21", url=f"https://example.com/{sid}",
                  is_reprint=bool(reprint_of), reprint_of=reprint_of)


def _board(reg, *evs):
    board = EvidenceBoard(reg)
    for eid, grade, sid in evs:
        board.add(Evidence(evidence_id=eid, case_id="CASE-TEST",
                           content=f"fact {eid}", grade=grade, source_id=sid,
                           reliability_assessment="test reason" if grade in ("A", "B") else ""))
    return board


def _item(iid, evidence_ids):
    return CoverageItem(item_id=iid, category="测试", title=f"item {iid}",
                        question="?", evidence_ids=list(evidence_ids))


class TestTemplate(unittest.TestCase):
    def test_template_shape(self):
        items = template_items()
        self.assertEqual(len(items), 22)
        self.assertEqual(len({i["item_id"] for i in items}), 22)
        self.assertEqual(len({i["category"] for i in items}), 10)
        self.assertEqual([i["item_id"] for i in items][:3], ["C01", "C02", "C03"])

    def test_collection_paths(self):
        self.assertEqual(len(COLLECTION_PATHS), 10)
        for p in ("web_search", "direct_source", "news_db", "web_archive",
                  "court_db", "local_language", "books_media",
                  "user_supplied", "community_lead", "foia"):
            self.assertIn(p, COLLECTION_PATHS)


class TestCompute(unittest.TestCase):
    def test_reprints_count_as_one(self):
        reg = _reg_with(_src("S01"), _src("S02", reprint_of="S01"))
        board = _board(reg, ("E1", "C", "S01"), ("E2", "C", "S02"))
        cl = CoverageChecklist("CASE-TEST", [_item("T1", ["E1", "E2"])])
        s = cl.compute(board, reg)
        self.assertEqual(s["items"][0]["status"], "single")
        self.assertEqual(s["items"][0]["origins"], 1)

    def test_two_independent_origins_cover(self):
        reg = _reg_with(_src("S01"), _src("S03"))
        board = _board(reg, ("E1", "C", "S01"), ("E2", "C", "S03"))
        cl = CoverageChecklist("CASE-TEST", [_item("T1", ["E1", "E2"])])
        s = cl.compute(board, reg)
        self.assertEqual(s["items"][0]["status"], "covered")
        self.assertEqual(s["items"][0]["origins"], 2)

    def test_rumour_only_is_missing_and_flagged(self):
        reg = _reg_with(_src("S01"))
        board = _board(reg, ("E1", "F", "S01"))
        cl = CoverageChecklist("CASE-TEST", [_item("T1", ["E1"])])
        s = cl.compute(board, reg)
        self.assertEqual(s["items"][0]["status"], "missing")
        self.assertTrue(s["items"][0]["only_unusable"])
        self.assertEqual(s["only_unusable"], 1)

    def test_unverified_only_is_missing_and_flagged(self):
        reg = _reg_with(_src("S01"))
        board = _board(reg, ("E1", "H", "S01"))
        cl = CoverageChecklist("CASE-TEST", [_item("T1", ["E1"])])
        s = cl.compute(board, reg)
        self.assertEqual(s["items"][0]["status"], "missing")
        self.assertTrue(s["items"][0]["only_unusable"])

    def test_score_math(self):
        reg = _reg_with(_src("S01"), _src("S02"))
        board = _board(reg, ("E1", "C", "S01"), ("E2", "C", "S02"),
                       ("E3", "C", "S01"))
        items = [_item("I1", ["E1", "E2"]),   # covered
                 _item("I2", ["E1", "E2"]),   # covered
                 _item("I3", ["E3"]),         # single
                 _item("I4", [])]             # missing
        s = CoverageChecklist("CASE-TEST", items).compute(board, reg)
        self.assertEqual((s["covered"], s["single"], s["missing"]), (2, 1, 1))
        self.assertEqual(s["score"], 0.625)

    def test_not_applicable_excluded_from_total(self):
        reg = _reg_with(_src("S01"))
        board = _board(reg, ("E1", "C", "S01"))
        it = _item("I1", ["E1"])
        na = _item("I2", [])
        na.not_applicable = True
        s = CoverageChecklist("CASE-TEST", [it, na]).compute(board, reg)
        self.assertEqual(s["total"], 1)
        self.assertEqual(s["score"], 0.5)


class TestValidate(unittest.TestCase):
    def test_unknown_evidence_and_path_are_problems(self):
        reg = _reg_with(_src("S01"))
        board = _board(reg, ("E1", "C", "S01"))
        it = _item("T1", ["E1", "NOPE"])
        it.paths_tried = [{"path": "smoke_signals", "status": "tried"},
                          {"path": "web_search", "status": "maybe"}]
        problems = CoverageChecklist("CASE-TEST", [it]).validate(board)
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("NOPE" in p for p in problems))
        self.assertTrue(any("smoke_signals" in p for p in problems))
        self.assertTrue(any("maybe" in p for p in problems))

    def test_save_load_round_trip(self):
        cl = CoverageChecklist.from_template("CASE-TEST")
        with tempfile.TemporaryDirectory() as d:
            p = cl.save(Path(d))
            raw = json.loads(p.read_text(encoding="utf-8"))
            back = CoverageChecklist.load(Path(d))
        self.assertEqual(len(back.items), 22)
        self.assertEqual(back.items[0].item_id, "C01")
        self.assertEqual(raw["template_version"], "1")


class TestRealPacks(unittest.TestCase):
    def test_nanda_coverage(self):
        loaded = load_case(NANDA_DIR)
        cl = CoverageChecklist.load(NANDA_DIR)
        self.assertIsNotNone(cl)
        self.assertEqual(cl.validate(loaded["board"]), [])
        s = cl.compute(loaded["board"], loaded["registry"])
        self.assertEqual(s["total"], 22)
        self.assertEqual((s["covered"], s["single"], s["missing"]), (10, 9, 3))
        self.assertEqual(s["score"], 0.6591)
        self.assertEqual(s["missing_ids"], ["C03", "C10", "C11"])
        self.assertEqual(s["only_unusable"], 0)

    def test_baiyin_coverage(self):
        loaded = load_case(BAIYIN_DIR)
        cl = CoverageChecklist.load(BAIYIN_DIR)
        self.assertIsNotNone(cl)
        self.assertEqual(cl.validate(loaded["board"]), [])
        s = cl.compute(loaded["board"], loaded["registry"])
        self.assertEqual(s["total"], 21)  # C16 not applicable
        self.assertEqual((s["covered"], s["single"], s["missing"]), (7, 8, 6))
        self.assertEqual(s["score"], 0.5238)
        self.assertEqual(s["only_unusable"], 1)
        c22 = [i for i in s["items"] if i["item_id"] == "C22"][0]
        self.assertTrue(c22["only_unusable"])

    def test_markdown_section(self):
        loaded = load_case(NANDA_DIR)
        cl = CoverageChecklist.load(NANDA_DIR)
        s = cl.compute(loaded["board"], loaded["registry"])
        lines = cl.markdown_section(s)
        text = "\n".join(lines)
        self.assertIn("65.9%", text)
        self.assertIn("C03", text)
        self.assertIn("公开资料永远无法覆盖", text)

    def test_cli_coverage_command(self):
        r = subprocess.run([sys.executable, "-m", "detective_os.cli",
                            "coverage", str(NANDA_DIR)],
                           cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("65.9%", r.stdout)


if __name__ == "__main__":
    unittest.main()
