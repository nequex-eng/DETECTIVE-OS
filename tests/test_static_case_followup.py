import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_job import read_static_case_checkpoint


class StaticCaseFollowupTests(unittest.TestCase):
    def test_archived_case_packs_load_as_incremental_baselines(self):
        for slug in ("case-cn-1996-001", "case-cn-1988-001", "case-no-1970-001"):
            with self.subTest(case=slug):
                (collected, sources, texts, candidates, likelihoods,
                 categories, report, case) = read_static_case_checkpoint(slug)

                self.assertEqual(report["case_id"], case["case_id"])
                self.assertTrue(report["verdict"])
                self.assertGreater(len(sources), 0)
                self.assertEqual(texts, {})
                self.assertGreater(len(candidates), 0)
                self.assertTrue(all(c["source_id"].startswith("S") for c in candidates))
                self.assertTrue(all(c["quote"] for c in candidates))
                original = __import__("json").loads(
                    (ROOT / "cases" / slug / "evidence.json").read_text(encoding="utf-8"))
                eligible = [e for e in original
                            if str(e.get("grade", "")).upper() in "ABCDE"
                            and e.get("content") and e.get("original_quote") and e.get("source_id")]
                self.assertEqual(len(candidates), len(eligible))
                self.assertTrue(all("|F" in key for key in likelihoods))
                self.assertTrue(all(key.startswith("F") for key in categories))
                self.assertTrue(collected["paths_tried"])

if __name__ == "__main__":
    unittest.main()
