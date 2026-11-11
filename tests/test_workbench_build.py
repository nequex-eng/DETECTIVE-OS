"""T3 acceptance tests for the data-driven React workbench build."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data" / "cases"


class TestWorkbenchBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))

    def test_react_workbench_is_built_and_has_ten_navigation_modules(self):
        page = PUBLIC / "workbench.html"
        assets = PUBLIC / "workbench-assets"
        self.assertTrue(page.exists(), "Vite must emit public/workbench.html")
        self.assertTrue(assets.exists(), "Vite must emit hashed workbench assets")
        app = (ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
        for view in ('"cases"', '"sources"', '"evidence"', '"timeline"', '"graph"',
                     '"contradictions"', '"hypotheses"', '"plan"', '"review"', '"report"'):
            self.assertIn(view, app)

    def test_case_index_and_all_case_payloads_are_real_and_traceable(self):
        self.assertEqual(len(self.index), 6)
        self.assertEqual(
            {x["case_id"] for x in self.index},
            {"CASE-CN-1996-001", "CASE-CN-1988-001", "CASE-NO-1970-001",
             "CASE-DRAFT-6c31bb54", "CASE-DRAFT-9d0c95d6", "CASE-DRAFT-c23978f6"})
        for row in self.index:
            payload = json.loads(
                (DATA / (row["case_id"] + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(payload["case"]["case_id"], row["case_id"])
            self.assertTrue(payload["reportMarkdown"])
            self.assertTrue(payload["bayesian"]["posteriors"])
            self.assertTrue(payload["sources"])
            self.assertTrue(payload["evidence"])
            source_ids = {s["source_id"] for s in payload["sources"]}
            evidence_ids = {e["evidence_id"] for e in payload["evidence"]}
            for ev in payload["evidence"]:
                if ev["grade"] in ("A", "B", "C", "D", "E"):
                    self.assertIn(ev["source_id"], source_ids)
                elif ev.get("source_id"):
                    self.assertIn(ev["source_id"], source_ids)
            for edge in payload["relationships"]:
                self.assertIn(edge["from_id"], {e["entity_id"] for e in payload["entities"]})
                self.assertIn(edge["to_id"], {e["entity_id"] for e in payload["entities"]})
            self.assertTrue((PUBLIC / payload["reportUrl"].lstrip("/")).exists())

    def test_completed_investigations_are_auto_archived_without_review_queue(self):
        index = (PUBLIC / "index.html").read_text(encoding="utf-8")
        self.assertIn("已完成调查 · 自动归档", index)
        self.assertIn("COMPLETE · 自动归档", index)
        self.assertNotIn("待调查 · 草稿案卷", index)
        self.assertNotIn("调查完成 · 等待复核", index)
        self.assertIn("张俊杰（已完成任务）", index)
        self.assertIn("e5b884e5-e8ac-4cdc-b57f-8aa50d840cb1", index)
        self.assertIn("结构化案卷完整度：未完成", index)

    def test_archived_case_pages_deep_link_to_case_specific_analysis_modules(self):
        for case_id in ("case-cn-1996-001", "case-cn-1988-001", "case-no-1970-001"):
            page = (PUBLIC / (case_id + ".html")).read_text(encoding="utf-8")
            self.assertIn("workbench.html?case=CASE-", page)
            self.assertIn("tab=timeline", page)
            self.assertIn("tab=graph", page)
            self.assertIn("tab=contradictions", page)

    def test_isdal_workbench_payload_contains_six_sources_and_sixteen_evidence(self):
        payload = json.loads((DATA / "CASE-NO-1970-001.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["sources"]), 6)
        self.assertEqual(len(payload["evidence"]), 16)
        self.assertEqual(len(payload["events"]), 7)
        self.assertEqual(len(payload["contradictions"]), 4)
        self.assertEqual(payload["bayesian"]["verdict"].split(":")[0], "undecided")
        self.assertFalse(any(e.get("is_suspect") for e in payload["entities"]))


if __name__ == "__main__":
    unittest.main()
