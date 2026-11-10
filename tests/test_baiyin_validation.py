"""Baiyin validation tests: the engine, fed pre-arrest public facts only,
must rank the true profile first — without ever seeing ground truth.

Run: python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from detective_os.cli import load_case  # noqa: E402

CASE_DIR = ROOT / "cases" / "case-cn-1988-001"


class TestBaiyinValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load_case(CASE_DIR)
        cls.bayes = cls.loaded["hypotheses"].bayesian()
        cls.post = {s["hypothesis_id"]: s["posterior"]
                    for s in cls.bayes["posteriors"]}
        cls.ranked = [s["hypothesis_id"] for s in cls.bayes["posteriors"]]

    def test_ground_truth_never_enters_the_engine(self):
        """Integrity: no evidence mentions the perpetrator, the arrest,
        or DNA-Y. The engine ranks from pre-arrest facts alone."""
        for e in self.loaded["board"].items.values():
            self.assertNotIn("高承勇", e.content)
            self.assertNotIn("DNA-Y", e.content)
            self.assertNotIn("落网", e.content)
        self.assertNotIn("ground-truth", str(self.loaded.keys()))

    def test_true_profile_ranked_first(self):
        """H1 (single, long-term local, stranger stalking) must rank first."""
        self.assertEqual(self.ranked[0], "H1")

    def test_single_beats_multiple(self):
        single = self.post["H1"] + self.post["H2"]
        multi = self.post["H3"] + self.post["H5"]
        self.assertGreater(single, multi)

    def test_local_beats_drifter(self):
        self.assertGreater(self.post["H1"], self.post["H2"])

    def test_independent_cases_ranked_last(self):
        """Same DNA/fingerprints across scenes must push H5 to the bottom."""
        self.assertEqual(self.ranked[-1], "H5")

    def test_no_early_winner_when_close(self):
        """If the top two are close, the verdict must stay undecided —
        even when the ranking itself is right."""
        top_two = self.bayes["posteriors"][:2]
        gap = top_two[0]["posterior"] - top_two[1]["posterior"]
        if gap < 0.10:
            self.assertTrue(self.bayes["verdict"].startswith("undecided"))


if __name__ == "__main__":
    unittest.main()
