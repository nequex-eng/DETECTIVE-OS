import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_job import read_static_case_checkpoint


class StaticCaseFollowupTests(unittest.TestCase):
    def test_archived_1996_case_is_loaded_as_incremental_baseline(self):
        (collected, sources, texts, candidates, likelihoods,
         categories, report, case) = read_static_case_checkpoint("case-cn-1996-001")

        self.assertEqual(case["case_id"], "CASE-CN-1996-001")
        self.assertEqual(report["case_id"], "CASE-CN-1996-001")
        self.assertTrue(report["verdict"])
        self.assertEqual(len(sources), 8)
        self.assertEqual(texts, {})
        self.assertGreater(len(candidates), 0)
        self.assertTrue(all(c["source_id"].startswith("S") for c in candidates))
        self.assertTrue(all(c["quote"] for c in candidates))
        # F/G/H rumor, inference, and unknown records must never enter baseline.
        original = __import__("json").loads(
            (ROOT / "cases/case-cn-1996-001/evidence.json").read_text(encoding="utf-8"))
        eligible = [e for e in original if e.get("grade") in "ABCDE"
                    and e.get("content") and e.get("original_quote") and e.get("source_id")]
        self.assertEqual(len(candidates), len(eligible))
        self.assertTrue(all("|F" in key for key in likelihoods))
        self.assertTrue(all(key.startswith("F") for key in categories))
        self.assertTrue(collected["paths_tried"])


if __name__ == "__main__":
    unittest.main()
