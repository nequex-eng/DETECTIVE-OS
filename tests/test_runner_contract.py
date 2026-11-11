"""Guard the scheduled runner handoff contract against accidental drift."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "runner-v2-instructions.md"


class TestScheduledRunnerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_all_structured_intake_fields_are_explicitly_consumed(self):
        for field in (
            "intake.objective", "intake.time_range",
            "intake.evidence_cutoff_date", "intake.known_facts",
            "intake.questions", "intake.exclusions",
            "intake.source_urls", "intake.user_source_text", "intake.materials",
            "intake.parent_job_id", "intake.parent_report_context",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.text)

    def test_collection_requires_real_page_text_and_provenance(self):
        for field in (
            '"sources"', '"texts"', '"paths_tried"', '"source_id"',
            '"published_at"', '"origin_url"', '"reprint_of"',
            '"reliability"', '"last_verified"',
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.text)
        self.assertIn("substantive page text actually read", self.text)
        self.assertIn("never inflate source counts with reprints", self.text)

    def test_runner_delegates_mechanical_execution_and_final_status(self):
        self.assertIn("python3 scripts/run_job.py <job_id>", self.text)
        self.assertIn("Never set a job to `done` yourself", self.text)
        self.assertIn("Confirm `status=done`, a non-null result", self.text)

    def test_evidence_cutoff_and_unverified_material_safeguards(self):
        self.assertIn("exclude all sources and information published after that date", self.text)
        self.assertIn("user-provided leads", self.text)
        self.assertIn("never create a grade-C fact from pasted text alone", self.text)
        self.assertIn("incremental continuation", self.text)
        self.assertIn("preserves the previous result", self.text)
        self.assertIn("Never identify a real person as the perpetrator", self.text)


if __name__ == "__main__":
    unittest.main()
